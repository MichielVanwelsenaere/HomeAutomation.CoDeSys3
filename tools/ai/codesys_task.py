# -*- coding: utf-8 -*-
"""Headless CODESYS driver for the AI-assisted development loop.

This file runs INSIDE the CODESYS ScriptEngine (IronPython 2.7), not in CPython.
It is launched by tools/ai/codesys.ps1, which writes a task file and passes its
path as the single script argument:

    CODESYS.exe --noUI --runscript=codesys_task.py --scriptargs:"<task.json>"

Tasks (task.json key "task"):

    tree     dump the project object tree, so a human or an agent can see what
             the project actually contains without opening the GUI
    export   export the IEC content of the real project to PLCopen XML
    verify   import candidate PLCopen XML into a throwaway copy of the project,
             build it, and report every compiler message
    apply    import candidate PLCopen XML into the real project and save it

Everything the caller needs comes back as JSON on disk (task.json "report"),
because a --noUI CODESYS process has no usable stdout.

IronPython 2.7 applies: no f-strings, no dict comprehensions in old syntax
traps, and the standard library is the one shipped in CODESYS/ScriptLib.
"""

import codecs
import json
import os
import re
import sys
import traceback

# Injected by the ScriptEngine: system, projects, device_repository, ...
# Referenced without import on purpose.

SEVERITY_ORDER = {"FatalError": 0, "Error": 1, "Warning": 2, "Information": 3, "Text": 4}
BAD_SEVERITIES = ("FatalError", "Error")


# ---------------------------------------------------------------- utilities


def read_task():
    if len(sys.argv) < 2:
        raise ValueError("no task file passed via --scriptargs")
    path = sys.argv[1].strip().strip('"')
    # utf-8-sig: tolerate a BOM if the caller wrote one.
    fh = codecs.open(path, "r", "utf-8-sig")
    try:
        return json.loads(fh.read())
    finally:
        fh.close()


_LOG_PATH = [None]


def log(message):
    """Append a progress line, flushed immediately.

    A --noUI CODESYS process has no usable stdout, so this file is the only way
    to see how far the script got when something kills it mid-run.
    """
    path = _LOG_PATH[0]
    if not path:
        return
    try:
        fh = codecs.open(path, "a", "utf-8")
        try:
            fh.write(u"%s\n" % message)
        finally:
            fh.close()
    except Exception:
        pass


def write_report(path, payload):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    # Serialise before opening the file: a serialisation failure used to
    # truncate the report to zero bytes and leave no clue why.
    try:
        # default=: .NET values (enums, UInt32, Guid) reach here as opaque
        # objects that IronPython's json refuses; stringify rather than lose
        # the whole report over one field.
        # ensure_ascii=False keeps the encoder off the ascii path, which chokes
        # on non-ASCII compiler messages; the file itself is written as utf-8.
        body = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=u)
    except Exception:
        log("report serialisation failed:\n%s" % traceback.format_exc())
        body = json.dumps(
            {
                "ok": False,
                "task": u(payload.get("task")),
                "errors": [u("report serialisation failed: %s" % traceback.format_exc())],
                "messages": [],
            },
            indent=2,
            ensure_ascii=False,
            default=u,
        )
    fh = codecs.open(path, "w", "utf-8")
    try:
        fh.write(body)
    finally:
        fh.close()


def object_path(obj):
    """Slash-separated path of an object inside the project tree."""
    parts = []
    cur = obj
    guard = 0
    while cur is not None and guard < 40:
        guard += 1
        try:
            if cur.is_root:
                break
        except Exception:
            pass
        try:
            parts.append(cur.get_name())
        except Exception:
            break
        try:
            cur = cur.parent
        except Exception:
            break
    parts.reverse()
    return "/".join(parts)


def u(value):
    """Coerce anything to unicode without ever raising.

    Compiler messages carry non-ASCII text (a stray currency symbol in a string
    literal is enough), and IronPython's json encoder tries to ASCII-encode
    plain str, so everything that lands in the report goes through here.
    """
    if value is None:
        return None
    if isinstance(value, unicode):  # noqa: F821 - Python 2 builtin
        return value
    try:
        return unicode(value)  # noqa: F821
    except Exception:
        try:
            return unicode(str(value), "utf-8", "replace")  # noqa: F821
        except Exception:
            return u"<unprintable>"


def sort_key(name):
    """Case-insensitive key that sorts `_` below letters and digits.

    CODESYS wrote the committed export using a .NET culture-aware comparison,
    where punctuation carries less weight than alphanumerics. Plain ordinal
    sorting would put FB_RS485_EASTRON_SDM220 before ..._SDM_POWER; this key
    keeps the order the project already has.
    """
    return (name or "").lower().replace("_", "\x00")


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ---------------------------------------------------------------- messages


def clear_all_messages():
    for cat in list(safe(lambda: system.get_message_categories(True), []) or []):
        safe(lambda: system.clear_messages(cat))


def collect_messages():
    """Every message in the store, from every active category.

    Compiler output does not live in the default ScriptMessage category, so
    filtering by a single category GUID would silently drop the errors we came
    for. We sweep all active categories and dedupe instead.
    """
    found = []
    seen = {}
    for cat in list(safe(lambda: system.get_message_categories(True), []) or []):
        category = safe(lambda: system.get_message_category_description(cat), str(cat))
        for msg in list(safe(lambda: system.get_message_objects(cat), []) or []):
            severity = u(safe(lambda: msg.severity, "Information"))
            obj = safe(lambda: msg.object)
            item = {
                "category": u(category),
                "severity": severity,
                "text": u(safe(lambda: msg.text, "") or ""),
                "object": u(object_path(obj)) if obj is not None else None,
                "position": u(safe(lambda: msg.position_text)) or None,
                # .NET integer types are not JSON serialisable as-is.
                "number": safe(lambda: int(msg.number)),
            }
            key = (item["severity"], item["text"], item["object"], item["position"])
            if key in seen:
                # The same message can appear in more than one category. Count
                # the collapses instead of hiding them, so a mismatch with
                # CODESYS's own "N errors, M warnings" line is explainable.
                seen[key]["occurrences"] += 1
                continue
            item["occurrences"] = 1
            seen[key] = item
            found.append(item)
    found.sort(key=lambda m: (SEVERITY_ORDER.get(m["severity"], 9), m["object"] or "", m["text"]))
    return found


# ---------------------------------------------------------------- reporters


class Reporter(ImportReporter):  # noqa: F821 - ScriptEngine global
    """Import reporter that records instead of prompting.

    Must subclass the injected ImportReporter: the .NET binding wants an
    IImportReporter and will not accept a merely duck-typed class.

    resolve_conflict answers Replace: a candidate is a new version of a block,
    so overwriting the sandbox copy is the whole point. In `apply` mode the
    wrapper has already made the caller confirm.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []
        # Deliberately not named after the callbacks below: an instance
        # attribute would shadow the method the ScriptEngine calls.
        self.added_objects = []
        self.replaced_objects = []
        self.skipped_objects = []

    def error(self, message):
        self.errors.append(str(message))

    def warning(self, message):
        self.warnings.append(str(message))

    def resolve_conflict(self, obj):
        return ConflictResolve.Replace  # noqa: F821 - ScriptEngine global

    def added(self, obj):
        self.added_objects.append(object_path(obj))

    def replaced(self, obj):
        self.replaced_objects.append(object_path(obj))

    def skipped(self, objectname):
        self.skipped_objects.append(str(objectname))

    @property
    def aborting(self):
        return False

    def as_dict(self):
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "added": sorted(set(self.added_objects)),
            "replaced": sorted(set(self.replaced_objects)),
            "skipped": sorted(set(self.skipped_objects)),
        }


class ExportReporterCollect(ExportReporter):  # noqa: F821 - ScriptEngine global
    """Same rule as Reporter: subclass the injected base, don't duck-type it."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.nonexportable_objects = []

    def error(self, obj, message):
        self.errors.append("%s: %s" % (object_path(obj) if obj else "-", message))

    def warning(self, obj, message):
        self.warnings.append("%s: %s" % (object_path(obj) if obj else "-", message))

    def nonexportable(self, obj):
        self.nonexportable_objects.append(object_path(obj))

    @property
    def aborting(self):
        return False

    def as_dict(self):
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "nonexportable": sorted(set(self.nonexportable_objects)),
        }


# ---------------------------------------------------------------- tree


def describe(obj):
    return {
        "name": safe(lambda: obj.get_name(), "?"),
        "path": object_path(obj),
        "is_folder": bool(safe(lambda: obj.is_folder, False)),
        "is_device": bool(safe(lambda: obj.is_device, False)),
        "is_application": bool(safe(lambda: obj.is_application, False)),
        "is_task_configuration": bool(safe(lambda: obj.is_task_configuration, False)),
        "is_libman": bool(safe(lambda: obj.is_libman, False)),
        "has_declaration": bool(safe(lambda: obj.has_textual_declaration, False)),
        "has_implementation": bool(safe(lambda: obj.has_textual_implementation, False)),
        "type": str(safe(lambda: obj.type, "")),
    }


def walk(node, out, depth=0):
    for child in list(safe(lambda: node.get_children(False), []) or []):
        item = describe(child)
        item["depth"] = depth
        out.append(item)
        walk(child, out, depth + 1)


# ---------------------------------------------------------------- export set


# Top-level objects PLCopen cannot carry, and which the committed export has
# never contained. Everything else at project level is exported.
EXPORT_SKIP = ("Project Settings", "__VisualizationStyle")


def iec_export_roots(proj):
    """Flat list of every exportable object, matching the committed PLCopen.xml.

    Two things make this less obvious than "export the top level":

    * The function blocks live in the project-level POU pool (BASIC, MQTT,
      HVAC, ...), the programs and GVLs under the device node. Exporting only
      the application would silently drop every function block.
    * A folder is not exportable, and passing one as a root makes the export
      report it and skip its whole subtree. So folders are walked *through*,
      never passed.

    We therefore descend through containers and collect the objects that carry
    content. Descent stops at objects that own code, because their children are
    methods and actions, which `recursive=True` brings along.
    """
    found = []  # (top_level_name, object_name, object)

    def collect(node, depth, top):
        if depth > 12:
            return
        for child in list(safe(lambda: node.get_children(False), []) or []):
            name = safe(lambda: child.get_name(), "")
            if depth == 0 and name in EXPORT_SKIP:
                continue
            if safe(lambda: child.is_project_info, False):
                continue
            top_name = name if depth == 0 else top
            is_folder = bool(safe(lambda: child.is_folder, False))
            if not is_folder:
                found.append((top_name, name, child))
            owns_code = bool(safe(lambda: child.has_textual_declaration, False)) or bool(
                safe(lambda: child.has_textual_implementation, False)
            )
            if not owns_code:
                collect(child, depth + 1, top_name)

    collect(proj, 0, "")
    # Deterministic order, so re-exporting an unchanged project produces an
    # unchanged file and diffs stay readable. `_` is folded below alphanumerics
    # to match the .NET culture-aware sort CODESYS itself used, which keeps the
    # committed ordering (FB_MQTT_BASE before FB_MqttPublishQueue).
    found.sort(key=lambda item: (sort_key(item[0]), sort_key(item[1])))
    return [item[2] for item in found]


# ---------------------------------------------------------------- tasks


# A candidate POU sitting unreferenced in the project-level POU pool is not
# part of any application, so CODESYS never generates code for it and `verify`
# would report a clean build for code that does not compile. Everything below
# exists to make imported blocks reachable from the task configuration.
FB_PATTERN = re.compile(r'<pou\s+name="([^"]+)"\s+pouType="functionBlock"')
POU_PATTERN = re.compile(r'<pou\s+name="([^"]+)"\s+pouType="([^"]+)"')
# An <FB_init> method taking parameters means the instance cannot be declared
# without supplying them, so such blocks are reported instead of instantiated.
FB_INIT_PATTERN = re.compile(
    r'<Method\s+name="FB_init"[^>]*>.*?</Method>', re.DOTALL | re.IGNORECASE
)


def read_text(path):
    fh = codecs.open(path, "r", "utf-8-sig")
    try:
        return fh.read()
    finally:
        fh.close()


def candidate_pous(path):
    """Function blocks in a candidate file, split by whether we can declare one.

    Returns (instantiable, skipped) where skipped is a list of (name, reason).
    """
    try:
        text = read_text(path)
    except Exception:
        return [], [("<file>", "could not be read: %s" % traceback.format_exc())]

    instantiable = []
    skipped = []
    fb_names = FB_PATTERN.findall(text)
    for name, pou_type in POU_PATTERN.findall(text):
        if pou_type != "functionBlock":
            skipped.append((name, "pouType=%s is only compiled where it is called" % pou_type))
    # Granularity is per file, not per block: any parameterised FB_init in the
    # file holds back every block in it. Harmless under the one-block-per-file
    # convention, and it errs towards reporting rather than a false pass.
    init = FB_INIT_PATTERN.search(text)
    for name in fb_names:
        if init is not None and "<inputVars>" in init.group(0):
            skipped.append((name, "FB_init takes parameters; declare it by hand at a real call site"))
        else:
            instantiable.append(name)
    return instantiable, skipped


def harness_host(proj):
    """A program the task configuration already calls, so it gets compiled.

    Injecting into an existing task-bound program avoids having to create a POU
    and a task, and guarantees the code is part of the application.
    """
    for node in list(safe(lambda: proj.get_children(True), []) or []):
        if not safe(lambda: node.is_task_configuration, False):
            continue
        for task in list(safe(lambda: node.get_children(False), []) or []):
            for call in list(safe(lambda: task.get_children(False), []) or []):
                name = safe(lambda: call.get_name(), "")
                if not name:
                    continue
                for match in list(safe(lambda: proj.find(name, True), []) or []):
                    # The task's own call node shares the name but owns no code.
                    if safe(lambda: match.has_textual_declaration, False):
                        return match
    return None


def read_manual_harness(folder):
    """Author-supplied harness text from .ai/candidates/_harness.{decl,impl}.

    Auto-instantiation cannot declare a block whose FB_init takes parameters,
    because it has no way to invent the arguments. These two optional files let
    the author take over: `_harness.decl` is appended to the host program's
    declaration (a complete VAR ... END_VAR block), `_harness.impl` to its body.
    """
    manual = {"decl": u"", "impl": u""}
    if not folder or not os.path.isdir(folder):
        return manual
    for key in ("decl", "impl"):
        path = os.path.join(folder, "_harness." + key)
        if os.path.isfile(path):
            try:
                manual[key] = read_text(path)
                log("harness: using manual %s (%d chars)" % (key, len(manual[key])))
            except Exception:
                log("harness: could not read %s:\n%s" % (path, traceback.format_exc()))
    return manual


