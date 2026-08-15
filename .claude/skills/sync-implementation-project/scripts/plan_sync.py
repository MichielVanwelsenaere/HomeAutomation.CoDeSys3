#!/usr/bin/env python3
"""Turn two `codesys.ps1 info` reports into a sync plan.

The reference project is the source of truth for *shared* code - the function
blocks, functions and data types that every installation reuses. An
installation project owns its own *logic*: which blocks are instantiated, on
which I/O channels, in which programs, with which names and timings.

This script decides which objects fall on which side of that line, and emits:

  * a plan JSON, listing exactly the object names to lift out of the reference
  * a compatibility verdict, which is a gate rather than advice
  * a readable report of everything it classified and why

It reads only the two info reports, so it is instant and can be re-run freely.

    py plan_sync.py --reference .ai/reports/info.HomeAutomation.json \
                    --implementation .ai/reports/info.SiteA.json \
                    --out .ai/sync/plan.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from typing import Any


# Object kinds that are shared library code, i.e. what this skill synchronises.
# A PROGRAM is deliberately absent: a program is where an installation wires its
# own blocks to its own I/O, and copying one across sites would replace the
# building's behaviour with the reference building's behaviour.
SHARED_KINDS = {"FUNCTION_BLOCK", "FUNCTION", "TYPE", "INTERFACE"}

# Kinds that carry an installation's own logic and are never synchronised.
LOGIC_KINDS = {"PROGRAM", "VAR_GLOBAL", "VAR_CONFIG"}


def load(path: str) -> dict[str, Any]:
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def device_names(report: dict[str, Any]) -> set[str]:
    """Top-level containers that are devices.

    Everything filed under a device node - programs, GVLs, the task
    configuration, the I/O modules - is that installation's own. Everything at
    project level is the shared POU pool. This is the structural half of the
    classification, and it is what catches a GVL or program that some site
    happens to have named like a library block.
    """
    return {d["name"] for d in report.get("info", {}).get("devices", [])}


def index_by_name(report: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Name -> object, preferring the object that actually owns code.

    A project contains the same name twice on purpose: a program lives under
    PRG's and is *called* from a node under Task Configuration, and both are
    objects with that name. The call node holds nothing. A naive
    {o["name"]: o for o in objects} keeps whichever came last, which is usually
    the empty one - and then every program in the project reads as having no
    declaration and no kind, and gets misclassified.

    Returns the index and any name that is genuinely ambiguous (two
    code-bearing objects sharing a name), which is a thing to report rather
    than resolve silently.
    """
    index: dict[str, dict[str, Any]] = {}
    ambiguous: list[str] = []
    for obj in report["objects"]:
        if obj.get("is_task_call"):
            continue
        name = obj["name"]
        current = index.get(name)
        if current is None:
            index[name] = obj
            continue
        # Prefer the one with code. If both have code, that is a real collision.
        if current.get("signature") is None and obj.get("signature") is not None:
            index[name] = obj
        elif current.get("signature") is not None and obj.get("signature") is not None:
            if name not in ambiguous:
                ambiguous.append(name)
    return index, ambiguous


def word_in(needle: str, haystack: str) -> bool:
    """Whole-identifier occurrence of `needle` in ST source."""
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(needle), haystack) is not None


def source_of(obj: dict[str, Any]) -> str:
    """All the ST text of an object, when the info report was taken with -Full."""
    parts = [obj.get("decl") or "", obj.get("impl") or ""]
    for member in obj.get("members") or []:
        parts.append(member.get("decl") or "")
        parts.append(member.get("impl") or "")
    return "\n".join(parts)


VAR_BLOCK = re.compile(r"^[ \t]*(VAR_GLOBAL[^\r\n]*)$(.*?)^[ \t]*END_VAR[ \t]*$",
                       re.MULTILINE | re.DOTALL | re.IGNORECASE)
DECLARATION = re.compile(r"^[ \t]*([A-Za-z_]\w*)[ \t]*:", re.MULTILINE)


def gvl_blocks(decl: str) -> list[tuple[str, str]]:
    """(header, body) for each VAR_GLOBAL ... END_VAR block in a GVL.

    The header matters: `VAR_GLOBAL CONSTANT` and plain `VAR_GLOBAL` are
    different things, and a constant appended into the wrong one stops being
    usable as a string length.
    """
    return [(m.group(1).strip(), m.group(2)) for m in VAR_BLOCK.finditer(decl or "")]


