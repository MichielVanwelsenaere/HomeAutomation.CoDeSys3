#!/usr/bin/env python3
"""Prove a sync changed the shared blocks and nothing else.

This is the check that makes the whole skill trustworthy. A clean build after a
sync says the project still compiles; it says nothing about whether the sync
also rewrote a program, dropped a GVL member or moved an I/O mapping. Only a
before/after comparison of the implementation project can say that.

Run `codesys.ps1 info` on the implementation copy before the sync and again
after, then:

    py check_logic_unchanged.py --before .ai/sync/before.json \
                                --after  .ai/sync/after.json \
                                --plan   .ai/sync/plan.json

Exit code 0 means: every object that changed was on the plan, and nothing the
installation owns moved at all. Anything else is a finding, printed by name.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from typing import Any

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from plan_sync import classify, device_names, index_by_name, source_of, word_in  # noqa: E402


def instantiation_coverage(
    objects: dict[str, Any], planned: set[str], devices: set[str]
) -> tuple[list[str], list[str]]:
    """Which synced blocks the installation's own compiled code actually uses.

    `verify` reports a block as NOT COMPILE-CHECKED whenever its FB_init takes
    parameters, because the harness cannot declare an instance without supplying
    them. On a sync that warning is usually a false alarm: the installation's own
    programs and GVLs declare these blocks for real, and those objects ARE
    compiled, so the block was checked - just not by the harness.

    "Usually" is not "always", so this works it out instead of assuming.

    Reachability is TRANSITIVE, and getting that wrong understates coverage
    badly. The installation's programs name maybe ten blocks directly; those
    blocks EXTEND FB_MQTT_BASE, declare MQTT_MESSAGE, and take E_MQTT_ENTITY
    parameters, and every one of those is compiled too. So: seed from the code
    the installation owns, then follow references through the shared objects
    until nothing new appears.
    """
    reachable: set[str] = set()
    frontier = "\n".join(
        source_of(obj) for obj in objects.values()
        if obj.get("top") in devices and obj.get("signature") is not None
    )
    candidates = {n: o for n, o in objects.items()
                  if o.get("signature") is not None and o.get("top") not in devices}
    while frontier:
        found = [n for n in candidates if n not in reachable and word_in(n, frontier)]
        if not found:
            break
        reachable.update(found)
        frontier = "\n".join(source_of(candidates[n]) for n in found)

    covered = sorted(n for n in planned if n in reachable)
    uncovered = sorted(n for n in planned if n not in reachable)
    return covered, uncovered


def declaration_lines(obj: dict[str, Any]) -> list[str]:
    return [line.strip() for line in (obj.get("decl") or "").splitlines() if line.strip()]


COMMENT_BLOCK = re.compile(r"\(\*.*?\*\)", re.DOTALL)


def code_only(text: str) -> list[str]:
    """The code of a declaration or body, with everything CODESYS is free to
    reshape on import taken out: comments in either form, blank lines, and an
    empty VAR/END_VAR pair. Returned sorted, because the importer also reorders
    VAR sections - a block whose VAR_OUTPUT moved above its VAR is the same
    block.

    Deliberately blunt: it answers "is this the same code", not "is this the same
    file". Anything it cannot see is something the compiler cannot see either.
    """
    text = COMMENT_BLOCK.sub(" ", text or "")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"//.*$", "", line).strip()
        if line:
            lines.append(line)
    out = []
    for line in lines:
        if out and out[-1].upper() == "VAR" and line.upper() == "END_VAR":
            out.pop()               # an empty VAR block the importer dropped
            continue
        out.append(line)
    return sorted(out)


def same_code(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True when two objects are the same code, ignoring import reshaping."""
    if code_only(left.get("decl")) != code_only(right.get("decl")):
        return False
    if code_only(left.get("impl")) != code_only(right.get("impl")):
        return False
    lm = {m["name"]: m for m in left.get("members") or []}
    rm = {m["name"]: m for m in right.get("members") or []}
    if set(lm) != set(rm):
        return False
    for name, member in lm.items():
        other = rm[name]
        if code_only(member.get("decl")) != code_only(other.get("decl")):
            return False
        if code_only(member.get("impl")) != code_only(other.get("impl")):
            return False
    return True