def add_verify_harness(proj, result, files, candidates_folder=None):
    """Make candidate blocks reachable from the task configuration.

    Declaring an instance is enough: CODESYS generates code for an instantiated
    function block, so the body gets fully checked. Instances are not called by
    the auto-generated part, which keeps VAR_IN_OUT and required inputs out of
    the picture; a manual harness may call them explicitly.
    """
    instantiable = []
    skipped = []
    for path in files:
        good, bad = candidate_pous(path)
        instantiable.extend(good)
        skipped.extend([{"name": n, "reason": r} for n, r in bad])

    manual = read_manual_harness(candidates_folder)
    # A block named in the manual harness is covered after all, so move it out
    # of the not-instantiated list rather than warning about it misleadingly.
    if manual["decl"] or manual["impl"]:
        manual_text = manual["decl"] + u"\n" + manual["impl"]
        still_skipped = []
        for entry in skipped:
            if entry["name"] in manual_text:
                instantiable.append(entry["name"])
                log("harness: %s covered by the manual harness" % entry["name"])
            else:
                still_skipped.append(entry)
        skipped = still_skipped

    harness = {
        "instantiated": sorted(set(instantiable)),
        "not_instantiated": skipped,
        "host": None,
        "manual": bool(manual["decl"] or manual["impl"]),
    }
    result["harness"] = harness

    auto = [n for n in instantiable if n not in (manual["decl"] + manual["impl"])]
    if not instantiable and not manual["decl"] and not manual["impl"]:
        log("harness: nothing to instantiate")
        return

    host = harness_host(proj)
    if host is None:
        result["errors"].append(
            "no task-bound program found to host the verify harness; "
            "candidate blocks would not have been compiled"
        )
        return

    harness["host"] = object_path(host)
    try:
        if auto:
            lines = [u"", u"// injected by tools/ai/codesys_task.py - sandbox only", u"VAR"]
            for index, name in enumerate(auto):
                lines.append(u"\tai_verify_%d : %s;" % (index, name))
            lines.append(u"END_VAR")
            # A second VAR block after the existing one is valid IEC, so this
            # needs no parsing of the host's declaration.
            host.textual_declaration.append(u"\n".join(lines) + u"\n")
            log("harness: auto-declared %d instance(s) in %s" % (len(auto), harness["host"]))
        if manual["decl"]:
            host.textual_declaration.append(u"\n" + manual["decl"] + u"\n")
            log("harness: appended manual declaration")
        if manual["impl"]:
            # Programs in this project keep their logic in actions, so the
            # program body itself is often empty and exposes no implementation.
            # Fall back to an action that does have one.
            target = host if safe(lambda: host.has_textual_implementation, False) else None
            if target is None:
                for child in list(safe(lambda: host.get_children(False), []) or []):
                    if safe(lambda: child.has_textual_implementation, False):
                        target = child
                        break
            if target is None:
                result["errors"].append(
                    "manual harness implementation could not be injected: neither %s nor any "
                    "of its actions exposes a textual implementation" % harness["host"]
                )
            else:
                target.textual_implementation.append(u"\n" + manual["impl"] + u"\n")
                harness["impl_host"] = u(object_path(target))
                log("harness: appended manual implementation to %s" % harness["impl_host"])
    except Exception:
        trace = traceback.format_exc()
        log("harness injection failed:\n%s" % trace)
        result["errors"].append("could not inject the verify harness: %s" % trace)


def candidate_files(folder):
    if not folder or not os.path.isdir(folder):
        return []
    names = [n for n in sorted(os.listdir(folder)) if n.lower().endswith(".xml")]
    return [os.path.join(folder, n) for n in names]


def do_tree(cfg, result):
    proj = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    try:
        out = []
        walk(proj, out)
        result["tree"] = out
        result["applications"] = [i["path"] for i in out if i["is_application"]]
    finally:
        safe(lambda: proj.close())


def do_export(cfg, result):
    proj = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    try:
        roots = iec_export_roots(proj)
        # cfg["only"]: export just these objects, by name. This is how the sync
        # skill lifts the shared function blocks out of the reference without
        # dragging along its programs, GVLs and device tree - which are that
        # installation's own logic and must never reach another one.
        only = cfg.get("only")
        if only:
            wanted = set([u(n) for n in only])
            roots = [r for r in roots if u(safe(lambda: r.get_name(), u"")) in wanted]
            found = set([u(safe(lambda: r.get_name(), u"")) for r in roots])
            missing = sorted(wanted - found)
            result["not_found"] = missing
            if missing:
                # Loud, not silent: a typo here produces a sync that quietly
                # leaves a block un-updated and still reports success.
                result["errors"].append("requested objects not found in project: %s" % ", ".join(missing))
                return
        result["exported_roots"] = [object_path(r) for r in roots]
        if not roots:
            result["errors"].append("no exportable IEC objects found")
            return
        reporter = ExportReporterCollect()
        target = cfg["output"]
        parent = os.path.dirname(target)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        # Positional, reporter first: the shipped .pyi stub has the argument
        # order wrong (see `probe`). export_folder_structure matches the
        # committed export, which the docs generator reads; declarations stay
        # in XML form there for the same reason. `plaintext` additionally emits
        # the lossless ST declaration text, which is far easier to read and
        # review - use it for a scratch copy, never for the committed export.
        plaintext = bool(cfg.get("plaintext"))
        log("exporting %d root(s) plaintext=%s" % (len(roots), plaintext))
        #               reporter, objects,      path,   recursive, folders, plaintext
        proj.export_xml(reporter, tuple(roots), target, True,      True,    plaintext)
        result["export"] = reporter.as_dict()
        result["output"] = target
        result["errors"].extend(reporter.errors)
    finally:
        safe(lambda: proj.close())


# ---------------------------------------------------------------- info


def text_of(obj, which):
    """Declaration or implementation text of an object, or None.

    `has_textual_*` lies often enough to matter: some objects report True and
    then raise on access (an SFC program has a declaration but no
    implementation *attribute at all*). So the presence flag is a hint and the
    access is guarded.
    """
    flag = "has_textual_" + which
    if not safe(lambda: getattr(obj, flag), False):
        return None
    holder = safe(lambda: getattr(obj, "textual_" + which), None)
    if holder is None:
        return None
    return safe(lambda: u(holder.text), None)


def digest(text):
    if text is None:
        return None
    import hashlib

    # Newlines and trailing whitespace are not semantic here, and CODESYS is not
    # consistent about them across a save cycle. Normalise so that "this block
    # is unchanged" does not turn on a line ending.
    norm = u"\n".join([line.rstrip() for line in text.replace(u"\r\n", u"\n").split(u"\n")])
    return hashlib.md5(norm.strip().encode("utf-8")).hexdigest()


# Object-type GUID of a task's call entry - the "PLC_PRG_MAIN" that appears
# under Task Configuration/MainTask as well as under PRG's. It carries no code
# and is not the program; it is a reference to it.
#
# This matters more than it looks. Indexing an inventory by name without
# filtering these gives you the EMPTY task-call node for every program in the
# project, because it sorts after the real one - so every program silently
# reads as "no declaration, no kind, nothing to see". The same duplication is
# what the project notes flag about find_editable returning the Task
# Configuration node instead of the program.
TASK_CALL_TYPE = "413e2a7d"

KIND_PATTERN = re.compile(
    r"^\s*(FUNCTION_BLOCK|FUNCTION|PROGRAM|INTERFACE|TYPE|VAR_GLOBAL|VAR_CONFIG)\b",
    re.IGNORECASE | re.MULTILINE,
)


def declared_kind(decl):
    """FUNCTION_BLOCK / PROGRAM / FUNCTION / TYPE / VAR_GLOBAL, from the text.

    The object-type GUID only distinguishes POU from DUT from GVL; it cannot
    tell a function block from a program, and that distinction is the whole
    basis of the sync decision - a function block is shared library code, a
    program is the installation's own logic. The declaration's first keyword is
    the authoritative answer and costs nothing.
    """
    if not decl:
        return None
    # Skip pragmas and comments ahead of the keyword: {attribute ...} lines and
    # a leading (* ... *) banner are both common here.
    text = re.sub(r"\(\*.*?\*\)", u" ", decl, flags=re.DOTALL)
    text = re.sub(r"^\s*\{[^}]*\}", u" ", text, flags=re.MULTILINE)
    match = KIND_PATTERN.search(text)
    return u(match.group(1).upper()) if match else None


def inventory(proj, full=False):
    """Every content-bearing object in the project, with a hash of its code.

    This is the mechanism the sync skill runs on. Comparing two projects object
    by object on a hash of (declaration + implementation + every member) answers
    "which function blocks actually differ from the reference" without exporting,
    parsing or diffing a 19000-line XML file on either side.
    """
    items = []

    def visit(node, depth, top):
        for child in list(safe(lambda: node.get_children(False), []) or []):
            name = u(safe(lambda: child.get_name(), u"?"))
            if safe(lambda: child.is_project_info, False):
                continue
            top_name = name if depth == 0 else top
            is_folder = bool(safe(lambda: child.is_folder, False))
            decl = text_of(child, "declaration")
            impl = text_of(child, "implementation")
            owns_code = decl is not None or impl is not None
            if not is_folder:
                # Members (methods, actions, properties) roll into the parent's
                # signature: a changed method is a changed function block, and
                # the sync replaces whole objects anyway.
                members = []
                if owns_code:
                    for m in list(safe(lambda: child.get_children(False), []) or []):
                        m_decl = text_of(m, "declaration")
                        m_impl = text_of(m, "implementation")
                        if m_decl is None and m_impl is None:
                            continue
                        entry = {
                            "name": u(safe(lambda: m.get_name(), u"?")),
                            "decl_hash": digest(m_decl),
                            "impl_hash": digest(m_impl),
                        }
                        if full:
                            entry["decl"] = m_decl
                            entry["impl"] = m_impl
                        members.append(entry)
                    members.sort(key=lambda e: e["name"])
                item = {
                    "name": name,
                    "path": object_path(child),
                    "top": top_name,
                    "depth": depth,
                    "is_folder": is_folder,
                    "is_device": bool(safe(lambda: child.is_device, False)),
                    "is_application": bool(safe(lambda: child.is_application, False)),
                    "is_libman": bool(safe(lambda: child.is_libman, False)),
                    "is_task_configuration": bool(safe(lambda: child.is_task_configuration, False)),
                    "type": u(safe(lambda: str(child.type), u"")),
                    "is_task_call": u(safe(lambda: str(child.type), u"")).lower().startswith(TASK_CALL_TYPE),
                    "kind": declared_kind(decl),
                    "decl_hash": digest(decl),
                    "impl_hash": digest(impl),
                    "members": members,
                }
                # One hash per object, over everything that is code in it. This
                # is what a sync decision is made on.
                parts = [item["decl_hash"] or u"", item["impl_hash"] or u""]
                for m in members:
                    parts.append(u"%s:%s:%s" % (m["name"], m["decl_hash"] or u"", m["impl_hash"] or u""))
                item["signature"] = digest(u"|".join(parts)) if owns_code else None
                if full:
                    item["decl"] = decl
                    item["impl"] = impl
                items.append(item)
            # Descend through containers only. A POU's children are its members,
            # already folded into its signature above.
            if not owns_code and depth < 12:
                visit(child, depth + 1, top_name)

    visit(proj, 0, u"")
    items.sort(key=lambda i: (sort_key(i["top"]), sort_key(i["name"])))
    return items


def library_references(proj):
    """Every library the project references, from every library manager in it."""
    out = []
    for child in list(safe(lambda: proj.get_children(True), []) or []):
        if not safe(lambda: child.is_libman, False):
            continue
        manager = object_path(child)
        refs = safe(lambda: list(child.references), None)
        if refs is None:
            # Older/leaner managers only answer get_libraries().
            for nm in list(safe(lambda: child.get_libraries(False), []) or []):
                out.append({"manager": manager, "name": u(nm), "is_placeholder": None,
                            "namespace": None, "system": None})
            continue
        for ref in refs:
            out.append({
                "manager": manager,
                # "Name, Version (Company)" for a fixed reference, "#Name" for a
                # placeholder. The version is inside the name; there is no
                # separate version property on a reference.
                "name": u(safe(lambda: ref.name, u"?")),
                "is_placeholder": bool(safe(lambda: ref.is_placeholder, False)),
                "namespace": u(safe(lambda: ref.namespace, u"")),
                "system": bool(safe(lambda: ref.system_library, False)),
            })
    out.sort(key=lambda r: (r["manager"], r["name"]))
    return out


def device_identifications(proj):
    out = []
    for child in list(safe(lambda: proj.get_children(True), []) or []):
        if not safe(lambda: child.is_device, False):
            continue
        ident = safe(lambda: child.get_device_identification(), None)
        out.append({
            "name": u(safe(lambda: child.get_name(), u"?")),
            "path": object_path(child),
            "type_id": u(safe(lambda: str(ident.type), u"")),
            "id": u(safe(lambda: str(ident.id), u"")),
            "version": u(safe(lambda: str(ident.version), u"")),
            "simulation": bool(safe(lambda: child.get_simulation_mode(), False)),
        })
    return out


# The compiler version a project stores is NOT reachable from the scripting
# API - it is an application property with no accessor, and a reflection sweep
# over the application object finds nothing. Do not go looking again.
#
# The check that matters is empirical anyway: build the project with the
# installed IDE. If its stored compiler version is not installed, the build says
# so in as many words. That is what `verify -Baseline -Project <impl>` is for,
# and the sync skill gates on it.


def do_info(cfg, result):
    """Read-only description of a project: versions, libraries, code hashes.

    Opened with the default VersionUpdateFlags.NoUpdates, so inspecting an older
    installation project never converts it as a side effect of being looked at.
    That matters: a conversion is what an implementation project must NOT get
    by accident, and `open` would happily do it under other flags.
    """
    clear_all_messages()
    proj = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    try:
        full = bool(cfg.get("full"))
        # Messages raised by the open itself. A project written by an older
        # CODESYS reports its version-compatibility complaints here, which is the
        # closest thing to a "would this be converted?" answer the API offers.
        result["messages"] = collect_messages()
        info = {
            "path": u(cfg["project"]),
            "ide_version": u(cfg.get("ide_version", u"")),
            "applications": [object_path(c) for c in list(safe(lambda: proj.get_children(True), []) or [])
                             if safe(lambda: c.is_application, False)],
            "libraries": library_references(proj),
            "devices": device_identifications(proj),
            "project_info": {},
        }
        if safe(lambda: proj.has_project_info, False):
            pi = safe(lambda: proj.get_project_info(), None)
            if pi is not None:
                for name in ("company", "title", "version", "released", "author", "description"):
                    value = safe(lambda: getattr(pi, name), None)
                    if value is not None:
                        info["project_info"][name] = u(str(value))
        result["info"] = info
        result["objects"] = inventory(proj, full)
        log("info: %d objects, %d libraries" % (len(result["objects"]), len(info["libraries"])))
        target = cfg.get("output")
        if target:
            parent = os.path.dirname(target)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            fh = codecs.open(target, "w", "utf-8")
            try:
                fh.write(json.dumps({"info": info, "objects": result["objects"]},
                                    indent=2, sort_keys=True, ensure_ascii=False, default=u))
            finally:
                fh.close()
            result["output"] = target
    finally:
        safe(lambda: proj.close())


DIFF_NAMES = [
    (0x01, "ADDED"),
    (0x02, "DELETED"),
    (0x04, "CONTENT_CHANGED"),
    (0x08, "FOLDER_CHANGED"),
    (0x10, "ACCESS_RIGHTS_CHANGED"),
    (0x20, "PROPERTIES_CHANGED"),
    (0x40, "RENAMED"),
]


def diff_names(value):
    try:
        bits = int(value)
    except Exception:
        return [u(str(value))]
    if bits == 0:
        return [u"EQUAL"]
    return [u(name) for mask, name in DIFF_NAMES if bits & mask]