def gvl_members(decl: str) -> dict[str, tuple[str, str]]:
    """member name -> (block header, its declaration text, statement included)."""
    out: dict[str, tuple[str, str]] = {}
    for header, body in gvl_blocks(decl):
        # Split the block body into statements. A declaration runs to its
        # terminating semicolon, which is what carries initialisers containing
        # commas and nested brackets.
        for statement in re.split(r";", body):
            statement = statement.strip("\r\n")
            if not statement.strip():
                continue
            match = DECLARATION.search(statement)
            if not match:
                continue
            out[match.group(1)] = (header, statement.strip() + ";")
    return out


def plan_gvl_additions(
    ref_objects: dict[str, dict[str, Any]],
    impl_objects: dict[str, dict[str, Any]],
    selected: list[str],
) -> list[dict[str, Any]]:
    """Global-variable members the synced blocks need and the installation lacks.

    The shared/logic split is not clean at the GVL boundary. `MqttVariables`
    holds an installation's instance declarations - unambiguously its own - and
    also holds shared infrastructure the blocks read, like the string-length
    constants a block declares its topic buffers with. When the reference adds
    such a constant, every synced block fails with "Identifier
    'MqttVariables.MQTT_TOPIC_LEN' not defined" and the GVL is the last place
    anyone looks, because the GVL is on the do-not-touch list.

    So: work out exactly which members the synced code references and the
    installation does not have, and plan those - and only those - as an
    APPEND. Nothing existing is rewritten, so no instance declaration can be
    lost. Anything beyond an append is a human's call.
    """
    additions: list[dict[str, Any]] = []
    corpus = "\n".join(source_of(ref_objects[n]) for n in selected if n in ref_objects)

    for name, impl_gvl in sorted(impl_objects.items()):
        if impl_gvl.get("kind") != "VAR_GLOBAL":
            continue
        ref_gvl = ref_objects.get(name)
        if ref_gvl is None or ref_gvl.get("kind") != "VAR_GLOBAL":
            continue
        have = set(gvl_members(impl_gvl.get("decl") or ""))
        reference = gvl_members(ref_gvl.get("decl") or "")
        wanted = []
        for member, (header, statement) in sorted(reference.items()):
            if member in have:
                continue
            if not word_in("%s.%s" % (name, member), corpus):
                continue
            wanted.append({"member": member, "block": header, "declaration": statement})
        if wanted:
            additions.append({"gvl": name, "members": wanted})
    return additions


def classify(obj: dict[str, Any], devices: set[str]) -> str:
    if obj.get("is_task_call"):
        return "logic"
    if obj.get("is_folder"):
        return "folder"
    if obj.get("is_device") or obj.get("is_application") or obj.get("is_libman"):
        return "device"
    if obj.get("is_task_configuration"):
        return "logic"
    if obj.get("top") in devices:
        # Filed under the device: this installation's own, whatever it declares.
        return "logic"
    kind = obj.get("kind")
    if kind in SHARED_KINDS:
        return "shared"
    if kind in LOGIC_KINDS:
        return "logic"
    if obj.get("signature") is None:
        # No code in it at all (a visualisation style, an image pool).
        return "other"
    return "unclassified"