def load(path: str) -> dict[str, Any]:
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, help="info report taken before the sync")
    parser.add_argument("--after", required=True, help="info report taken after the sync")
    parser.add_argument("--plan", required=True, help="the plan that was applied")
    parser.add_argument(
        "--migrations",
        help="hand-authored call-site migrations that were applied. Objects named "
             "here are allowed to have changed, and each is listed in the output "
             "so the change is never invisible.",
    )
    parser.add_argument(
        "--reference",
        help="info report of the reference project. With it, a planned object "
             "that did not change is compared against the reference before being "
             "reported: one that already matches it had nothing to import, which "
             "is not the same failure as an import that silently did nothing.",
    )
    args = parser.parse_args()

    reference = load(args.reference) if args.reference else None
    before = load(args.before)
    after = load(args.after)
    plan = load(args.plan)

    planned = set(plan.get("export", []))
    # GVLs the plan appends to. Allowed to change, but only by growing - checked
    # line by line below, because this is the file that holds a building's
    # instance list and a rewrite would be catastrophic and silent.
    additive = {entry["gvl"] for entry in (plan.get("gvl_additions") or [])}
    migrated: set[str] = set()
    deletions: set[str] = set()
    if args.migrations:
        for edit in load(args.migrations).get("edits", []):
            if edit.get("delete_pou"):
                deletions.add(edit["pou"])
            else:
                migrated.add(edit["pou"])

    b_objects, _ = index_by_name(before)
    a_objects, _ = index_by_name(after)
    b_devices = device_names(before)

    findings: list[str] = []
    expected_changed: list[str] = []
    unexpected_changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    moved: list[str] = []
    grew: list[str] = []
    migrations_seen: list[str] = []

    for name in sorted(set(b_objects) | set(a_objects)):
        b = b_objects.get(name)
        a = a_objects.get(name)
        if b is None:
            added.append(name)
            if name not in planned:
                findings.append("ADDED but not on the plan: %s (%s)" % (name, a.get("top")))
            continue
        if a is None:
            removed.append(name)
            if name not in deletions:
                findings.append("REMOVED by the sync: %s (%s)" % (name, b.get("top")))
            continue
        if b.get("top") != a.get("top"):
            moved.append(name)
            if name not in planned:
                findings.append(
                    "MOVED but not on the plan: %s  %s -> %s" % (name, b.get("top"), a.get("top"))
                )
        if b.get("signature") == a.get("signature"):
            continue
        if name in planned:
            expected_changed.append(name)
            continue
        if name in additive:
            # Append-only is the whole guarantee here. Every declaration line
            # that was there must still be there; new lines are the point.
            before_lines = declaration_lines(b)
            after_lines = declaration_lines(a)
            if not before_lines:
                findings.append("GVL %s has no declaration text to compare - "
                                "re-run info with -Full" % name)
                continue
            remaining = list(after_lines)
            lost = []
            for line in before_lines:
                if line in remaining:
                    remaining.remove(line)
                else:
                    lost.append(line)
            if lost:
                findings.append(
                    "GVL %s was NOT append-only - %d declaration line(s) gone, first: %s"
                    % (name, len(lost), lost[0][:80])
                )
            else:
                grew.append("%s (+%d line(s))" % (name, len(after_lines) - len(before_lines)))
            continue
        if name in migrated:
            migrations_seen.append(name)
            continue
        unexpected_changed.append(name)
        kind_of_object = classify(b, b_devices)
        findings.append(
            "CHANGED but not on the plan: %s  (%s, %s, in %s)"
            % (name, b.get("kind") or "?", kind_of_object, b.get("top"))
        )

    # A planned block that did NOT change is just as much a failure: the import
    # silently did nothing, and a green build would hide it. This is the exact
    # failure mode the reference project's own notes warn about - an edit that
    # reports success and does not take effect.
    inert = sorted(planned - set(expected_changed) - set(added))
    # ...unless it did not change because it was already the same code. That is
    # not hypothetical: an installation that has just had the reference's rename
    # maps applied to it holds byte-equal blocks, and CODESYS's importer leaves
    # them alone. It also normalises on import - it reorders VAR sections, drops
    # an empty VAR/END_VAR pair, and stores a /// doc comment as structured
    # documentation that exports as (* *) - so three kinds of difference here are
    # provably not code. Comparing against the reference with those normalised
    # away separates "the import silently did nothing", which is a real and
    # dangerous failure, from "there was nothing to do", which is fine. Without
    # this the one check that gates a promote cries wolf on every sync.
    in_step = []
    if reference is not None:
        ref_objects = {
            o["name"]: o for o in reference["objects"] if not o.get("is_task_call")
        }
        after_objects = {
            o["name"]: o for o in after["objects"] if not o.get("is_task_call")
        }
        still_inert = []
        for name in inert:
            if name in ref_objects and name in after_objects and same_code(
                ref_objects[name], after_objects[name]
            ):
                in_step.append(name)
            else:
                still_inert.append(name)
        inert = still_inert
    for name in inert:
        findings.append("PLANNED but unchanged - the import did not take: %s" % name)

    gone = sorted(n for n in deletions if n not in a_objects)
    if gone:
        print("deleted deliberately            : %d  %s" % (len(gone), ", ".join(gone)))
        print("  Named with delete_pou in the migrations, and confirmed absent.")
        print("")

    if in_step:
        print("already in step with the reference : %d  %s"
              % (len(in_step), ", ".join(in_step)))
        print("  Nothing to import: same code, differing only in what CODESYS")
        print("  reshapes on import - VAR section order, an empty VAR block, or a")
        print("  /// comment stored as structured documentation.")
        print("")

    print("before : %s" % before["info"]["path"])
    print("after  : %s" % after["info"]["path"])
    print("planned: %d object(s)" % len(planned))
    print("")
    print("changed as planned : %d  %s" % (len(expected_changed), ", ".join(expected_changed)))
    print("added              : %d  %s" % (len(added), ", ".join(added)))
    print("moved              : %d  %s" % (len(moved), ", ".join(moved)))
    print("globals appended   : %d  %s" % (len(grew), ", ".join(grew)))
    print("")
    # Never a silent pass: these are edits to the installation's own programs,
    # and the whole point of the skill is that they are visible and deliberate.
    if migrations_seen:
        print("CALL SITES MIGRATED - the installation's own code was edited (%d)"
              % len(migrations_seen))
        for name in migrations_seen:
            print("  %s" % name)
        print("  These must be behaviour-preserving. Review them before promoting.")
        print("")
    # A deletion that did happen needs no further proof; one that did NOT is a
    # finding, because the object is still there and something still expects it
    # to be gone.
    for name in sorted(deletions):
        if name in a_objects:
            findings.append("DELETION listed but the object is still there: %s" % name)
    unmigrated = sorted(migrated - set(migrations_seen))
    for name in unmigrated:
        findings.append("MIGRATION listed but the object did not change: %s" % name)

    covered, uncovered = instantiation_coverage(a_objects, planned, device_names(after))
    print("COMPILE COVERAGE")
    print("  used by the installation's own compiled code : %d" % len(covered))
    if uncovered:
        print("  NOT referenced anywhere in it                 : %d" % len(uncovered))
        for name in uncovered:
            print("    %s" % name)
        print("  A block nothing instantiates is not compiled, so a clean build says")
        print("  nothing about it. Treat these as unverified.")
    print("")
    if findings:
        print("FINDINGS (%d)" % len(findings))
        for f in findings:
            print("  %s" % f)
        print("")
        print("RESULT: the sync did more than it was supposed to - do not keep this copy")
        return 1
    print("RESULT: shared blocks updated, installation logic untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