def do_compare(cfg, result):
    """CODESYS's own project comparison between two projects.

    `left` is cfg["project"] (the installation project), `right` is
    cfg["against"] (the reference). ADDED therefore means "only in the
    installation project" and DELETED means "in the reference but missing from
    the installation project" - read them in that direction, they are easy to
    get backwards.
    """
    left = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    right = None
    try:
        # primary=False: the second project must not take over as the primary,
        # or later calls quietly address the wrong one.
        right = projects.open(cfg["against"], primary=False, allow_readonly=True)  # noqa: F821
        # IGNORE_WHITESPACE | IGNORE_PROPERTIES: reformatting and metadata are
        # not a reason to resync a block. Numeric because the enum is not one of
        # the injected globals and the values are stable.
        flags = 1 | 4
        log("comparing ...")
        comparison = left.compare_to(right, flags)
        rows = []
        for obj in list(safe(lambda: comparison.get_changed_objects(0xFFFFFF), []) or []):
            state = safe(lambda: comparison.get_diff_state(obj), None)
            bits = safe(lambda: state.ObjectDifferences, 0) if state is not None else 0
            rows.append({
                "path": object_path(obj),
                "name": u(safe(lambda: obj.get_name(), u"?")),
                "difference": u"+".join(diff_names(bits)),
                "in_installation": state is not None and safe(lambda: state.left_object, None) is not None,
                "in_reference": state is not None and safe(lambda: state.right_object, None) is not None,
            })
        rows.sort(key=lambda r: (sort_key(r["path"]), sort_key(r["name"])))
        result["compare"] = {
            "left": u(cfg["project"]),
            "right": u(cfg["against"]),
            "differences": rows,
        }
        log("compare: %d difference(s)" % len(rows))
        target = cfg.get("output")
        if target:
            parent = os.path.dirname(target)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            fh = codecs.open(target, "w", "utf-8")
            try:
                fh.write(json.dumps(result["compare"], indent=2, sort_keys=True,
                                    ensure_ascii=False, default=u))
            finally:
                fh.close()
            result["output"] = target
    finally:
        if right is not None:
            safe(lambda: right.close())
        safe(lambda: left.close())


def build_and_collect(proj, result):
    apps = [c for c in list(safe(lambda: proj.get_children(True), []) or []) if safe(lambda: c.is_application, False)]
    result["applications"] = [object_path(a) for a in apps]
    log("applications: %s" % result["applications"])
    if not apps:
        result["errors"].append("no application found in project")
        return
    # Collected per application, because a build CLEARS the message store. With
    # one application that was invisible; with two, sweeping only at the end
    # returned the last application's messages and silently dropped the first
    # one's - which is how a baseline came back with none of this project's eight
    # known warnings in it.
    gathered = []
    gathered_keys = {}

    def gather():
        for item in collect_messages():
            key = (item["severity"], item["text"], item["object"], item["position"])
            if key in gathered_keys:
                gathered_keys[key]["occurrences"] += item.get("occurrences", 1)
                continue
            gathered_keys[key] = item
            gathered.append(item)

    for app in apps:
        name = object_path(app)
        clear_all_messages()
        try:
            log("building %s ..." % name)
            # rebuild(), not build(). `build()` is incremental, and an
            # application CODESYS considers up to date compiles nothing and
            # reports nothing - so it lands in `built` having said nothing about
            # itself. That is harmless until a project has two applications:
            # then a baseline recorded straight after a save came back with the
            # new application's messages only, and the eight known warnings of
            # the other one read as NEW on the next run. A complete message set
            # is worth the extra seconds.
            try:
                app.rebuild()
            except Exception:
                # No rebuild on this object: an incremental build is still
                # better than no build.
                log("rebuild unavailable for %s, falling back to build()" % name)
                app.build()
            result["built"].append(name)
            log("built %s" % name)
        except Exception:
            trace = traceback.format_exc()
            log("build failed for %s:\n%s" % (name, trace))
            result["errors"].append("build failed for %s: %s" % (name, trace))
        gather()
        log("messages after %s: %d" % (name, len(gathered)))
    gathered.sort(key=lambda m: (SEVERITY_ORDER.get(m["severity"], 9),
                                 m["object"] or "", m["text"]))
    result["messages"] = gathered
    log("messages: %d" % len(result["messages"]))


def find_or_create_member(target, kind, name, return_type=None):
    """Find a method/action/property on a POU, creating it if absent.

    Lets an edit spec add a brand-new method to an existing function block, which
    a candidate import cannot do safely (it would replace the whole object) and
    the plain textual API cannot do at all.
    """
    for child in list(safe(lambda: target.get_children(False), []) or []):
        if safe(lambda: child.get_name(), "") == name:
            return child, False
    factory = {"method": "create_method", "action": "create_action", "property": "create_property"}[kind]
    maker = getattr(target, factory)
    created = None
    # The .NET binding's argument order is not the stub's, so try the shapes.
    attempts = []
    if kind == "method":
        attempts = [
            lambda: maker(name, return_type),
            lambda: maker(name),
            lambda: maker(return_type, name),
        ]
    else:
        attempts = [lambda: maker(name)]
    errors = []
    for attempt in attempts:
        try:
            created = attempt()
            break
        except Exception:
            errors.append(traceback.format_exc().strip().split("\n")[-1])
    if created is None:
        raise ValueError("could not create %s %s: %s" % (kind, name, " | ".join(errors)))
    return created, True


def find_editable(proj, name, member=None, path=None):
    """Locate a POU (or one of its methods/actions) that owns editable text.

    `proj.find` also returns things that merely share the name, such as the task
    configuration's POU-call nodes, so candidates are filtered to objects that
    actually carry declaration or implementation text.

    A name alone stops being enough as soon as a project holds more than one
    controller: an installation with two PFCs has two `PLC_PRG_MAIN`, both
    text-owning and both legitimate, and every edit addressed by name is then
    refused as ambiguous. `path` is a substring of the object path - normally the
    device node, e.g. "Wago_G1_Annex/" - matched case-insensitively to pick
    one. It narrows, it never widens: if the filter leaves nothing, that is
    reported rather than falling back to the unfiltered set, because silently
    editing the other controller's program is exactly the failure this prevents.
    """
    def owns_text(obj):
        return bool(safe(lambda: obj.has_textual_declaration, False)) or bool(
            safe(lambda: obj.has_textual_implementation, False)
        )

    hits = [m for m in list(safe(lambda: proj.find(name, True), []) or []) if owns_text(m)]
    if not hits:
        return None, "no object named %s owns editable text" % name
    if path:
        needle = u(path).lower().replace(u"\\", u"/")
        narrowed = [h for h in hits
                    if needle in u(object_path(h)).lower().replace(u"\\", u"/")]
        if not narrowed:
            return None, "no object named %s under path %r (candidates: %s)" % (
                name, path, ", ".join([object_path(h) for h in hits]))
        hits = narrowed
    if len(hits) > 1:
        paths = ", ".join([object_path(h) for h in hits])
        hint = "" if path else " - add \"path\" to the edit to pick one"
        return None, "%s is ambiguous: %s%s" % (name, paths, hint)
    target = hits[0]
    if not member:
        return target, None
    for child in list(safe(lambda: target.get_children(False), []) or []):
        if safe(lambda: child.get_name(), "") == member and owns_text(child):
            return child, None
    return None, "%s has no method or action named %s that owns text" % (name, member)


def find_all_editable(proj, name, path=None):
    """Every text-owning object of that name, narrowed by `path` if given.

    `find_editable` refuses ambiguity, which is right for an edit - rewriting the
    wrong controller's program is unrecoverable. A rename sometimes genuinely
    means all of them: this project has two applications and therefore two
    `MqttVariables`, and the convention applies to both. So the ambiguity is
    surfaced here and the map decides, rather than being resolved by guesswork.
    """
    def owns_text(obj):
        return bool(safe(lambda: obj.has_textual_declaration, False)) or bool(
            safe(lambda: obj.has_textual_implementation, False)
        )

    hits = [m for m in list(safe(lambda: proj.find(name, True), []) or []) if owns_text(m)]
    if path:
        needle = u(path).lower().replace(u"\\", u"/")
        hits = [h for h in hits
                if needle in u(object_path(h)).lower().replace(u"\\", u"/")]
    return hits


def find_task_calls(proj, name):
    """The task configuration's call entries for a program of that name.

    A task calls a program through a separate object that carries the program's
    name and owns no code, so it is invisible to every text-owning filter here -
    and renaming the program without it leaves the task pointing at a name that no
    longer exists:

        Identifier 'PLC_PRG_MAIN' not defined   <.../Task Configuration/MainTask>

    That is a build failure rather than a silent one, so it costs a run rather
    than a project. It is still the reason a program rename is two renames.
    """
    out = []
    for hit in list(safe(lambda: proj.find(name, True), []) or []):
        kind = str(safe(lambda: hit.type, u""))
        if kind.startswith(TASK_CALL_TYPE):
            out.append(hit)
    return out


def find_deletable(proj, name):
    """Locate one object to remove: a POU, a DUT, an enum, or a folder.

    Deliberately looser than `find_editable`, which requires the object to own
    editable text - a folder owns none, and folders need deleting too once the
    last block inside one goes. The looseness is why the ambiguity check below is
    strict: `proj.find` also returns the task configuration's POU-call node for
    any program, so a bare "pick the first hit" would sometimes unhook a program
    from its task instead of deleting it. Text-owning objects therefore win, and
    a nameless tie is refused rather than guessed - a wrong delete is the one
    edit this harness cannot undo.
    """
    def owns_text(obj):
        return bool(safe(lambda: obj.has_textual_declaration, False)) or bool(
            safe(lambda: obj.has_textual_implementation, False)
        )

    hits = list(safe(lambda: proj.find(name, True), []) or [])
    if not hits:
        return None, "no object named %s" % name
    textual = [h for h in hits if owns_text(h)]
    if len(textual) == 1:
        return textual[0], None
    if len(textual) > 1:
        return None, "%s is ambiguous: %s" % (
            name, ", ".join([object_path(h) for h in textual])
        )
    # No text anywhere: a folder, which is only safe if it is the sole match.
    if len(hits) == 1:
        return hits[0], None
    return None, "%s is ambiguous: %s" % (
        name, ", ".join([object_path(h) for h in hits])
    )


def edit_text(obj, spec, result):
    """Apply one edit spec to one object's declaration and/or implementation.

    Editing through the textual API rather than by re-importing XML: a candidate
    import REPLACES the whole object (so a partial file drops methods), and
    appending to an existing POU's plaintext declaration in XML is silently
    ignored - the block keeps its old declaration and the only symptom is an
    "Identifier not defined" somewhere else.
    """
    done = []

    def text_of(key):
        if spec.get(key) is not None:
            return spec[key]
        path = spec.get(key + "_file")
        if path:
            return read_text(path)
        return None

    decl_append = text_of("decl_append")
    decl_replace = text_of("decl_replace")
    body_prepend = text_of("body_prepend")
    body_append = text_of("body_append")
    body_replace = text_of("body_replace")

    # Idempotence. An edit spec gets re-run constantly during a refactor - after a
    # partial apply, after adding one more block - and an append or prepend that
    # has already landed would silently duplicate itself. `skip_if_contains` is a
    # sentinel: if it is already in the target's text, that edit is a no-op.
    # Replacements need no guard, being idempotent by definition.
    sentinel = spec.get("skip_if_contains")
    if sentinel:
        current_decl = safe(lambda: obj.textual_declaration.text, u"") or u""
        current_impl = safe(lambda: obj.textual_implementation.text, u"") or u""
        if sentinel in current_decl:
            decl_append = None
            done.append("decl_append already present")
        if sentinel in current_impl:
            body_prepend = None
            body_append = None
            done.append("body already present")

    if decl_replace is not None:
        obj.textual_declaration.replace(decl_replace)
        done.append("decl_replace")
    elif decl_append is not None:
        obj.textual_declaration.append(u"\n" + decl_append.rstrip() + u"\n")
        done.append("decl_append")

    # Targeted substring replacement, for iterating on code that is ALREADY in the
    # project - where a prepend is blocked by its own sentinel and a full replace
    # would discard the original body. A miss is an error, never a silent no-op:
    # that failure mode is exactly how a refactor quietly half-applies.
    for key, prop in (("replace_in_body", "textual_implementation"),
                      ("replace_in_decl", "textual_declaration")):
        for rule in list(spec.get(key) or []):
            find = rule.get("find")
            with_text = rule.get("with", "")
            if not find:
                raise ValueError("%s needs a 'find'" % key)
            current = getattr(obj, prop).text
            if find not in current:
                if rule.get("optional"):
                    done.append("%s skipped (no match)" % key)
                    continue
                raise ValueError(
                    "%s found no match for %r - the target text has changed"
                    % (key, find[:80])
                )
            # An FB_init argument list in a declaration is a trap. CODESYS keeps an
            # instance's FB_init arguments in a separate "InputAssignments" structure,
            # and the COMPILER READS THAT, not the declaration text. Editing the text
            # updates the text only: the source looks right, the PLCopen export looks
            # right, the build is clean, and the PLC keeps running the old value.
            #
            # Confirmed the hard way - the HVAC valve travel time read T#5S in the
            # declaration and TIME#3m0s0ms in InputAssignments, and the PLC ran 3m.
            # No scripting API reaches InputAssignments, so this cannot be fixed here;
            # it can only be refused to pass in silence.
            if key == "replace_in_decl":
                args = re.compile(r":\s*[\w.]+\s*\(([^)]*)\)")
                old_args = args.search(find)
                new_args = args.search(with_text)
                if old_args and new_args and old_args.group(1).strip() != new_args.group(1).strip():
                    who = spec.get("pou") or "?"
                    note = (
                        u"%s: this changes an FB_init argument list (%s -> %s). The "
                        u"compiler reads InputAssignments, NOT this text, so the PLC "
                        u"will keep the OLD value however clean the build looks. "
                        u"Change it in the IDE, or write the member at runtime."
                        % (who, old_args.group(1).strip(), new_args.group(1).strip())
                    )
                    result.setdefault("advisories", []).append(note)
                    # Loud in the log too: the report is skimmed, the log is read when
                    # something is wrong, and this is the case where nothing LOOKS wrong.
                    log("WARNING %s" % note)
            occurrences = current.count(find)
            expected = rule.get("count")
            if expected is not None and occurrences != int(expected):
                raise ValueError(
                    "%s expected %s occurrence(s) of %r but found %d"
                    % (key, expected, find[:60], occurrences)
                )
            getattr(obj, prop).replace(current.replace(find, with_text))
            done.append("%s x%d" % (key, occurrences))

    if body_replace is not None:
        obj.textual_implementation.replace(body_replace)
        done.append("body_replace")
    else:
        if body_prepend is not None:
            text = body_prepend.rstrip() + u"\n\n"
            # insert() takes the OFFSET FIRST in the .NET binding, the reverse of
            # the shipped .pyi stub - same trap as export_xml/import_xml. Offset 0
            # is the very top of the body.
            try:
                obj.textual_implementation.insert(0, text)
            except TypeError:
                # Fall back to a read-modify-write if the binding disagrees again.
                existing = obj.textual_implementation.text
                obj.textual_implementation.replace(text + existing)
            done.append("body_prepend")
        if body_append is not None:
            obj.textual_implementation.append(u"\n" + body_append.rstrip() + u"\n")
            done.append("body_append")

    return done