def compatibility(ref: dict[str, Any], impl: dict[str, Any]) -> dict[str, Any]:
    """Can the reference's blocks compile inside this implementation project?

    Everything checked here is a precondition that a build would only report as
    a confusing downstream error, so it is worth failing early and by name.

    Note what is deliberately NOT checked: the CODESYS compiler version stored
    in the project. It is not reachable from the scripting API. The empirical
    check replaces it - `verify -Baseline -Project <impl>` builds the untouched
    implementation project with the installed IDE, and if the stored compiler
    version is missing the build says so outright.
    """
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str, fatal: bool = True) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "fatal": fatal})

    ref_ide = ref["info"].get("ide_version", "")
    impl_ide = impl["info"].get("ide_version", "")
    check(
        "same IDE read both projects",
        ref_ide == impl_ide and bool(ref_ide),
        "reference %s / implementation %s" % (ref_ide or "?", impl_ide or "?"),
    )

    # Library references. Placeholders resolve through the installed library
    # repository, so two projects opened by the same IDE resolve them
    # identically - which means an identical *set* of references is a genuine
    # guarantee here, not a coincidence. A fixed reference pins a version and
    # must match exactly.
    ref_libs = {lib["name"] for lib in ref["info"]["libraries"]}
    impl_libs = {lib["name"] for lib in impl["info"]["libraries"]}
    missing = sorted(ref_libs - impl_libs)
    check(
        "libraries the reference uses are present",
        not missing,
        "all %d present" % len(ref_libs) if not missing else "MISSING: " + ", ".join(missing),
    )
    extra = sorted(impl_libs - ref_libs)
    check(
        "no unexpected extra libraries",
        not extra,
        "none" if not extra else "implementation also has: " + ", ".join(extra),
        fatal=False,
    )

    # Runtime target. The device *id* is the controller family; the I/O modules
    # plugged under it differ per building and are not compared.
    def controllers(report: dict[str, Any]) -> set[tuple[str, str]]:
        return {
            (d["id"], d["version"])
            for d in report["info"]["devices"]
            # 0013 is the PFC controller itself; 0001 entries are bus couplers
            # and I/O modules, which are site wiring.
            if d.get("id") not in ("0001",)
        }

    ref_ctl = controllers(ref)
    impl_ctl = controllers(impl)
    check(
        "same controller type and version",
        bool(ref_ctl) and ref_ctl == impl_ctl,
        "reference %s / implementation %s"
        % (sorted(ref_ctl) or "?", sorted(impl_ctl) or "?"),
    )

    fatal = [c for c in checks if not c["ok"] and c["fatal"]]
    return {"ok": not fatal, "checks": checks, "blocking": [c["name"] for c in fatal]}


SENTINEL = "synced from the reference project"


