#!/usr/bin/env python3
"""Move per-instance configuration out of an init action and onto the declaration.

A sync is not finished when the project compiles. The reference does not only
change what is inside a block; it changes **how a block is configured**, and a
compiler cannot notice that an installation is still using the old way. The old
way keeps working - that is the point of a backwards-compatible refactor - so
the installation quietly stays on it forever.

The case this handles is the self-wiring one. A block that

  * declares a `FriendlyName` input, and
  * carries the self-wiring prologue in its body

configures itself from the declaration site: set `FriendlyName` and on its first
cyclic call it reaches into `MqttVariables` for its queue, prefixes and collector
and announces itself to Home Assistant. The `InitMqtt` / `InitMqttDiscovery*`
calls in the installation's init action become dead weight that says the same
thing in thirty lines.

This script finds every instance still doing it the old way and writes the edits
that move it, preserving exactly what the old calls said:

  * the friendly name comes from the existing `Name :=` argument, never from a
    trailing comment - `FB_DO_LIGHT_005` is commented `// Hall` and announces
    as `'Landing'`, and the comment is the wrong one to believe;
  * `InitMqttDiscoveryAsLight` becomes `EntityType := E_MQTT_ENTITY.Light`, so a
    block announced as something other than its own default keeps announcing as
    that. Getting this wrong orphans the retained discovery topic and creates a
    second entity in Home Assistant, which no build can catch.

    py plan_declaration_migration.py --implementation .ai/sync/before.json \
       --out .ai/sync/edits/migrations.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_sync import device_names, index_by_name, source_of  # noqa: E402

PROLOGUE_MARKER = "self-wiring prologue"
# `InitMqttDiscoveryAsLight` -> `Light`; bare `InitMqttDiscovery` -> no EntityType.
DISCOVERY_CALL = re.compile(
    r"(?<![A-Za-z0-9_])(\w+)\s*\.\s*InitMqttDiscovery(?:As(\w+))?\s*\(", re.IGNORECASE)
INIT_CALL = re.compile(r"(?<![A-Za-z0-9_])(\w+)\s*\.\s*InitMqtt\s*\(", re.IGNORECASE)
NAME_ARG = re.compile(r"(?<![A-Za-z0-9_])Name\s*:=\s*'([^']*)'", re.IGNORECASE)


def load(path: str) -> dict[str, Any]:
    with io.open(path, encoding="utf-8") as handle:
        return json.load(handle)


EXTENDS = re.compile(r"\bEXTENDS\s+([A-Za-z_]\w*)", re.IGNORECASE)


def declares_friendly_name(name: str, objects: dict[str, Any], depth: int = 0) -> bool:
    """Does this block, or anything it EXTENDS, declare the FriendlyName input?

    Walking the chain is the whole point: `FriendlyName` is declared once on
    `FB_MQTT_BASE` and inherited by every block that extends it, so looking only
    at a derived block's own declaration finds nothing and the migration
    concludes there is nothing to do.
    """
    obj = objects.get(name)
    if obj is None or depth > 8:
        return False
    decl = obj.get("decl") or ""
    if "FriendlyName" in decl:
        return True
    base = EXTENDS.search(decl)
    return bool(base) and declares_friendly_name(base.group(1), objects, depth + 1)


def self_wiring_types(objects: dict[str, Any]) -> set[str]:
    """Blocks that can be configured from their declaration.

    Both halves are required. The prologue is the mechanism; the inherited
    `FriendlyName` input is the switch that arms it. A block with one and not
    the other is a half-finished refactor in the reference, not something to
    migrate an installation onto.
    """
    return {
        name for name, obj in objects.items()
        if PROLOGUE_MARKER in (obj.get("impl") or "") and declares_friendly_name(name, objects)
    }


def call_span(text: str, start: int) -> tuple[int, int]:
    """Extent of a `foo.Bar( ... );` statement beginning at `start`.

    Counts brackets rather than searching for the first `)`, because these calls
    span many lines and every one of them carries `(* ... *)` comments.
    """
    depth = 0
    i = text.index("(", start)
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    end = i + 1
    while end < len(text) and text[end] in " \t":
        end += 1
    if end < len(text) and text[end] == ";":
        end += 1
    # Swallow the blank line the statement sits on, so removing it does not
    # leave a growing stack of empty lines behind.
    while end < len(text) and text[end] in "\r\n":
        end += 1
        if end < len(text) and text[end - 1] == "\n":
            break
    return start, end


def instance_declarations(decl: str, types: set[str]) -> dict[str, dict[str, Any]]:
    """instance name -> {type, line, has_initialiser} for every instance of `types`."""
    found: dict[str, dict[str, Any]] = {}
    for line in decl.splitlines():
        match = re.match(r"\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*(\(|:=|;)", line)
        if not match:
            continue
        instance, type_name = match.group(1), match.group(2)
        if type_name not in types:
            continue
        found[instance] = {
            "type": type_name,
            "line": line,
            "has_initialiser": ":= (" in line.replace(":=(", ":= ("),
        }
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation", required=True, help="info -Full report of the implementation")
    parser.add_argument("--out", help="write the edits here (migrations.json format)")
    parser.add_argument("--init-action", default="MAIN_INIT",
                        help="the action holding the init calls (default MAIN_INIT)")
    args = parser.parse_args()

    impl = load(args.implementation)
    objects, _ = index_by_name(impl)
    devices = device_names(impl)
    types = self_wiring_types(objects)
    if not types:
        print("No self-wiring blocks found. Either the sync has not run yet, or the")
        print("reference does not use this pattern. Nothing to migrate.")
        return 0

    edits: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    skipped: list[str] = []

    for prog_name, prog in sorted(objects.items()):
        if prog.get("top") not in devices or prog.get("kind") != "PROGRAM":
            continue
        action = None
        for member in prog.get("members") or []:
            if member["name"].upper() == args.init_action.upper():
                action = member
        if action is None or not action.get("impl"):
            continue
        body = action["impl"]
        instances = instance_declarations(prog.get("decl") or "", types)
        if not instances:
            continue

        # Which instances does the rest of this program call cyclically? A
        # self-wired block that is never called never wires itself, so moving it
        # would silently remove it from Home Assistant. Refuse those.
        cyclic = "\n".join(
            m.get("impl") or "" for m in (prog.get("members") or [])
            if m["name"].upper() != args.init_action.upper()
        )

        replacements: list[dict[str, Any]] = []
        decl_rules: list[dict[str, Any]] = []

        for match in DISCOVERY_CALL.finditer(body):
            instance, variant = match.group(1), match.group(2)
            info = instances.get(instance)
            if info is None:
                continue
            start, end = call_span(body, match.start())
            statement = body[start:end]
            name_match = NAME_ARG.search(statement)
            if not name_match:
                skipped.append("%s: no Name argument in its discovery call" % instance)
                continue
            friendly = name_match.group(1)
            if not re.search(r"(?<![A-Za-z0-9_])%s\s*\(" % re.escape(instance), cyclic):
                skipped.append("%s: never called cyclically - self-wiring would "
                               "silently unwire it" % instance)
                continue
            if info["has_initialiser"]:
                skipped.append("%s: declaration already has an initialiser" % instance)
                continue

            initialiser = "FriendlyName := '%s'" % friendly
            if variant:
                initialiser += ", EntityType := E_MQTT_ENTITY.%s" % variant

            old_line = info["line"]
            # Insert `:= (...)` before the trailing `;`, keeping any FB_init
            # argument list and any trailing comment exactly where they are.
            semicolon = old_line.index(";")
            new_line = "%s := (%s)%s" % (old_line[:semicolon], initialiser, old_line[semicolon:])
            decl_rules.append({"find": old_line, "with": new_line, "count": 1})

            replacements.append({"find": statement, "with": "", "count": 1})
            rows.append({
                "program": prog_name, "instance": instance, "type": info["type"],
                "friendly_name": friendly,
                "entity_type": ("E_MQTT_ENTITY.%s" % variant) if variant else "(default)",
            })

            # The paired InitMqtt call for the same instance goes too.
            for init in INIT_CALL.finditer(body):
                if init.group(1) != instance:
                    continue
                i_start, i_end = call_span(body, init.start())
                replacements.append({"find": body[i_start:i_end], "with": "", "count": 1})

        if decl_rules:
            edits.append({"pou": prog_name, "replace_in_decl": decl_rules})
        if replacements:
            edits.append({"pou": prog_name, "member": action["name"],
                          "replace_in_body": replacements})
            # Deleting thirty statements out of an action leaves the blank lines
            # that separated them, so what remains is mostly whitespace. Collapse
            # runs of blank lines, computed against the body that WILL exist
            # after the deletions above.
            remaining = body
            for rule in replacements:
                remaining = remaining.replace(rule["find"], rule["with"], 1)
            tidied = re.sub(r"\n{3,}", "\n\n", remaining).strip() + "\n"
            if tidied != remaining:
                edits.append({"pou": prog_name, "member": action["name"],
                              "body_replace": tidied})
                print("note: %s.%s will also have its blank runs collapsed. The section"
                      % (prog_name, action["name"]))
                print("      comments that used to head each deleted block are left in")
                print("      place - read the result and tidy them by hand.")

    print("SELF-WIRING BLOCK TYPES (%d): %s" % (len(types), ", ".join(sorted(types))))
    print("")
    print("INSTANCES TO MOVE ONTO THEIR DECLARATION (%d)" % len(rows))
    for row in rows:
        print("  %-18s %-32s %-24s %s"
              % (row["instance"], row["type"], "'%s'" % row["friendly_name"], row["entity_type"]))
    if skipped:
        print("")
        print("LEFT AS EXPLICIT CALLS (%d)" % len(skipped))
        for note in skipped:
            print("  %s" % note)
    print("")

    if args.out:
        parent = os.path.dirname(os.path.abspath(args.out))
        if not os.path.isdir(parent):
            os.makedirs(parent)
        existing = []
        if os.path.isfile(args.out):
            existing = load(args.out).get("edits", [])
            print("note: %s already had %d edit(s); they are kept and these are appended."
                  % (args.out, len(existing)))
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"edits": existing + edits}, indent=2, ensure_ascii=False) + "\n")
        print("edits written to %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