def apply_edits(proj, cfg, result):
    """Apply every edit in the spec, in order, to POUs already in the project."""
    specs = cfg.get("edits") or []
    # PowerShell's ConvertTo-Json unwraps a single-element array into a bare
    # object, and iterating a dict would yield its keys as strings. Normalise.
    if isinstance(specs, dict):
        specs = [specs]
    specs = [s for s in list(specs) if isinstance(s, dict)]
    if not specs:
        return
    log("applying %d edit(s)" % len(specs))
    result["edits"] = []
    for spec in specs:
        name = spec.get("pou")
        member = spec.get("member")
        label = name if not member else "%s.%s" % (name, member)
        entry = {"target": u(label), "applied": [], "error": None}
        # delete_pou removes a whole top-level object: a POU, a DUT, or a folder.
        # Deleting a block is the only honest way to retire one - an unreferenced
        # POU still compiles, still exports, and still reads as supported API, so
        # leaving it behind is indistinguishable from keeping it. Nothing else in
        # the spec applies once the object is gone, hence the `continue`.
        if spec.get("delete_pou"):
            victim, problem = find_deletable(proj, name)
            if victim is None:
                # Idempotent, but only for "not there": an ambiguous name is a
                # real error, because removing the wrong object is unrecoverable.
                if problem and problem.startswith("no object named"):
                    entry["applied"].append("%s already absent" % name)
                    log("edit %s: already absent" % label)
                else:
                    entry["error"] = u(problem)
                    result["errors"].append("delete %s: %s" % (label, problem))
                    log("delete %s FAILED: %s" % (label, problem))
            else:
                entry["path"] = u(object_path(victim))
                try:
                    victim.remove()
                    entry["applied"].append("deleted %s" % name)
                    log("edit %s: deleted (%s)" % (label, entry["path"]))
                except Exception:
                    trace = traceback.format_exc()
                    entry["error"] = u(trace)
                    result["errors"].append("delete %s raised: %s" % (label, trace))
                    log("delete %s RAISED:\n%s" % (label, trace))
            result["edits"].append(entry)
            continue
        target, problem = find_editable(proj, name, member, spec.get("path"))
        # create_method/create_action name a member to add to the POU if missing;
        # the decl/body keys of this same edit then apply to that member.
        for kind in ("method", "action", "property"):
            key = "create_" + kind
            if target is not None and spec.get(key):
                try:
                    target, was_created = find_or_create_member(
                        target, kind, spec[key], spec.get("return_type")
                    )
                    entry["target"] = u("%s.%s" % (name, spec[key]))
                    entry["applied"].append("created %s" % kind if was_created else "%s exists" % kind)
                    log("edit %s.%s: %s" % (name, spec[key], entry["applied"][-1]))
                except Exception:
                    problem = traceback.format_exc()
                    target = None
        # delete_member removes a method/action/property from the POU. Needed when a
        # refactor makes one redundant - a Configure* setter replaced by FB_init, say.
        # Leaving a dead setter behind is worse than removing it: it still compiles
        # and still looks like the supported way to configure the block.
        wanted = spec.get("delete_member")
        if target is not None and wanted:
            victim = None
            for child in list(safe(lambda: target.get_children(False), []) or []):
                if safe(lambda: child.get_name(), "") == wanted:
                    victim = child
                    break
            if victim is None:
                # Idempotent: already gone is the desired end state, not an error.
                entry["applied"].append("member %s already absent" % wanted)
                log("edit %s: member %s already absent" % (label, wanted))
            else:
                try:
                    victim.remove()
                    entry["applied"].append("deleted member %s" % wanted)
                    log("edit %s: deleted member %s" % (label, wanted))
                except Exception:
                    problem = traceback.format_exc()
                    target = None

        if target is None:
            entry["error"] = u(problem)
            result["errors"].append("edit %s: %s" % (label, problem))
            log("edit %s FAILED: %s" % (label, problem))
        else:
            entry["path"] = u(object_path(target))
            try:
                # extend, not assign: create_method and delete_member have already
                # recorded what they did, and assigning would drop it from the report.
                entry["applied"].extend(edit_text(target, spec, result))
                log("edit %s: %s" % (label, ", ".join(entry["applied"]) or "nothing"))
            except Exception:
                trace = traceback.format_exc()
                entry["error"] = u(trace)
                result["errors"].append("edit %s raised: %s" % (label, trace))
                log("edit %s RAISED:\n%s" % (label, trace))
        result["edits"].append(entry)


def conflict_resolve(name):
    """Translate a spec string into the ScriptEngine's ConflictResolve enum.

    Only needed for the replace-an-existing-object case; see import_candidates.
    The enum is not one of the globals the ScriptEngine injects, so it has to be
    imported, and the numeric fallback exists because the values are stable
    (Replace=0, Copy=1, Skip=2) and .NET overload resolution accepts the int.
    """
    wanted = {"replace": 0, "copy": 1, "skip": 2}.get(name)
    if wanted is None:
        raise ValueError(
            "import_conflict must be replace, copy or skip - got %r" % name
        )
    try:
        from scriptengine import ConflictResolve  # noqa: F401 - IronPython/.NET
        return [ConflictResolve.Replace, ConflictResolve.Copy, ConflictResolve.Skip][wanted]
    except Exception:
        return wanted


def import_candidates(proj, cfg, result):
    files = candidate_files(cfg.get("candidates"))
    result["candidates"] = files
    log("candidates: %d file(s)" % len(files))
    # By default an import runs through a Reporter, which is what gives the useful
    # "+6 replaced 0 skipped 0" line - but that overload has no say in what happens
    # when the imported object already exists, and the answer turns out to be "add
    # a second one". A candidate that rewrites an existing POU therefore needs
    # import_conflict: "replace" in the spec, and gives up the reporter to get it.
    #
    # Worth knowing why a POU would ever be re-imported rather than edited: an SFC
    # body is not text, so an action association in a chart cannot be reached by
    # replace_in_body. Everything textual should still go through edits.
    mode = (cfg.get("import_conflict") or "").strip().lower()
    resolve = conflict_resolve(mode) if mode else None
    if resolve is not None:
        log("import conflict policy: %s (no reporter on this overload)" % mode)
    # A hand-written candidate holds a bare <pous> list with no folders, so
    # honouring its structure files the object at the project root - hence the
    # default below. A candidate *exported from another project* does carry
    # folders, and then honouring them is exactly right: it is what puts
    # FB_OUTPUT_COVER_MQTT back into BASIC/ instead of at the root, where it
    # would sit beside the real one and never be compiled. The sync sets this.
    folders = bool(cfg.get("import_folders", False))
    log("import folder structure: %s" % folders)
    for path in files:
        if resolve is not None:
            entry = {"file": path, "conflict": mode, "errors": [], "warnings": [],
                     "added": None, "replaced": None, "skipped": None}
            try:
                proj.import_xml(resolve, path, folders)
                log("imported %s with conflict=%s" % (os.path.basename(path), mode))
            except Exception:
                trace = traceback.format_exc()
                entry["errors"].append(trace)
                log("import failed for %s:\n%s" % (path, trace))
                result["errors"].append("import failed for %s: %s" % (path, trace))
            result["imports"].append(entry)
            continue
        reporter = Reporter()
        try:
            # Positional, reporter first (see the `probe` task). The reporter
            # overload has always honoured folders; only the conflict overload
            # needed the flag made explicit.
            proj.import_xml(reporter, path, True)
        except Exception:
            trace = traceback.format_exc()
            log("import failed for %s:\n%s" % (path, trace))
            result["errors"].append("import failed for %s: %s" % (path, trace))
        entry = reporter.as_dict()
        entry["file"] = path
        result["imports"].append(entry)
        result["errors"].extend(["%s: %s" % (os.path.basename(path), e) for e in reporter.errors])
    return files


def do_verify(cfg, result):
    proj = projects.open(cfg["project"])  # noqa: F821 - sandbox copy, opened primary
    try:
        files = import_candidates(proj, cfg, result)
        # Edits run after imports, so a candidate can introduce a type that an
        # edit then refers to.
        apply_edits(proj, cfg, result)
        add_verify_harness(proj, result, files, cfg.get("candidates"))
        build_and_collect(proj, result)
    finally:
        safe(lambda: proj.close())


def clear_precompile_cache(cfg, result):
    """Delete `<name>_project.precompilecache` beside the project, if there is one.

    Returns True when a file was actually removed, so the caller only pays for a
    rebuild when there was something to invalidate. The cache is a build
    accelerator and CODESYS regenerates it, so removing it is safe; it is not
    removed pre-emptively because a full rebuild of a two-controller project costs
    minutes.
    """
    path = cfg.get("project") or ""
    stem, _ = os.path.splitext(path)
    cache = stem + "_project.precompilecache"
    if not os.path.isfile(cache):
        return False
    try:
        os.remove(cache)
        log("removed %s" % cache)
        return True
    except Exception:
        result.setdefault("warnings_local", []).append(
            "could not remove %s: %s" % (cache, traceback.format_exc().strip().split("\n")[-1]))
        return False


def save_if_it_builds(cfg, result, proj, reason):
    """Build, and save only if it builds. True when the project was saved.

    The same guard `apply` and `libs` carry inline: build, and on failure clear
    the precompile cache and build once more, because an in-place build can fail
    citing an identifier the source no longer contains. Refusing to save a
    project that does not build is what makes a wrong guess cost a run rather
    than a project.
    """
    build_and_collect(proj, result)
    blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
    if blocking and not result["errors"] and clear_precompile_cache(cfg, result):
        del result["messages"][:]
        log("build failed; precompile cache cleared, rebuilding once")
        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
        result["precompile_cache_cleared"] = True
    if blocking or result["errors"]:
        result["saved"] = False
        result["errors"].append("project NOT saved: %s" % reason)
        return False
    proj.save()
    result["saved"] = True
    return True


def do_apply(cfg, result):
    proj = projects.open(cfg["project"])  # noqa: F821
    try:
        files = import_candidates(proj, cfg, result)
        apply_edits(proj, cfg, result)
        if not files and not cfg.get("edits"):
            result["errors"].append("nothing to apply: no candidate XML and no edits")
            return
        # No harness here: `apply` writes to the real project, so it must not
        # inject scaffolding. Run `verify` first - that is what checks the code.
        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
        if blocking and not result["errors"] and clear_precompile_cache(cfg, result):
            # `verify` builds a copy alone in .ai/work; `apply` builds the real
            # project, beside CODESYS's <name>_project.precompilecache. That cache
            # can serve a stale compiled interface for a block this very run just
            # re-declared, and the result is an error naming an identifier the
            # source no longer contains - "'Invert' is no valid assignment target"
            # for code already rewritten to RelayType, in a project where the only
            # remaining `Invert` was inside a comment.
            #
            # It is worth a rebuild rather than a warning because the failure is
            # indistinguishable from a real one by reading the messages, and the
            # cost of getting it wrong is abandoning a change that was correct.
            # Only when the build itself failed: a tool error means something else
            # broke, and rebuilding would bury it.
            del result["messages"][:]
            log("build failed; precompile cache cleared, rebuilding once")
            build_and_collect(proj, result)
            blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
            result["precompile_cache_cleared"] = True
            if not blocking:
                log("clean after clearing the cache - the first failure was stale, "
                    "not your edit")
        if blocking or result["errors"]:
            result["saved"] = False
            result["errors"].append("project NOT saved: the imported code does not build")
            return
        proj.save()
        result["saved"] = True
    finally:
        safe(lambda: proj.close())


# ---------------------------------------------------------------- rename


# IEC string literals: single-quoted STRING, double-quoted WSTRING, `$` escapes.
# A rename must never reach inside one. MQTT topics, Home Assistant discovery
# keys and JSON fragments all live in literals, and "fixing" a topic string would
# be invisible here and visible only as a broker going quiet.
LITERAL_RE = re.compile(r"'(?:\$.|[^'\n])*'|\"(?:\$.|[^\"\n])*\"")

# Comments are deliberately NOT protected. A comment still naming MqttVariables
# after the GVL became GVL_MQTT is worse than no comment, because the next reader
# believes it.
TOKEN_RE = re.compile(r"[A-Za-z_]\w*")


def literal_spans(text):
    """Half-open [start, end) ranges of every string literal in `text`."""
    return [(m.start(), m.end()) for m in LITERAL_RE.finditer(text)]


def ctx_member_or_named_arg(text, match):
    """True for `foo.NAME` and for `NAME :=`.

    Those are the two ways one POU reaches another POU's member: qualified access
    through an instance, and a named argument at a call site. An FB's input pin is
    reached through instance names this tool cannot enumerate, so the shape of the
    reference is the only handle there is. Both shapes fail loudly at compile time
    when the guess is wrong, which is what makes them safe to use.
    """
    before = text[max(0, match.start() - 8):match.start()]
    if before.rstrip().endswith(u"."):
        return True
    after = text[match.end():match.end() + 8]
    return after.lstrip().startswith(u":=")


def qualified_context(qualifiers):
    """True only for `Qualifier.NAME`, for one of the given qualifier names.

    Tighter than `ctx_member_or_named_arg` and preferred wherever the qualifier is
    known - a GVL member or an enumeration value is always reached through the
    list or the type, so nothing else can be caught by accident.
    """
    names = [re.escape(u(q)) for q in qualifiers if q]
    if not names:
        return lambda text, match: False
    pattern = re.compile(r"(?:%s)\s*\.\s*$" % u"|".join(names), re.IGNORECASE)

    def ctx(text, match):
        window = text[max(0, match.start() - 80):match.start()]
        return bool(pattern.search(window))

    return ctx


def rewrite_tokens(text, mapping, protect=(), context=None):
    """Rename whole identifiers in `text`, outside string literals.

    Token-walking rather than one alternation regex: word characters include `_`,
    so `MQTT_DISCOVERY_LIGHT_DIMMER` is a single token and a rename of `Dimmer`
    cannot eat half of it, and there is no longest-match-first ordering to get
    wrong. Matching is case-insensitive because IEC is: `PersistentVars` refers to
    `HVACMODES` for a type declared `HvacModes`, and a case-sensitive pass would
    leave that reference dangling and the build broken in a way that reads like a
    missing type.

    Returns (new_text, hits).
    """
    if not text or not mapping:
        return text, 0
    lookup = {}
    for old in mapping:
        lookup[u(old).lower()] = u(mapping[old])
    blocked = set([u(p).lower() for p in (protect or ())])
    spans = literal_spans(text)
    hits = [0]

    def in_literal(index):
        for start, end in spans:
            if start <= index < end:
                return True
            if index < start:
                break
        return False

    def replace(match):
        token = match.group(0)
        key = token.lower()
        if key not in lookup or key in blocked:
            return token
        if in_literal(match.start()):
            return token
        if context is not None and not context(text, match):
            return token
        hits[0] += 1
        return lookup[key]

    return TOKEN_RE.sub(replace, text), hits[0]


# A variable or struct member declaration: `name : TYPE;`, allowing a leading
# pragma. Anchored per line, so `TYPE ST_X :` and `METHOD Foo : BOOL` - which are
# object headers, not declarations - do not match.
DECLARED_RE = re.compile(r"^[ \t]*(?:\{[^}]*\}[ \t]*)?([A-Za-z_]\w*)[ \t]*:", re.MULTILINE)


def declared_variable_names(nodes):
    """Every name declared as a variable or struct member, lowercased.

    Used to catch the one mistake an object rename can make that still compiles.
    `PRG_DALI_VERIFY` declares an instance called `Dimmer`; the enumeration
    `Dimmer` is renamed to `E_DIMMER`. A blind token sweep renames the instance
    too - consistently, in its declaration and at its call site - so the project
    builds and a variable is now called `E_DIMMER`. Nothing downstream would ever
    report it.
    """
    names = {}
    for node in nodes:
        decl = text_of(node, "declaration")
        if not decl:
            continue
        for match in DECLARED_RE.finditer(decl):
            key = match.group(1).lower()
            names.setdefault(key, []).append(object_path(node))
    return names


def text_nodes(proj):
    """Every node in the project, methods and actions included.

    Members own text too, and a rewrite that skipped them would half-land - which
    on a rename is the worst outcome available, because the half that landed
    compiles.
    """
    out = []

    def recurse(node):
        for child in list(safe(lambda: node.get_children(False), []) or []):
            out.append(child)
            recurse(child)

    recurse(proj)
    return out