def write_edits(folder: str, additions: list[dict[str, Any]]) -> None:
    """Emit an edits spec that appends the missing GVL members, and nothing else.

    `decl_append` with a `skip_if_contains` sentinel: append-only, so no existing
    declaration can be rewritten or dropped, and idempotent, so re-running a
    half-finished sync does not declare everything twice. Both properties are
    load-bearing - this is a file that holds a building's instance list.
    """
    if not os.path.isdir(folder):
        os.makedirs(folder)
    edits = []
    for entry in additions:
        gvl = entry["gvl"]
        by_block: dict[str, list[str]] = {}
        for member in entry["members"]:
            by_block.setdefault(member["block"], []).append(member["declaration"])
        lines = ["", "(* %s *)" % SENTINEL]
        for header in sorted(by_block):
            lines.append(header)
            for statement in by_block[header]:
                lines.append("\t" + statement)
            lines.append("END_VAR")
        fragment = os.path.join(folder, "%s.decl" % gvl)
        with io.open(fragment, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("\n".join(lines) + "\n")
        edits.append({
            "pou": gvl,
            "decl_append_file": os.path.basename(fragment),
            "skip_if_contains": SENTINEL,
        })
    # Hand-authored call-site migrations live in their own file so that
    # re-running the planner cannot wipe them, and are folded into the single
    # spec that `-Edits` takes. See the skill's "Call-site migrations" section.
    migrations_path = os.path.join(folder, "migrations.json")
    migrations = []
    if os.path.isfile(migrations_path):
        with io.open(migrations_path, encoding="utf-8") as handle:
            migrations = json.load(handle).get("edits", [])

    with io.open(os.path.join(folder, "edits.json"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({
            "edits": edits + migrations,
            # Replace an object that already exists, rather than filing a second
            # one beside it. Travels here because `-Edits` and the candidate
            # import share one spec file.
            "import_conflict": "replace",
        }, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="info report of the reference project")
    parser.add_argument("--implementation", required=True, help="info report of the implementation project")
    parser.add_argument("--out", help="write the plan JSON here")
    parser.add_argument(
        "--emit-edits",
        metavar="DIR",
        help="write an edits spec into DIR that appends the global-variable "
             "members the synced blocks need and the installation lacks",
    )
    parser.add_argument(
        "--add-missing",
        action="store_true",
        help="also plan shared blocks the implementation does not have at all. "
             "Off by default: a block the installation never used is dead code "
             "there, and adding it is a scope decision, not a sync.",
    )
    args = parser.parse_args()

    ref = load(args.reference)
    impl = load(args.implementation)
    ref_devices = device_names(ref)
    impl_devices = device_names(impl)

    ref_objects, ref_ambiguous = index_by_name(ref)
    impl_objects, impl_ambiguous = index_by_name(impl)

    ref_class = {n: classify(o, ref_devices) for n, o in ref_objects.items()}
    impl_class = {n: classify(o, impl_devices) for n, o in impl_objects.items()}

    update: list[dict[str, Any]] = []
    add: list[dict[str, Any]] = []
    unchanged: list[str] = []
    site_only: list[dict[str, Any]] = []
    reference_only_logic: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []

    for name in sorted(ref_objects):
        robj = ref_objects[name]
        kind_of_object = ref_class[name]
        iobj = impl_objects.get(name)

        if kind_of_object != "shared":
            if iobj is None and kind_of_object == "logic":
                reference_only_logic.append(
                    {"name": name, "kind": robj.get("kind"), "top": robj.get("top")}
                )
            continue

        if iobj is None:
            add.append({"name": name, "kind": robj.get("kind"), "folder": robj.get("top")})
            continue

        if impl_class[name] != "shared":
            # Same name, different nature: the installation has a program or a
            # GVL where the reference has a block. Overwriting that would delete
            # site logic, so it stops here and asks for a human.
            review.append({
                "name": name,
                "reason": "reference has %s, implementation has %s"
                          % (robj.get("kind"), iobj.get("kind")),
                "reference_kind": robj.get("kind"),
                "implementation_kind": iobj.get("kind"),
            })
            continue

        if robj.get("signature") == iobj.get("signature"):
            unchanged.append(name)
            continue

        update.append({
            "name": name,
            "kind": robj.get("kind"),
            "folder": robj.get("top"),
            "implementation_folder": iobj.get("top"),
            "members_reference": len(robj.get("members") or []),
            "members_implementation": len(iobj.get("members") or []),
            "folder_moves": robj.get("top") != iobj.get("top"),
        })

    for name in sorted(impl_objects):
        if name in ref_objects:
            continue
        iobj = impl_objects[name]
        site_only.append({
            "name": name,
            "kind": iobj.get("kind"),
            "top": iobj.get("top"),
            "classification": impl_class[name],
        })

    selected = [item["name"] for item in update]
    if args.add_missing:
        selected += [item["name"] for item in add]

    # A block cannot be updated to a version that names a type the installation
    # project has never heard of. Where the reference report carries source text
    # (`info -Full`), work out which of the missing shared objects the planned
    # ones actually reference, and pull those in too - transitively, because a
    # newly added type can reference another one.
    #
    # Without this the sync builds a project that fails with "Identifier
    # 'E_MQTT_ENTITY' not defined" and it is not obvious why: nothing in the
    # plan mentions the type, because nothing in the plan is the type.
    required: list[dict[str, Any]] = []
    have_source = any(o.get("decl") or o.get("impl") for o in ref["objects"])
    if have_source:
        available = {item["name"]: item for item in add}
        chosen = set(selected)
        changed = True
        while changed and available:
            changed = False
            corpus = "\n".join(source_of(ref_objects[n]) for n in chosen if n in ref_objects)
            for name in sorted(available):
                if name in chosen:
                    continue
                if word_in(name, corpus):
                    chosen.add(name)
                    entry = dict(available[name])
                    entry["required_by_plan"] = True
                    required.append(entry)
                    changed = True
        selected = sorted(chosen)
    else:
        required = None  # type: ignore[assignment]

    gvl_additions = plan_gvl_additions(ref_objects, impl_objects, selected) if have_source else None
    if args.emit_edits and gvl_additions:
        write_edits(args.emit_edits, gvl_additions)

    plan = {
        "reference": ref["info"]["path"],
        "gvl_additions": gvl_additions,
        "implementation": impl["info"]["path"],
        "compatibility": compatibility(ref, impl),
        # The export list for `codesys.ps1 export -Only`.
        "export": sorted(selected),
        "update": update,
        "add_available": add,
        "add_included": bool(args.add_missing),
        # None means the reference report had no source text, so this could not
        # be worked out - see `have_source`. Not the same as "nothing needed".
        "add_required": required,
        "unchanged": unchanged,
        "site_only": site_only,
        "reference_only_logic": reference_only_logic,
        "needs_review": review,
        "ambiguous_names": {"reference": ref_ambiguous, "implementation": impl_ambiguous},
    }

    if args.out:
        parent = os.path.dirname(os.path.abspath(args.out))
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False))

    compat = plan["compatibility"]
    print("reference      : %s" % plan["reference"])
    print("implementation : %s" % plan["implementation"])
    print("")
    print("COMPATIBILITY")
    for c in compat["checks"]:
        mark = "OK  " if c["ok"] else ("FAIL" if c["fatal"] else "warn")
        print("  [%s] %-42s %s" % (mark, c["name"], c["detail"]))
    print("  => %s" % ("compatible" if compat["ok"] else
                       "INCOMPATIBLE - " + ", ".join(compat["blocking"])))
    print("")
    print("SHARED CODE TO UPDATE (%d)" % len(update))
    for item in update:
        moved = "  MOVES %s -> %s" % (item["implementation_folder"], item["folder"]) if item["folder_moves"] else ""
        print("  %-40s %-16s %s%s" % (item["name"], item["kind"] or "?", item["folder"], moved))
    print("")
    if required is None:
        print("DEPENDENCIES: not checked - the reference info report has no source text.")
        print("              re-run `codesys.ps1 info -Full` on the reference.")
    else:
        names = [item["name"] for item in required]
        print("PULLED IN AS DEPENDENCIES (%d)  %s" % (len(names), ", ".join(names)))
    print("")
    required_names = {item["name"] for item in (required or [])}
    optional_add = [item for item in add if item["name"] not in required_names]
    print("SHARED CODE MISSING FROM THE IMPLEMENTATION AND NOT REFERENCED (%d)%s"
          % (len(optional_add), "" if args.add_missing else "  - not planned, pass --add-missing"))
    for item in optional_add:
        print("  %-40s %-16s %s" % (item["name"], item["kind"] or "?", item["folder"]))
    print("")
    if gvl_additions:
        print("GLOBAL VARIABLES TO APPEND (append-only, nothing rewritten)")
        for entry in gvl_additions:
            for member in entry["members"]:
                # The declaration text can carry the reference's comment block,
                # which is worth keeping in the fragment and useless on one line.
                terse = re.sub(r"\(\*.*?\*\)", "", member["declaration"], flags=re.DOTALL)
                terse = " ".join(terse.split())
                print("  %-24s %-22s %s" % (entry["gvl"], member["block"], terse))
        if args.emit_edits:
            print("  edits spec: %s" % os.path.join(args.emit_edits, "edits.json"))
        else:
            print("  NOT emitted - pass --emit-edits DIR to generate them")
        print("")
    print("ALREADY IDENTICAL (%d)" % len(unchanged))
    print("")
    print("LEFT ALONE - the installation's own (%d)" % len(site_only))
    for item in site_only:
        print("  %-40s %-16s %s" % (item["name"], item["kind"] or "?", item["top"]))
    print("")
    print("LEFT ALONE - reference-only logic, not shared code (%d)" % len(reference_only_logic))
    for item in reference_only_logic:
        print("  %-40s %-16s %s" % (item["name"], item["kind"] or "?", item["top"]))
    if review:
        print("")
        print("NEEDS A HUMAN (%d)" % len(review))
        for item in review:
            print("  %-40s %s" % (item["name"], item["reason"]))
    if ref_ambiguous or impl_ambiguous:
        print("")
        print("AMBIGUOUS NAMES - two code-bearing objects share a name, so the")
        print("classification picked one arbitrarily. Resolve before trusting the plan.")
        for name in ref_ambiguous:
            print("  reference     : %s" % name)
        for name in impl_ambiguous:
            print("  implementation: %s" % name)
    print("")
    print("EXPORT SET (%d): %s" % (len(plan["export"]), ", ".join(plan["export"])))
    if args.out:
        print("")
        print("plan written to %s" % args.out)

    if not compat["ok"]:
        return 2
    if review or ref_ambiguous or impl_ambiguous:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
