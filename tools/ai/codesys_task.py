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
    clear_all_messages()
    for app in apps:
        name = object_path(app)
        try:
            log("building %s ..." % name)
            app.build()
            result["built"].append(name)
            log("built %s" % name)
        except Exception:
            trace = traceback.format_exc()
            log("build failed for %s:\n%s" % (name, trace))
            result["errors"].append("build failed for %s: %s" % (name, trace))
    log("collecting messages ...")
    result["messages"] = collect_messages()
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


def do_device(cfg, result):
    """Report the configured communication target, without connecting to it.

    Answers "could this project be downloaded from here?" — which gateway and
    address the device node points at, and whether simulation is switched on —
    while making no attempt to reach the PLC.
    """
    proj = projects.open(cfg["project"], allow_readonly=True)  # noqa: F821
    try:
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
    "info": do_info,
    "device": do_device,
    "download": do_download,
    "scan": do_scan,
    "simulate": do_simulate,
    "tree": do_tree,
    "export": do_export,
    "verify": do_verify,
    "apply": do_apply,
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