def rewrite_node(node, mapping, protect, context, dry):
    """Apply one rewrite to a node's declaration and implementation. Returns hits."""
    total = 0
    for which in ("declaration", "implementation"):
        current = text_of(node, which)
        if not current:
            continue
        new_text, hits = rewrite_tokens(current, mapping, protect, context)
        if not hits:
            continue
        total += hits
        if dry:
            continue
        holder = safe(lambda: getattr(node, "textual_" + which), None)
        if holder is None:
            continue
        holder.replace(new_text)
    return total


def sweep(nodes, mapping, protect, context, dry, skip=()):
    """Rewrite every node, reporting where the hits landed.

    The per-object counts are the point, not decoration: a rename that reports
    zero hits outside the declaring object either is not referenced anywhere - fine
    - or is referenced in a form this pass does not recognise, which is the failure
    worth catching before the compiler has to.
    """
    hits = {}
    for node in nodes:
        name = u(safe(lambda: node.get_name(), u"?"))
        if name.lower() in skip:
            continue
        count = rewrite_node(node, mapping, protect, context, dry)
        if count:
            hits[object_path(node)] = hits.get(object_path(node), 0) + count
    return hits


def top_hits(hits, limit=12):
    """The busiest objects, so a report stays readable when 60 files changed."""
    ranked = sorted(hits.items(), key=lambda pair: (-pair[1], pair[0]))
    return [{"object": u(path), "hits": count} for path, count in ranked[:limit]]


def do_rename(cfg, result):
    """Rename objects and identifiers, rewriting every reference to them.

    CODESYS's IDE refactoring is not reachable from the ScriptEngine, so
    `node.rename()` renames an object and updates nothing that refers to it. The
    references are therefore ours to rewrite, which is the whole reason this task
    exists rather than being a loop around `rename()`.

    Two shapes of rename, because they carry different risk:

    - **objects** - a type, block, program or GVL. The name is unique in the
      project, so every occurrence of the token anywhere is that object.
    - **identifiers** - variables inside one declaring object. `mode` decides how
      far the rewrite reaches: `local` stays inside the declaring object,
      `qualified` also rewrites `Owner.name` project-wide (right for GVL members
      and enumeration values), `loose` also rewrites `.name` and `name :=`
      project-wide (the only handle on a function block's pins, whose qualifier is
      an instance name that cannot be enumerated).

    Identifier groups run first, and name their object **as the project spells it
    today** - so one map can rename a variable out of the way of an object about to
    take its name.

    Two failures the compiler cannot catch, both refused rather than risked:

    - **A collision.** Renaming to a name that already exists binds silently to the
      wrong thing, where everything else fails loudly.
    - **A shadow.** An object whose old name is also a variable somewhere gets that
      variable renamed too, consistently enough to compile - see
      `declared_variable_names`. Rename the variable in the same map, or accept it
      explicitly through `allow_shadow`.

    Nothing is written unless the whole map applied and the project still builds,
    which is what makes a wrong map cost a run rather than a project.
    """
    # The map is read here rather than handed over as a converted object:
    # PowerShell's ConvertTo-Json truncates below this structure's depth by
    # default, and a silently truncated map renames half a project.
    spec = cfg.get("rename") or {}
    map_path = cfg.get("rename_map")
    if map_path:
        try:
            spec = json.loads(read_text(map_path))
        except Exception:
            result["errors"].append(
                "could not read the rename map %s:\n%s" % (map_path, traceback.format_exc()))
            return
    if isinstance(spec, list):
        spec = spec[0] if spec else {}
    dry = bool(cfg.get("dry_run"))
    objects_map = dict(spec.get("objects") or {})
    entries = spec.get("identifiers") or []
    if isinstance(entries, dict):
        entries = [entries]
    entries = [e for e in list(entries) if isinstance(e, dict)]
    protect = tuple([u(p) for p in (spec.get("protect") or ())])
    skip = set([u(s).lower() for s in (spec.get("skip_objects") or ())])
    if not objects_map and not entries:
        result["errors"].append(
            "nothing to rename: the map has neither \"objects\" nor \"identifiers\"")
        return

    report = {
        "dry_run": dry,
        "objects": [],
        "identifiers": [],
        "protected": len(protect),
        "skipped_objects": sorted(skip),
    }
    result["renames"] = report
    log("rename: %d object(s), %d identifier group(s)%s"
        % (len(objects_map), len(entries), " (dry run)" if dry else ""))

    proj = projects.open(cfg["project"])  # noqa: F821
    try:
        # 1. Validate every object rename before applying any of them.
        planned = []
        sweep_map = {}
        for old in sorted(objects_map):
            # A value is either the new name, or {"new": ..., "all": true, "path": ...}
            # when one name has to reach more than one object - two applications
            # mean two MqttVariables, and the convention applies to both.
            request = objects_map[old]
            if isinstance(request, dict):
                new = u(request.get("new") or u"")
                want_all = bool(request.get("all"))
                path_filter = request.get("path")
            else:
                new, want_all, path_filter = u(request), False, None
            if not new:
                result["errors"].append("rename %s: no new name given" % old)
                continue
            victims = find_all_editable(proj, old, path_filter)
            if not victims:
                where = " under %r" % path_filter if path_filter else ""
                result["errors"].append(
                    "rename %s: no object of that name owns text%s" % (old, where))
                continue
            if len(victims) > 1 and not want_all:
                result["errors"].append(
                    "rename %s is ambiguous: %s - add \"path\" to pick one, or "
                    "\"all\": true to rename every one of them"
                    % (old, ", ".join([object_path(v) for v in victims])))
                continue
            clash = list(safe(lambda: proj.find(new, True), []) or [])
            if clash:
                result["errors"].append(
                    "rename %s -> %s refused: %s already exists (%s)"
                    % (old, new, new, ", ".join([object_path(c) for c in clash])))
                continue
            sweep_map[old] = new
            for victim in victims:
                planned.append((old, new, victim))
            # A program is called from the task configuration through a nameless
            # twin that owns no code. It has to follow the rename or the task
            # points at nothing.
            for call in find_task_calls(proj, old):
                planned.append((old, new, call))
        if result["errors"]:
            result["errors"].append("nothing was renamed: fix the map and re-run")
            return

        nodes = text_nodes(proj)
        # Read the declared names up front, so the shadow check below behaves the
        # same in a dry run - where no identifier rewrite has actually been
        # written - as in a real one. A group that renames the shadowing variable
        # clears the shadow either way, which is the whole point of running the
        # groups first.
        declared_before = declared_variable_names(nodes)
        cleared = {}

        # 2. Identifier groups, one declaring object at a time. These run BEFORE
        #    the object renames so that a group can rename a variable out of the
        #    way of an object taking its name, in a single run - and so that a
        #    group names its object as it is spelled in the project today rather
        #    than as it will be spelled afterwards.
        for group in entries:
            name = u(group.get("object") or u"")
            mapping = dict(group.get("map") or {})
            mode = u(group.get("mode") or u"local").lower()
            if not name or not mapping:
                result["errors"].append(
                    "identifier group needs \"object\" and a non-empty \"map\": %r" % group)
                continue
            owner, problem = find_editable(proj, name, None, group.get("path"))
            if owner is None:
                result["errors"].append("rename in %s: %s" % (name, problem))
                continue
            # Members of the declaring object are part of its scope: a method's
            # body references the block's variables, so the local pass has to
            # include them.
            family = [owner] + list(safe(lambda: owner.get_children(False), []) or [])
            local = sweep(family, mapping, protect, None, dry)
            # Whatever this group renamed is no longer available to shadow an
            # object taking the same name.
            family_paths = set([object_path(n) for n in family])
            for old_name in mapping:
                key = u(old_name).lower()
                cleared.setdefault(key, set()).update(family_paths)
            entry = {
                "object": u(object_path(owner)),
                "mode": mode,
                "names": len(mapping),
                "local_hits": sum(local.values()),
                "cross_hits": 0,
            }
            if mode in ("qualified", "loose"):
                # In a dry run the text still carries the old object name, so
                # accept either spelling as the qualifier rather than reporting a
                # confident zero.
                aliases = [name] + [o for o in sweep_map if sweep_map[o] == name]
                context = (qualified_context(aliases) if mode == "qualified"
                           else ctx_member_or_named_arg)
                elsewhere = [n for n in nodes if n not in family]
                cross = sweep(elsewhere, mapping, protect, context, dry, skip)
                entry["cross_hits"] = sum(cross.values())
                entry["cross_top"] = top_hits(cross)
            elif mode != "local":
                result["errors"].append(
                    "unknown mode %r for %s: use local, qualified or loose" % (mode, name))
                continue
            report["identifiers"].append(entry)
            log("rename in %s: %d name(s), %d local, %d elsewhere (%s)"
                % (name, len(mapping), entry["local_hits"], entry["cross_hits"], mode))

        # 3. Refuse an object rename whose old name is also a variable somewhere.
        #    See declared_variable_names: this is the failure that compiles.
        if planned:
            allowed = set([u(a).lower() for a in (spec.get("allow_shadow") or ())])
            for old, new, victim in planned:
                key = u(old).lower()
                remaining = set(declared_before.get(key, [])) - cleared.get(key, set())
                if remaining and key not in allowed:
                    result["errors"].append(
                        "rename %s -> %s refused: %s is also declared as a variable in %s. "
                        "Rename that variable in the same map (an \"identifiers\" group), or "
                        "list %s in \"allow_shadow\" to rewrite both."
                        % (old, new, old, ", ".join(sorted(remaining)[:4]), old))
            if result["errors"]:
                result["errors"].append("nothing was saved: fix the map and re-run")
                return

        # 4. Rename the objects themselves, then rewrite every reference. Object
        #    names are project-unique, so no context filter is wanted here: a type
        #    used only inside an otherwise-exempt struct still has to follow it.
        for old, new, victim in planned:
            entry = {
                "old": u(old),
                "new": u(new),
                "path": u(object_path(victim)),
                "task_call": str(safe(lambda: victim.type, u"")).startswith(TASK_CALL_TYPE),
            }
            if not dry:
                try:
                    victim.rename(new)
                except Exception:
                    trace = traceback.format_exc()
                    result["errors"].append("renaming %s to %s failed:\n%s" % (old, new, trace))
                    log("rename %s FAILED:\n%s" % (old, trace))
                    return
            report["objects"].append(entry)
            log("rename object: %s -> %s" % (old, new))

        if sweep_map:
            hits = sweep(nodes, sweep_map, protect, None, dry)
            total = sum(hits.values())
            report["object_references"] = {"total": total, "top": top_hits(hits)}
            log("rename: rewrote %d object reference(s) across %d object(s)"
                % (total, len(hits)))

        if dry:
            log("dry run: nothing written, nothing built")
            return
        if result["errors"]:
            result["errors"].append(
                "project NOT saved: the rename map was only partly applicable")
            return
        save_if_it_builds(cfg, result, proj, "the renamed project does not build")
    finally:
        safe(lambda: proj.close())


def do_probe(cfg, result):
    """Dump real .NET signatures for the API calls we depend on.

    The .pyi stubs shipped with CODESYS document keyword names that the .NET
    binding does not always accept, and overload resolution decides the
    positional order. This is how to settle such a question in one run instead
    of guessing across several 80-second round trips.
    """
    proj = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    try:
        sigs = {}
        for name in ("export_xml", "import_xml", "export_native", "import_native"):
            member = getattr(proj, name, None)
            sigs[name] = safe(lambda: str(member.__doc__), "<no doc>")
        app = None
        for child in list(safe(lambda: proj.get_children(True), []) or []):
            if safe(lambda: child.is_application, False):
                app = child
                break
        if app is not None:
            for name in ("build", "generate_code"):
                member = getattr(app, name, None)
                sigs["application." + name] = safe(lambda: str(member.__doc__), "<no doc>")
            # Everything the object really exposes, because the stubs document a
            # subset. This is how an application setting with no documented
            # accessor gets found - or ruled out.
            result["members"] = {
                "application": sorted([u(n) for n in dir(app) if not n.startswith("_")]),
                "project": sorted([u(n) for n in dir(proj) if not n.startswith("_")]),
            }
        result["signatures"] = sigs
    finally:
        safe(lambda: proj.close())


def top_level_devices(proj):
    """Device nodes directly under the project, i.e. the PLCs themselves.

    The fieldbus modules under Pfc200Bus are also devices, but simulation is a
    property of the controller, not of a 750-series terminal.
    """
    found = []
    for child in list(safe(lambda: proj.get_children(False), []) or []):
        if safe(lambda: child.is_device, False):
            found.append(child)
    return found


def run_steps(online_app, steps, result):
    """Execute a test spec against the running application.

    Steps are applied in order; a step may combine keys. Values are strings on
    both sides of the wire, which is what the scripting API deals in.

        {"write": {"expr": "TRUE"}}   prepare + write values
        {"delay_ms": 500}             let the PLC run some cycles
        {"read": ["expr"]}            record a value
        {"expect": {"expr": "100"}}   record and assert
    """
    outcomes = []
    for index, step in enumerate(steps):
        entry = {"index": index, "values": {}, "failures": []}
        if step.get("label"):
            entry["label"] = u(step["label"])
        try:
            writes = step.get("write") or {}
            for expr in sorted(writes.keys()):
                online_app.set_prepared_value(expr, u(writes[expr]))
            if writes:
                online_app.write_prepared_values()
                entry["wrote"] = sorted(writes.keys())

            if step.get("delay_ms"):
                system.delay(int(step["delay_ms"]))  # noqa: F821

            for expr in list(step.get("read") or []):
                entry["values"][u(expr)] = u(online_app.read_value(expr))

            expects = step.get("expect") or {}
            for expr in sorted(expects.keys()):
                actual = u(online_app.read_value(expr))
                entry["values"][u(expr)] = actual
                expected = u(expects[expr])
                if (actual or u"").strip() != (expected or u"").strip():
                    failure = u"%s: expected %s, got %s" % (expr, expected, actual)
                    entry["failures"].append(failure)
                    result["test_failures"].append(failure)
        except Exception:
            trace = traceback.format_exc()
            log("step %d failed:\n%s" % (index, trace))
            entry["failures"].append(u("step raised: %s" % trace))
            result["test_failures"].append(u("step %d raised: %s" % (index, trace)))
        outcomes.append(entry)
    return outcomes


