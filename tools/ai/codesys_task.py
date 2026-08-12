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


def add_verify_harness(proj, result, files):
    """Declare an instance of each candidate function block in a compiled program.

    Declaration is enough: CODESYS generates code for an instantiated function
    block, so the body gets fully checked. Instances are never called, which
    keeps VAR_IN_OUT and required inputs out of the picture.
    """
    instantiable = []
    skipped = []
    for path in files:
        good, bad = candidate_pous(path)
        instantiable.extend(good)
        skipped.extend([{"name": n, "reason": r} for n, r in bad])

    harness = {"instantiated": instantiable, "not_instantiated": skipped, "host": None}
    result["harness"] = harness
    if not instantiable:
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
    lines = [u"", u"// injected by tools/ai/codesys_task.py - sandbox only", u"VAR"]
    for index, name in enumerate(instantiable):
        lines.append(u"\tai_verify_%d : %s;" % (index, name))
    lines.append(u"END_VAR")
    block = u"\n".join(lines) + u"\n"
    try:
        # A second VAR block after the existing one is valid IEC, so this needs
        # no parsing of the host's declaration.
        host.textual_declaration.append(block)
        log("harness: declared %d instance(s) in %s" % (len(instantiable), harness["host"]))
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
        # in XML form for the same reason.
        #               reporter, objects,      path,   recursive, folders, plaintext
        proj.export_xml(reporter, tuple(roots), target, True,      True,    False)
        result["export"] = reporter.as_dict()
        result["output"] = target
        result["errors"].extend(reporter.errors)
    finally:
        safe(lambda: proj.close())


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


def import_candidates(proj, cfg, result):
    files = candidate_files(cfg.get("candidates"))
    result["candidates"] = files
    log("candidates: %d file(s)" % len(files))
    for path in files:
        reporter = Reporter()
        try:
            # Positional, reporter first (see the `probe` task).
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
        add_verify_harness(proj, result, files)
        build_and_collect(proj, result)
    finally:
        safe(lambda: proj.close())


def do_apply(cfg, result):
    proj = projects.open(cfg["project"])  # noqa: F821
    try:
        files = import_candidates(proj, cfg, result)
        if not files:
            result["errors"].append("nothing to apply: no candidate XML found")
            return
        # No harness here: `apply` writes to the real project, so it must not
        # inject scaffolding. Run `verify` first - that is what checks the code.
        build_and_collect(proj, result)
        blocking = [m for m in result["messages"] if m["severity"] in BAD_SEVERITIES]
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
        add_verify_harness(proj, result, files)

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


TASKS = {
    "device": do_device,
    "download": do_download,
    "scan": do_scan,
    "simulate": do_simulate,
    "tree": do_tree,
    "export": do_export,
    "verify": do_verify,
    "apply": do_apply,
    "probe": do_probe,
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