def do_simulate(cfg, result):
    """Download to a simulated PLC, start it, and run a test spec.

    Simulation is switched on in the project, which is why the wrapper only ever
    points this at a throwaway copy: leaving the real project in simulation mode
    would silently retarget the next GUI download away from the PLC.
    """
    online_info = {}
    result["online"] = online_info
    proj = projects.open(cfg["project"])  # noqa: F821 - sandbox copy
    online_app = None
    try:
        files = import_candidates(proj, cfg, result)
        add_verify_harness(proj, result, files, cfg.get("candidates"))

        devices = top_level_devices(proj)
        if not devices:
            result["errors"].append("no top-level device found to simulate")
            return
        for device in devices:
            device.set_simulation_mode(True)
            log("simulation enabled on %s" % object_path(device))
        online_info["simulated_devices"] = [u(object_path(d)) for d in devices]

        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
        if blocking:
            result["errors"].append("not going online: the application does not build")
            return

        apps = [c for c in list(safe(lambda: proj.get_children(True), []) or [])
                if safe(lambda: c.is_application, False)]
        if not apps:
            result["errors"].append("no application to go online with")
            return

        log("creating online application ...")
        online_app = online.create_online_application(apps[0])  # noqa: F821
        # Never: force a full download rather than an online change, so the run
        # always starts from a known state.
        log("login (full download) ...")
        online_app.login(OnlineChangeOption.Never, True)  # noqa: F821
        online_info["logged_in"] = bool(safe(lambda: online_app.is_logged_in, False))
        log("logged_in=%s" % online_info["logged_in"])

        log("start ...")
        online_app.start()
        settle = int(cfg.get("settle_ms") or 1000)
        system.delay(settle)  # noqa: F821

        online_info["application_state"] = u(safe(lambda: online_app.application_state))
        operating = safe(lambda: online_app.operation_state)
        online_info["operation_state"] = u(operating)
        log("state=%s operating=%s" % (online_info["application_state"], online_info["operation_state"]))

        # An application that faulted reports success on login and start, so the
        # exception flag has to be checked explicitly.
        if "exception" in (online_info["operation_state"] or u"").lower():
            result["test_failures"].append(
                u"the application stopped on an exception in simulation "
                u"(operation_state=%s)" % online_info["operation_state"]
            )

        steps = list(cfg.get("steps") or [])
        if steps:
            log("running %d step(s) ..." % len(steps))
            online_info["steps"] = run_steps(online_app, steps, result)
    except Exception:
        trace = traceback.format_exc()
        log("simulate failed:\n%s" % trace)
        result["errors"].append(trace)
    finally:
        if online_app is not None:
            safe(lambda: online_app.stop())
            safe(lambda: online_app.logout())
            # Holding the connection open has side effects; the stub is explicit
            # about disposing it rather than waiting for script exit.
            safe(lambda: online_app.Dispose())
            log("stopped, logged out, disposed")
        safe(lambda: proj.close())


def do_scan(cfg, result):
    """List PLCs reachable on each configured gateway.

    This is the tool for "the download said no connection": it shows what is
    actually answering, and the address to point the device at. Needs no project.
    """
    scans = []
    for gateway in list(safe(lambda: online.gateways, []) or []):  # noqa: F821
        entry = {"gateway": u(safe(lambda: gateway.name)), "devices": []}
        log("scanning %s ..." % entry["gateway"])
        results = safe(lambda: gateway.perform_network_scan())
        if not results:
            log("live scan empty, falling back to the cached result")
            entry["cached"] = True
            results = safe(lambda: gateway.get_cached_network_scan_result(), [])
        for found in list(results or []):
            entry["devices"].append(
                {
                    "name": u(safe(lambda: found.device_name)),
                    "address": u(safe(lambda: found.address)),
                    "type": u(safe(lambda: found.type_name)),
                    "vendor": u(safe(lambda: found.vendor_name)),
                    "target_id": u(safe(lambda: found.device_id)),
                }
            )
        log("%s: %d device(s)" % (entry["gateway"], len(entry["devices"])))
        scans.append(entry)
    result["scan"] = scans


def do_download(cfg, result):
    """Download the real project to the real PLC and (by default) start it.

    Unlike `simulate` this runs against src/HomeAutomation.project, because the
    point is to ship what the project actually contains. It never saves the
    project, and it refuses to run if the device is in simulation mode — that
    would mean downloading into a simulated PLC while reporting success.
    """
    online_info = {}
    result["online"] = online_info
    proj = projects.open(cfg["project"])  # noqa: F821
    online_app = None
    try:
        devices = top_level_devices(proj)
        if not devices:
            result["errors"].append("no top-level device found to download to")
            return
        device = devices[0]
        online_info["device"] = u(object_path(device))
        online_info["gateway"] = u(safe(lambda: device.get_gateway()))
        online_info["address"] = u(safe(lambda: device.get_address()))
        simulated = bool(safe(lambda: device.get_simulation_mode(), False))
        online_info["simulation"] = simulated
        log("target=%s gateway=%s address=%s simulation=%s" % (
            online_info["device"], online_info["gateway"], online_info["address"], simulated))
        if simulated:
            result["errors"].append(
                "device is in simulation mode; refusing to download. "
                "Clear simulation in the project first."
            )
            return

        # Optional run-scoped retarget. The project is never saved, so this does
        # not change the committed communication settings. `address` takes a
        # gateway node address as reported by the `scan` task (e.g. 003E); `ip`
        # takes an IP and lets the gateway resolve the node itself.
        ip = cfg.get("ip")
        node = cfg.get("address")
        if ip or node:
            gateway_id = safe(lambda: device.get_gateway())
            if node:
                log("retargeting to node %s via gateway %s (this run only)" % (node, gateway_id))
                device.set_gateway_and_address(gateway_id, node)
                online_info["retargeted_to"] = u(node)
            else:
                log("retargeting to %s via gateway %s (this run only)" % (ip, gateway_id))
                #                                gateway,    ip, port
                device.set_gateway_and_ip_address(gateway_id, ip, 11740)
                online_info["retargeted_to"] = u(ip)
            online_info["address"] = u(safe(lambda: device.get_address()))

        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
        if blocking:
            result["errors"].append("not downloading: the application does not build")
            return

        apps = [c for c in list(safe(lambda: proj.get_children(True), []) or [])
                if safe(lambda: c.is_application, False)]
        if not apps:
            result["errors"].append("no application to download")
            return

        # Credentials come from the environment via the wrapper, never from a
        # committed file. Without them we fall back to whatever CODESYS has
        # cached for this device from earlier interactive use.
        username = cfg.get("plc_user") or ""
        if username:
            log("using supplied device credentials for %s" % username)
            online.set_default_credentials(username, cfg.get("plc_password") or "")  # noqa: F821
            online_info["credentials"] = "supplied"
        else:
            log("no credentials supplied; relying on CODESYS's cached device login")
            online_info["credentials"] = "cached-or-none"

        online_app = online.create_online_application(apps[0])  # noqa: F821
        # Never: a full download, not an online change, so the PLC ends up
        # running exactly this project rather than a patched version of whatever
        # was there before.
        log("login (full download) ...")
        try:
            online_app.login(OnlineChangeOption.Never, True)  # noqa: F821
        except Exception:
            trace = traceback.format_exc()
            log("login failed:\n%s" % trace)
            lowered = trace.lower()
            if "no connection" in lowered or "rescan" in lowered:
                # By far the most likely failure, and not a code problem.
                result["errors"].append(
                    "the PLC did not answer at gateway %s address %s. Check that it is "
                    "powered and reachable on this network, run the `scan` task to see "
                    "what is answering, and pass -Ip <address> if it moved."
                    % (online_info["gateway"], online_info["address"])
                )
            elif "credential" in lowered or "authent" in lowered or "user" in lowered:
                result["errors"].append(
                    "the PLC refused the login. Set $env:PLC_USER and $env:PLC_PASS "
                    "to its device credentials. Original error:\n%s" % trace
                )
            else:
                result["errors"].append(trace)
            return
        online_info["logged_in"] = bool(safe(lambda: online_app.is_logged_in, False))
        log("logged_in=%s" % online_info["logged_in"])
        if not online_info["logged_in"]:
            result["errors"].append("login reported success but the application is not logged in")
            return

        # A cold reset before starting, so what runs is unambiguously the code just
        # downloaded, initialised from scratch.
        #
        # login(OnlineChangeOption.Never, ...) is documented as forcing a full
        # download, and yet a change to an FB_init argument was observed NOT taking
        # effect: the HVAC valve travel time was T#5S in the source and in the
        # export, the build was clean, and the running PLC still reported the old
        # TIME#3m afterwards. New code, old instance data. Whatever the cause, the
        # failure mode is the dangerous one - an FB_init change that looks applied
        # everywhere except on the PLC - so do not rely on the download to
        # re-initialise. Ask for it.
        #
        # Cold, not Warm: warm keeps retain variables, and FB_init's whole job is
        # assigning them. Cold KEEPS persistent variables (only reset_origin clears
        # those), so the thermostat setpoints and the cover's direction in
        # PersistentVars survive this - which is what we want, since losing them
        # would change behaviour rather than just re-initialise it.
        if cfg.get("cold_reset", True):
            log("cold reset (re-runs FB_init; keeps PERSISTENT, clears RETAIN) ...")
            try:
                online_app.reset(ResetOption.Cold, True)  # noqa: F821
                online_info["cold_reset"] = True
            except Exception:
                trace = traceback.format_exc()
                online_info["cold_reset"] = False
                # Not fatal on its own, but it must not pass silently: without the
                # reset an FB_init value on the PLC may be stale, and that is
                # exactly what this exists to prevent.
                result["errors"].append("cold reset failed, FB_init values may be stale: %s" % trace)
                log("cold reset FAILED:\n%s" % trace)
        else:
            online_info["cold_reset"] = False

        # After the reset, so the boot application is the initialised one.
        if cfg.get("boot_application"):
            log("creating boot application (survives a power cycle) ...")
            online_app.create_boot_application()
            online_info["boot_application"] = True

        if cfg.get("start", True):
            log("start ...")
            online_app.start()
            system.delay(int(cfg.get("settle_ms") or 1500))  # noqa: F821
            online_info["started"] = True
        else:
            online_info["started"] = False

        online_info["application_state"] = u(safe(lambda: online_app.application_state))
        online_info["operation_state"] = u(safe(lambda: online_app.operation_state))
        log("state=%s operating=%s" % (
            online_info["application_state"], online_info["operation_state"]))

        if "exception" in (online_info["operation_state"] or u"").lower():
            result["test_failures"].append(
                u"the PLC stopped on an exception after download "
                u"(operation_state=%s)" % online_info["operation_state"]
            )
        elif online_info["started"] and "run" not in (online_info["application_state"] or u"").lower():
            result["test_failures"].append(
                u"application is not running after start (state=%s)"
                % online_info["application_state"]
            )

        steps = list(cfg.get("steps") or [])
        if steps:
            log("running %d step(s) against the PLC ..." % len(steps))
            online_info["steps"] = run_steps(online_app, steps, result)
    except Exception:
        trace = traceback.format_exc()
        log("download failed:\n%s" % trace)
        result["errors"].append(trace)
    finally:
        if online_app is not None:
            # Deliberately no stop(): the PLC is meant to keep running the
            # application after we disconnect. Only the connection is closed.
            safe(lambda: online_app.logout())
            safe(lambda: online_app.Dispose())
            log("logged out, disposed (PLC left running)")
        # Never save: downloading must not rewrite the project binary.
        safe(lambda: proj.close())


def resolve_node(result, proj, needle):
    """The one device node matching `needle`, or None with an error recorded.

    An exact name wins outright, and only then does a path substring get a say.
    Without that precedence "Pfc200Bus" matches the bus AND every module already
    on it, because a child's path contains its parent's name - so the obvious
    query is refused as ambiguous by its own children.
    """
    needle = u(needle or u"").lower()
    exact, loose = [], []
    for node in list(safe(lambda: proj.get_children(True), []) or []):
        if not safe(lambda: node.is_device, False):
            continue
        if needle == u(safe(lambda: node.get_name(), u"")).lower():
            exact.append(node)
        elif needle in object_path(node).lower():
            loose.append(node)
    hits = exact or loose
    if not hits:
        result["errors"].append("no device node matches %r" % needle)
        return None
    if len(hits) > 1:
        # Same reasoning as an ambiguous POU edit: a coin flip over which bus
        # gets a new device is worse than a refusal.
        result["errors"].append(
            "%r matches %d device nodes (%s) - be more specific"
            % (needle, len(hits), ", ".join(object_path(h) for h in hits)))
        return None
    return hits[0]


def add_device(cfg, result, proj):
    """Add a device by its full identification: "type:id:version[:moduleid]".

    Unlike a module, a device carries its own identification, so it has to be
    given. Read it from the device description - `<DeviceIdentification>` in
    `C:\\ProgramData\\CODESYS\\Devices\\<type>\\<id>\\<version>\\device.xml`,
    which is also where the folder layout spells it out.

    With no parent the device is added at the project root, which is what makes
    a second controller possible: a project can hold several, and one that is
    never downloaded still gets compiled.

    Returns True when a device was added.
    """
    spec = u(cfg.get("device_add") or u"")
    parts = [p.strip() for p in spec.split(":")]
    if len(parts) < 3:
        result["errors"].append(
            "device_add wants \"type:id:version\" (optionally \":moduleid\"), got %r" % spec)
        return False
    try:
        dev_type = int(parts[0])
    except ValueError:
        result["errors"].append("device type %r is not a number" % parts[0])
        return False
    dev_id, dev_version = parts[1], parts[2]
    module_id = parts[3] if len(parts) > 3 else None
    name = u(cfg.get("node_name") or u"")
    if not name:
        result["errors"].append("device_add needs node_name: what to call the new device")
        return False

    needle = u(cfg.get("node_under") or u"")
    if needle:
        parent = resolve_node(result, proj, needle)
        if parent is None:
            return False
        where = object_path(parent)
    else:
        parent = proj
        where = u"the project root"

    try:
        if module_id:
            parent.add(name, dev_type, dev_id, dev_version, module_id)
        else:
            parent.add(name, dev_type, dev_id, dev_version)
    except Exception:
        trace = traceback.format_exc()
        result["errors"].append(
            "adding device %s under %s failed:\n%s" % (spec, where, trace))
        log("add_device failed:\n%s" % trace)
        return False

    change = u"added %s (%s) under %s" % (name, spec, where)
    result.setdefault("device_changes", []).append(change)
    log(change)
    return True


def rename_node(cfg, result, proj):
    """Rename a device or module node.

    Worth knowing what a device's name reaches: the object paths in every
    compiler message, and so the object paths recorded in a baseline. Rename a
    device and the next `verify` reads its unchanged warnings as NEW until the
    baseline is re-recorded.

    This renames a node in the DEVICE tree. For a POU, DUT, GVL or program, use
    the `rename` task instead - it rewrites the references too, which this does
    not, and it knows that a program's name is also the prefix of every persistent
    instance path in the persistent variable list.

    Returns True when a node was renamed.
    """
    node = resolve_node(result, proj, cfg.get("node_rename"))
    if node is None:
        return False
    new_name = u(cfg.get("node_name") or u"")
    if not new_name:
        result["errors"].append("node_rename needs node_name: what to rename it to")
        return False
    old_path = object_path(node)
    try:
        node.rename(new_name)
    except Exception:
        trace = traceback.format_exc()
        result["errors"].append("renaming %s to %r failed:\n%s" % (old_path, new_name, trace))
        log("rename_node failed:\n%s" % trace)
        return False
    change = u"renamed %s to %s" % (old_path, new_name)
    result.setdefault("device_changes", []).append(change)
    log(change)
    return True


def remove_node(cfg, result, proj):
    """Unplug a device or module from the device tree, by node name.

    The counterpart to adding one, and the reason the guard matters: removing a
    module changes what the runtime expects on its bus, so the build has to be
    re-run before this can be saved.

    Returns True when a node was removed.
    """
    node = resolve_node(result, proj, cfg.get("node_remove"))
    if node is None:
        return False
    path = object_path(node)
    try:
        node.remove()
    except Exception:
        trace = traceback.format_exc()
        result["errors"].append("removing %s failed:\n%s" % (path, trace))
        log("remove_node failed:\n%s" % trace)
        return False
    change = u"removed %s" % path
    result.setdefault("device_changes", []).append(change)
    log(change)
    return True


def add_module(cfg, result, proj):
    """Plug a module into a node of the device tree, by ModuleId.

    A module is not identified the way a device is. Its parent's device
    description carries every module that description can hold, and `add` takes
    the PARENT's (type, id, version) plus the module's own ModuleId - which is
    why every module already under `Pfc200Bus` reports the bus's own
    identification ("288", "0000 0001", "4.19.0.0") and differs only in name.
    So the identification is read off the parent rather than asked for: there is
    exactly one right answer and it is already in the project.

    Returns True when a module was added.
    """
    module_id = u(cfg.get("module_add") or u"")
    needle = u(cfg.get("node_under") or u"")
    name = u(cfg.get("node_name") or u"")
    if not needle:
        result["errors"].append("module_add needs node_under: which node to plug it into")
        return False

    parent = resolve_node(result, proj, needle)
    if parent is None:
        return False
    ident = safe(lambda: parent.get_device_identification(), None)
    if ident is None:
        result["errors"].append("cannot read the device identification of %s" % object_path(parent))
        return False
    dev_type = safe(lambda: int(str(ident.type)), None)
    dev_id = u(safe(lambda: str(ident.id), u""))
    dev_version = u(safe(lambda: str(ident.version), u""))
    if dev_type is None or not dev_id:
        result["errors"].append("incomplete device identification on %s" % object_path(parent))
        return False

    if not name:
        # CODESYS's own default instance name for these is the order number with
        # the leading digit dropped and dots turned into underscores; the modules
        # already in this project are named _75x_440 and the like. Deriving it
        # from the ModuleId keeps a scripted module indistinguishable from one
        # added in the IDE.
        name = u"_" + module_id.split("_", 1)[-1] if "_" in module_id else module_id

    # `add` appends, and on a K-bus the tree order IS the physical order: the
    # driver hands the process image out in the order the terminals sit on the
    # rail, so a module in the wrong slot of the tree reads its neighbour's
    # words. A terminal added anywhere but at the end of the rail therefore has
    # to be INSERTED, and `insert` takes the index second - name, index, then the
    # same identification `add` takes.
    #
    # The stub documents `insert(name, index, type, id, version, module)` and that
    # call is ACCEPTED AND IGNORED: two terminals asked for index 4 and 5 both
    # landed at the end of the bus. Since the .pyi is known to have the argument
    # order backwards elsewhere (`textual_implementation.insert` really takes the
    # offset first), index-first is tried first here and the documented order is
    # the fallback. Either way the achieved position is read back below, because
    # an insert that quietly appends is the whole reason this exists.
    index = cfg.get("node_index")
    try:
        if index is None:
            parent.add(name, dev_type, dev_id, dev_version, module_id)
        else:
            try:
                parent.insert(int(index), name, dev_type, dev_id, dev_version, module_id)
                log("insert: index-first argument order accepted")
            except Exception:
                parent.insert(name, int(index), dev_type, dev_id, dev_version, module_id)
                log("insert: index-first refused, used the documented name-first order")
    except Exception:
        trace = traceback.format_exc()
        result["errors"].append(
            "adding module %r under %s failed:\n%s" % (module_id, object_path(parent), trace))
        log("add_module failed:\n%s" % trace)
        return False

    # Read the position back - but do not believe it means rail position. See the
    # advisory below: `get_children` returns CREATION order, which is not the bus
    # order the IDE shows and not something a script can change.
    siblings = [u(safe(lambda: c.get_name(), u""))
                for c in list(safe(lambda: parent.get_children(False), []) or [])]
    landed = siblings.index(name) if name in siblings else None
    where = object_path(parent)
    if landed is not None:
        where = "%s at creation index %d of %d" % (where, landed, len(siblings))
    change = u"added %s (module %s) under %s" % (name, module_id, where)
    result.setdefault("device_changes", []).append(change)
    log(change)
    result.setdefault("device_order", {})[u(object_path(parent))] = siblings
    if index is not None:
        # Established the hard way: `insert` accepts an index and appends, and
        # removing a terminal and re-adding it does not move it either - the saved
        # project comes back in exactly the order it went in. So a script can add a
        # terminal but cannot place it, and cannot even read where it sits on the
        # rail. Refusing the save was worse than useless here: it blocked a correct
        # project because a number that means something else did not match.
        note = (u"%s: a script cannot position a module on a bus. `insert` ignores "
                u"the index, remove-and-re-add does not move it, and the order "
                u"reported here is CREATION order, not the order the IDE shows or "
                u"the rail carries. If this terminal is not at the far right of the "
                u"rail, check and fix the position in the IDE." % name)
        result.setdefault("advisories", []).append(note)
        log("ADVISORY %s" % note)
    return True


def channel_parameters(node):
    """Every mappable I/O channel of a device node, keyed by its visible name.

    A terminal's channels are not on the node itself but on its child connector's
    host parameter set - which is why the export shows them under
    <Connector role="child"><HostParameterSet>. `device_parameters` holds the
    node's own settings and carries no channels for a 750-series terminal, so both
    are walked and only the parameters answering `is_mappable_io` are kept.
    """
    found = {}
    sets = []
    for connector in list(safe(lambda: node.connectors, []) or []):
        sets.append(safe(lambda: connector.host_parameters, None))
    sets.append(safe(lambda: node.device_parameters, None))
    for pset in sets:
        if pset is None:
            continue
        for param in list(safe(lambda: list(pset), []) or []):
            if not safe(lambda: bool(param.is_mappable_io), False):
                continue
            name = u(safe(lambda: param.name, u"")) or u(safe(lambda: param.visible_name, u""))
            if name:
                found[name] = param
    return found


def map_io(cfg, result, proj):
    """Give a device's I/O channels IEC variable names.

    Mapping a channel is a double-click per channel in the IDE, and it is what
    makes a freshly added terminal usable at all: until it has a name, no IEC code
    can read it. `ScriptIoMapping.variable` does it from a script - an unqualified
    name creates the variable, which is exactly what the IDE's mapping editor does
    when you type one in.

    Each rule is {node, channel, variable}. A channel that does not exist is an
    error rather than a skip: a mistyped channel name would otherwise leave a
    terminal silently unmapped, and the build would fail later and elsewhere.

    Returns True when at least one mapping was written.
    """
    rules = list(cfg.get("map_io") or [])
    if not rules:
        return False
    wrote = 0
    for rule in rules:
        needle = u(rule.get("node") or u"")
        channel = u(rule.get("channel") or u"")
        variable = u(rule.get("variable") or u"")
        if not (needle and channel and variable):
            result["errors"].append(
                "map_io rule needs node, channel and variable: %r" % (rule,))
            continue
        node = resolve_node(result, proj, needle)
        if node is None:
            continue
        channels = channel_parameters(node)
        param = channels.get(channel)
        if param is None:
            result["errors"].append(
                "%s has no mappable channel %r - it has %s"
                % (object_path(node), channel, ", ".join(sorted(channels)) or "none"))
            continue
        mapping = safe(lambda: param.io_mapping, None)
        if mapping is None:
            result["errors"].append(
                "channel %r on %s exposes no io_mapping" % (channel, object_path(node)))
            continue
        try:
            mapping.variable = variable
        except Exception:
            trace = traceback.format_exc()
            result["errors"].append(
                "mapping %r on %s to %r failed:\n%s"
                % (channel, object_path(node), variable, trace))
            log("map_io failed:\n%s" % trace)
            continue
        # The setter takes anything that parses as an IEC expression, so reading
        # it back is the only confirmation that it landed as asked.
        readback = u(safe(lambda: param.io_mapping.variable, u""))
        entry = u"mapped %s / %s -> %s" % (object_path(node), channel, readback or variable)
        result.setdefault("device_changes", []).append(entry)
        log(entry)
        if readback != variable:
            result["errors"].append(
                "mapping %r on %s reads back as %r, not %r"
                % (channel, object_path(node), readback, variable))
        wrote += 1
    return wrote > 0


def do_device(cfg, result):
    """Report the configured communication target, without connecting to it.

    Answers "could this project be downloaded from here?" — which gateway and
    address the device node points at, and whether simulation is switched on —
    while making no attempt to reach the PLC.

    With `module_add` or `device_add` it also writes: something is plugged into
    the device tree, and then it behaves like `libs` and `apply` - build first,
    refuse to save a project that does not build.
    """
    mutating = bool(cfg.get("module_add") or cfg.get("device_add")
                    or cfg.get("node_remove") or cfg.get("node_rename")
                    or cfg.get("map_io"))
    proj = projects.open(cfg["project"], allow_readonly=not mutating)  # noqa: F821
    try:
        if cfg.get("node_rename"):
            if not rename_node(cfg, result, proj):
                return
        if cfg.get("node_remove"):
            if not remove_node(cfg, result, proj):
                return
        if cfg.get("device_add"):
            if not add_device(cfg, result, proj):
                return
        if cfg.get("module_add"):
            if not add_module(cfg, result, proj):
                return
        if cfg.get("map_io"):
            # After any add, so one run can plug a terminal in and name its
            # channels - which is the whole job, and neither half is any use
            # alone: an unmapped channel has no name for IEC code to read.
            if not map_io(cfg, result, proj):
                return
        devices = []
        for node in list(safe(lambda: proj.get_children(True), []) or []):
            if not safe(lambda: node.is_device, False):
                continue
            devices.append(
                {
                    "path": u(object_path(node)),
                    "gateway": u(safe(lambda: node.get_gateway())),
                    "address": u(safe(lambda: node.get_address())),
                    "simulation": safe(lambda: bool(node.get_simulation_mode())),
                }
            )
        result["devices"] = devices
        # Sibling order per node, which is CREATION order and NOT the order of
        # terminals on the rail. Both were confused for each other once, at the cost
        # of an afternoon: the IDE showed three RTD modules side by side while this
        # list and the PLCopen export both reported them split apart, and two
        # remove-and-re-add rounds could not change what either said. Report it
        # because it is the only order a script can see; do not conclude a bus is
        # misordered from it.
        order = {}
        for node in [None] + [n for n in list(safe(lambda: proj.get_children(True), []) or [])
                              if safe(lambda: n.is_device, False)]:
            if node is None:
                continue
            kids = [u(safe(lambda: c.get_name(), u""))
                    for c in list(safe(lambda: node.get_children(False), []) or [])
                    if safe(lambda: c.is_device, False)]
            if kids:
                order[u(object_path(node))] = kids
        result["device_order"] = order
        for where in sorted(order):
            log("order %s: %s" % (where, ", ".join(order[where])))
        gateways = []
        for gateway in list(safe(lambda: online.gateways, []) or []):  # noqa: F821
            gateways.append(
                {
                    "name": u(safe(lambda: gateway.name)),
                    "id": u(safe(lambda: gateway.gatewayid)),
                }
            )
        result["gateways"] = gateways
        log("devices=%d gateways=%d" % (len(devices), len(gateways)))
        if mutating:
            save_if_it_builds(cfg, result, proj,
                              "it does not build with this device tree")
    finally:
        safe(lambda: proj.close())


# ------------------------------------------------------------------ scaffold
#
# Adding a device gets you `Plc Logic/Application` with a Library Manager and
# nothing else - no program, no task configuration - so an application created
# from a script cannot compile anything yet. These three creations are what turn
# it into one that does, and they are the reason a second controller is a useful
# thing to be able to add: a program in an application no task calls is not
# compiled, and neither is a POU no application references.


def find_application(result, proj, needle):
    """The one application whose path contains `needle`."""
    needle = u(needle or u"").lower()
    hits = []
    for node in list(safe(lambda: proj.get_children(True), []) or []):
        if not safe(lambda: node.is_application, False):
            continue
        if needle in object_path(node).lower():
            hits.append(node)
    if not hits:
        result["errors"].append("no application matches %r" % needle)
        return None
    if len(hits) > 1:
        result["errors"].append(
            "%r matches %d applications (%s) - be more specific"
            % (needle, len(hits), ", ".join(object_path(h) for h in hits)))
        return None
    return hits[0]


def child_named(parent, name):
    for child in list(safe(lambda: parent.get_children(False), []) or []):
        if u(safe(lambda: child.get_name(), u"")) == u(name):
            return child
    return None


def task_configuration_of(app):
    for child in list(safe(lambda: app.get_children(False), []) or []):
        if safe(lambda: child.is_task_configuration, False):
            return child
    return None


def set_property(result, obj, name, *candidates):
    """Set a property, trying each candidate value until one is accepted.

    The ScriptEngine's stubs get property types wrong often enough that guessing
    is normal, and a swallowed failure here is invisible: the object keeps a
    default the compiler later rejects for its own reasons. So this reports the
    last error rather than shrugging.
    """
    last = None
    for value in candidates:
        try:
            setattr(obj, name, value)
            return True
        except Exception:
            last = traceback.format_exc()
    result["errors"].append("could not set %s on %s:\n%s"
                            % (name, object_path(obj), last))
    return False


def scaffold_item(cfg, result, proj, item):
    """Create one GVL, program or task, and set its text. Idempotent by name."""
    app = find_application(result, proj, item.get("application"))
    if app is None:
        return
    where = object_path(app)

    def text_for(key):
        # The wrapper has already made every *_file path absolute, exactly as it
        # does for an edits spec.
        path = item.get(key + "_file")
        if path:
            return read_text(path)
        return item.get(key)

    if item.get("gvl"):
        name = u(item["gvl"])
        obj = child_named(app, name)
        created = obj is None
        if created:
            obj = app.create_gvl(name)
        decl = text_for("decl")
        if decl is not None:
            obj.textual_declaration.replace(decl)
        result.setdefault("scaffold", []).append(
            u"%s GVL %s in %s" % (u"created" if created else u"updated", name, where))
        return

    if item.get("program"):
        name = u(item["program"])
        obj = child_named(app, name)
        created = obj is None
        if created:
            obj = app.create_pou(name, PouType.Program)  # noqa: F821
        decl = text_for("decl")
        body = text_for("body")
        if decl is not None:
            obj.textual_declaration.replace(decl)
        if body is not None:
            obj.textual_implementation.replace(body)
        result.setdefault("scaffold", []).append(
            u"%s program %s in %s" % (u"created" if created else u"updated", name, where))
        return

    if item.get("task"):
        name = u(item["task"])
        config = task_configuration_of(app)
        if config is None:
            config = app.create_task_configuration()
        task = child_named(config, name)
        created = task is None
        if created:
            task = config.create_task(name)
        if item.get("interval"):
            if not set_property(result, task, "interval", u(item["interval"])):
                return
        if item.get("priority") is not None:
            # The stub types priority as str; the real property is numeric, and a
            # string leaves it unset - which the compiler then reports as "The
            # task priority is invalid" rather than as a failed assignment. Try
            # the int first and keep the string as the fallback.
            if not set_property(result, task, "priority", int(item["priority"]),
                                u(str(item["priority"]))):
                return
        calls = item.get("calls") or []
        existing = [u(str(p)) for p in list(safe(lambda: task.pous, []) or [])]
        for pou in calls:
            # A task calling the same POU twice is legal and would run it twice,
            # so this has to be checked rather than just added.
            if not [e for e in existing if u(pou) in e]:
                task.pous.add(u(pou))
        # Read back what actually landed. A property the ScriptEngine accepted is
        # not necessarily a property the compiler accepts, and the compiler's
        # complaint ("the task priority is invalid") names the field without
        # showing its value.
        read_back = u"kind=%s interval=%s priority=%s" % (
            u(str(safe(lambda: task.kind_of_task, u"?"))),
            u(str(safe(lambda: task.interval, u"?"))),
            u(str(safe(lambda: task.priority, u"?"))))
        result.setdefault("scaffold", []).append(
            u"%s task %s in %s calling %s [%s]"
            % (u"created" if created else u"updated", name, where,
               ", ".join(calls) or u"nothing", read_back))
        return

    if item.get("set"):
        # Blind property setting, for a setting the stubs do not document and
        # `dir()` cannot reveal - ScriptEngine objects answer dir() with nothing,
        # so the only way to find out whether a property is reachable is to try
        # it and read back. Every attempt is reported, successes included, so a
        # run either proves the name or rules it out.
        for key in sorted(item["set"].keys()):
            value = item["set"][key]
            before = u(str(safe(lambda: getattr(app, key), u"<unreadable>")))
            ok = False
            try:
                setattr(app, key, value)
                ok = True
            except Exception:
                pass
            after = u(str(safe(lambda: getattr(app, key), u"<unreadable>")))
            result.setdefault("scaffold", []).append(
                u"set %s on %s: accepted=%s before=%s after=%s"
                % (key, where, ok, before, after))
        return

    result["errors"].append("scaffold item names none of gvl/program/task/set: %r" % item)


def do_scaffold(cfg, result):
    """Create objects inside an application from a spec, then build and save.

    Same contract as `libs` and `apply`: it refuses to save a project that does
    not build, so a wrong fragment costs a run rather than a project.
    """
    items = cfg.get("scaffold") or []
    if isinstance(items, dict):
        items = [items]
    if not items:
        result["errors"].append("nothing to scaffold: the spec has no objects")
        return
    proj = projects.open(cfg["project"])  # noqa: F821
    try:
        for item in items:
            scaffold_item(cfg, result, proj, item)
            if result["errors"]:
                return
        save_if_it_builds(cfg, result, proj,
                          "it does not build with these scaffolded objects")
    finally:
        safe(lambda: proj.close())


# ------------------------------------------------------------------ libraries
#
# The library manager was the last part of a project the harness could not
# reach. It matters for the same reason everything else here does: a reference
# nothing uses still appears in the Library Manager, still resolves, and still
# reads to the next person as a supported dependency.

REFERENCE_RE = re.compile(
    r"^\s*(?P<name>.+?)\s*,\s*(?P<version>[0-9][0-9.]*|\*)\s*\((?P<company>[^)]*)\)\s*$")


def parse_reference(text):
    """Split "IoDrvModbus, 4.5.0.0 (CODESYS)" into name, version and company.

    A reference carries its version inside its display name - there is no
    separate version property anywhere on the API - so this is the only way to
    compare one against what is installed.
    """
    match = REFERENCE_RE.match(u(text or u""))
    if not match:
        return None
    return {"name": u(match.group("name")),
            "version": u(match.group("version")),
            "company": u(match.group("company"))}


def version_key(text):
    """Sortable form of "4.5.0.0". Unparseable parts sort below numeric ones."""
    parts = []
    for chunk in u(text or u"").split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(-1)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def scripting_namespaces():
    """Every namespace the ScriptEngine might have injected its globals into."""
    spaces = [globals()]
    for mod in ("__builtin__", "builtins"):
        try:
            spaces.append(vars(__import__(mod)))
        except Exception:
            pass
    return spaces


def repository_manager(seen=None):
    """The global library repository object, whatever this build calls it.

    Named lookup first, then discovery by capability. The name is not reliable:
    the shipped stub calls it `library_manager`, and on this install that name
    does not resolve even though `projects` and `system` do from the same
    scope. Rather than guess again next time, find the object that answers
    get_all_libraries and report which name it was under.
    """
    # `librarymanager` is what this install actually calls it. The shipped
    # stub says `library_manager`, with the underscore, and that name does not
    # resolve - the same class of stub-versus-reality gap as export_xml's
    # argument order. The discovery pass below is the guard against it moving
    # again.
    for name in ("librarymanager", "library_manager", "libraries",
                 "library_repository", "libmanager"):
        try:
            obj = eval(name)  # noqa: S307 - injected scripting global
        except Exception:
            continue
        if obj is not None and hasattr(obj, "get_all_libraries"):
            return u(name), obj

    for space in scripting_namespaces():
        for key in sorted(space.keys()):
            if key.startswith("_"):
                continue
            if seen is not None:
                seen.append(u(key))
            try:
                obj = space[key]
            except Exception:
                continue
            if hasattr(obj, "get_all_libraries"):
                return u(key), obj
    return None, None


def installed_versions(result=None):
    """Every library version present in the local repositories, by display name.

    The limit is worth stating plainly, because the whole point of the function
    is to answer "is there a newer one?": it reports what is INSTALLED, not what
    the CODESYS Store has. A library nobody has downloaded is invisible here.
    "Nothing newer" from this means "none on this machine", never "none exists".

    Failures are recorded rather than swallowed. An empty result that looks like
    a clean answer is the worst thing this could return - it would report every
    reference in the project as missing from the repository, which is exactly
    what a real problem looks like.
    """
    tried = []
    seen = []
    name, manager = repository_manager(seen)
    if manager is None:
        if result is not None:
            # Name the candidates that WERE visible: the next person to hit this
            # should not have to run the search a second time to find out.
            result["library_repository_error"] = (
                "no object answering get_all_libraries is reachable. Names in "
                "scope: %s" % (", ".join(sorted(set(seen))[:40]) or "none"))
        return {}

    libs = None
    for call in (lambda: list(manager.get_all_libraries()),
                 lambda: list(manager.get_all_libraries(True)),
                 lambda: list(manager.get_all_libraries(False))):
        try:
            libs = call()
            break
        except Exception:
            tried.append(u(traceback.format_exc().strip().splitlines()[-1]))

    if libs is None:
        # One repository at a time: the argument-less overload is not offered by
        # every build, but the per-repository one always is.
        libs = []
        try:
            for repo in list(manager.repositories):
                try:
                    libs.extend(list(manager.get_all_libraries(repo)))
                except Exception:
                    tried.append(u(traceback.format_exc().strip().splitlines()[-1]))
        except Exception:
            tried.append(u(traceback.format_exc().strip().splitlines()[-1]))

    out = {}
    for lib in libs or []:
        # displayname is the full "Name, 4.5.0.0 (CODESYS)" string, the same
        # form a reference uses - NOT a bare library name. Grouping on it
        # directly gives one entry per version, which then matches nothing.
        display = u(safe(lambda: lib.displayname, u""))
        parsed = parse_reference(display)
        if parsed:
            name, version, company = parsed["name"], parsed["version"], parsed["company"]
        else:
            name = u(safe(lambda: lib.title, u"")) or display
            version = u(safe(lambda: str(lib.version), u""))
            company = u(safe(lambda: lib.company, u""))
        if not name:
            continue
        entry = out.setdefault(name, {"company": company, "versions": []})
        if version and version not in entry["versions"]:
            entry["versions"].append(version)
    for entry in out.values():
        entry["versions"].sort(key=version_key)
        entry["latest"] = entry["versions"][-1] if entry["versions"] else None

    if not out and result is not None:
        result["library_repository_error"] = (
            "%s returned no libraries. Tried: %s" % (name, "; ".join(tried) or "no exception"))
    log("libs: repository %s reported %d library/libraries" % (name, len(out)))
    return out


def libmans(proj):
    return [c for c in list(safe(lambda: proj.get_children(True), []) or [])
            if safe(lambda: c.is_libman, False)]


def reference_report(proj, installed):
    """Every reference in every library manager, measured against the repository."""
    out = []
    for man in libmans(proj):
        manager = object_path(man)
        for ref in list(safe(lambda: list(man.references), []) or []):
            item = {
                "manager": manager,
                "name": u(safe(lambda: ref.name, u"?")),
                "namespace": u(safe(lambda: ref.namespace, u"")),
                "is_placeholder": bool(safe(lambda: ref.is_placeholder, False)),
                "system": bool(safe(lambda: ref.system_library, False)),
            }
            resolution = item["name"]
            if item["is_placeholder"]:
                item["placeholder"] = u(safe(lambda: ref.placeholder_name, u""))
                item["default_resolution"] = u(safe(lambda: ref.default_resolution, u""))
                item["effective_resolution"] = u(safe(lambda: ref.effective_resolution, u""))
                item["is_redirected"] = bool(safe(lambda: ref.is_redirected, False))
                # The EFFECTIVE resolution is what the compiler uses. A default
                # with no effective resolution behind it means the placeholder
                # is not resolved in this project at all - several of the
                # visualisation ones are like that - and calling such a
                # reference "outdated" would send somebody after a version
                # nothing is using.
                item["unresolved"] = not item["effective_resolution"]
                resolution = item["effective_resolution"] or item["default_resolution"]
            parsed = parse_reference(resolution)
            if parsed:
                item["library"] = parsed["name"]
                item["version"] = parsed["version"]
                # Repository keys come from displaynames and references from the
                # project; the two disagree on case (`visuinputs` against
                # `VisuInputs`), so match without it.
                known = installed.get(parsed["name"])
                if known is None:
                    folded = parsed["name"].lower()
                    for key, entry in installed.items():
                        if key.lower() == folded:
                            known = entry
                            break
                if not known:
                    item["not_in_repository"] = True
                else:
                    item["installed_versions"] = known["versions"]
                    item["latest_installed"] = known["latest"]
                    if parsed["version"] == u"*":
                        # A floating reference already resolves to the newest
                        # installed version, so it cannot be behind one.
                        item["floating"] = True
                    elif item.get("unresolved"):
                        pass
                    elif known["latest"] and version_key(known["latest"]) > version_key(parsed["version"]):
                        item["outdated"] = True
            out.append(item)
    out.sort(key=lambda r: (r["manager"], r["name"].lower()))
    return out


def do_libs(cfg, result):
    """Report and edit a project's library references.

    Read-only unless remove/add/update is asked for. When it does write, it
    behaves like `apply`: build first, refuse to save if the build fails.
    Dropping a reference something still uses is exactly the kind of change
    that either compiles or does not, with nothing in between - so the guard
    means a wrong guess costs a run, not a project.
    """
    remove = [u(x) for x in (cfg.get("lib_remove") or [])]
    add = [u(x) for x in (cfg.get("lib_add") or [])]
    update = [u(x) for x in (cfg.get("lib_update") or [])]
    mutating = bool(remove or add or update)

    proj = projects.open(cfg["project"], allow_readonly=not mutating)  # noqa: F821
    try:
        installed = installed_versions(result)
        refs = reference_report(proj, installed)
        result["library_references"] = refs

        # Installed versions for anything referenced, plus anything the caller
        # asked about by name. The whole repository is several hundred entries
        # and nobody wants that in a report.
        wanted = set(r.get("library") for r in refs if r.get("library"))
        needle = u(cfg.get("lib_filter") or u"").lower()
        shown = {}
        for name, entry in installed.items():
            if name in wanted or (needle and needle in name.lower()):
                shown[name] = entry
        result["installed_libraries"] = shown

        if not mutating:
            log("libs: %d reference(s), %d library/libraries reported" % (len(refs), len(shown)))
            return

        managers = libmans(proj)
        if not managers:
            result["errors"].append("no library manager in %s" % cfg["project"])
            return

        # -UpdateLib is the only action that needs to know what is installed.
        # Reporting and removing do not, so a repository that will not answer
        # degrades the report rather than failing the run.
        if update and result.get("library_repository_error"):
            result["errors"].append(
                "cannot update a placeholder without the repository: %s"
                % result["library_repository_error"])
            return

        changed = []

        for name in remove:
            gone = False
            for man in managers:
                try:
                    man.remove_library(name)
                    changed.append(u"removed %s from %s" % (name, object_path(man)))
                    gone = True
                except Exception:
                    continue
            if not gone:
                result["errors"].append(
                    "no library reference named %r - the name must match the "
                    "Library Manager exactly, placeholders included" % name)

        for name in add:
            try:
                managers[0].add_library(name)
                changed.append(u"added %s to %s" % (name, object_path(managers[0])))
            except Exception:
                result["errors"].append("could not add %r:\n%s" % (name, traceback.format_exc()))

        for name in update:
            target = None
            for man in managers:
                for ref in list(safe(lambda: list(man.references), []) or []):
                    if not safe(lambda: ref.is_placeholder, False):
                        continue
                    if u(safe(lambda: ref.placeholder_name, u"")).lower() == name.lower():
                        target = ref
                        break
                if target is not None:
                    break
            if target is None:
                result["errors"].append(
                    "no placeholder named %r. Only a placeholder can be "
                    "repointed; a fixed reference is removed and re-added." % name)
                continue
            current = (parse_reference(safe(lambda: target.effective_resolution, u""))
                       or parse_reference(safe(lambda: target.default_resolution, u"")))
            if not current:
                result["errors"].append("cannot parse the current resolution of %r" % name)
                continue
            known = installed.get(current["name"])
            if not known or not known["latest"]:
                result["errors"].append(
                    "%r is not in any local repository, so there is no version "
                    "here to move it to" % current["name"])
                continue
            if current["version"] == u"*":
                changed.append(u"%s already floats on newest (*)" % name)
                continue
            if version_key(known["latest"]) <= version_key(current["version"]):
                changed.append(u"%s already at %s, the newest installed" % (name, current["version"]))
                continue
            newer = u"%s, %s (%s)" % (current["name"], known["latest"],
                                      known["company"] or current["company"])
            target.default_resolution = newer
            changed.append(u"%s: %s -> %s" % (name, current["version"], known["latest"]))

        result["library_changes"] = changed

        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
        if blocking and not result["errors"] and clear_precompile_cache(cfg, result):
            del result["messages"][:]
            log("build failed; precompile cache cleared, rebuilding once")
            build_and_collect(proj, result)
            blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
            result["precompile_cache_cleared"] = True
        if blocking or result["errors"]:
            result["saved"] = False
            result["errors"].append(
                "project NOT saved: it does not build with these library references")
            return
        proj.save()
        result["saved"] = True
        # Re-read, so the report describes what was saved rather than what was
        # asked for.
        result["library_references"] = reference_report(proj, installed)
    finally:
        safe(lambda: proj.close())


TASKS = {
    "compare": do_compare,
    "scaffold": do_scaffold,
    "info": do_info,
    "device": do_device,
    "download": do_download,
    "scan": do_scan,
    "simulate": do_simulate,
    "tree": do_tree,
    "export": do_export,
    "verify": do_verify,
    "apply": do_apply,
    "rename": do_rename,
    "probe": do_probe,
    "libs": do_libs,
}


# ---------------------------------------------------------------- entry point


def main():
    result = {
        "task": None,
        "ok": False,
        "errors": [],
        "messages": [],
        "imports": [],
        "built": [],
        # Assertion failures from a simulate spec: a wrong value is a failed run,
        # not a tool error, so they are counted separately but still fail `ok`.
        "test_failures": [],
    }
    report_path = None
    try:
        cfg = read_task()
        report_path = cfg["report"]
        _LOG_PATH[0] = report_path + ".log"
        try:
            os.remove(_LOG_PATH[0])
        except Exception:
            pass
        result["task"] = cfg["task"]
        log("task=%s project=%s" % (cfg["task"], cfg.get("project")))
        # Keep dialogs out of the way but still see what they said.
        safe(lambda: setattr(system, "prompt_handling", PromptHandling.LogSimplePrompts))  # noqa: F821
        handler = TASKS.get(cfg["task"])
        if handler is None:
            raise ValueError("unknown task: %s" % cfg["task"])
        handler(cfg, result)
        log("handler done")
    except Exception:
        trace = traceback.format_exc()
        log("UNHANDLED:\n%s" % trace)
        result["errors"].append(trace)

    blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
    result["error_count"] = len(blocking)
    result["warning_count"] = len([m for m in result["messages"] if m["severity"] == "Warning"])
    result["failure_count"] = len(result["test_failures"])
    result["ok"] = not result["errors"] and not blocking and not result["test_failures"]

    if report_path is None:
        report_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "codesys_task_report.json")
    write_report(report_path, result)
    log("report written: ok=%s errors=%s" % (result["ok"], len(result["errors"])))
    system.exit(0 if result["ok"] else 1)  # noqa: F821


main()
