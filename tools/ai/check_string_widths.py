#!/usr/bin/env python3
"""Fail when a string wider than 255 is passed to a STRING(255) function.

WHY THIS EXISTS
---------------
The IEC standard string functions - LEN, LEFT, RIGHT, MID, CONCAT, FIND,
INSERT, DELETE, REPLACE - are declared over ``STRING(255)``. Hand one a
``STRING(1500)`` and CODESYS narrows the argument to its first 255 bytes on the
way in. It compiles, it raises no warning, and it returns a confident answer
about the wrong 255 bytes.

That is not a hypothetical. ``FB_BASE_MQTT_DISCOVERY_DEVICE.PublishEntityConfig``
guarded against a truncated discovery config with::

    bJsonComplete := RIGHT(sMqttJSON, 1) = '}';

on a ``STRING(1500)``. RIGHT returned character 255 - for one entity the ``i``
in ``...availability"}],"`` - so the guard rejected every config longer than 255
characters, which is all of them. The PLC published no Home Assistant discovery
config at all for as long as that line stood, and said so only in a log line
nobody was reading. Home Assistant went on showing months-old retained configs.

The compiler cannot catch this: the narrowing is a legal implicit conversion.
So it is checked here, against the committed PLCopen export, which carries both
the declared width of every string and the ST that uses it.

WHAT IT CHECKS
--------------
For every POU, method and action: any call to one of the narrowing functions
whose arguments name a string declared wider than 255. Symbolic widths
(``STRING(GVL_MQTT.MQTT_TOPIC_LEN)``) are resolved from the GVL constants in the
same export.

Scope is deliberately conservative - a method sees its own locals plus its POU's
interface - so a name that means something different in another POU cannot
produce a finding here.

USAGE
-----
    py tools/ai/check_string_widths.py                # the committed export
    py tools/ai/check_string_widths.py --xml other.xml
    py tools/ai/check_string_widths.py --list         # every wide string found

Exits non-zero on a finding. Runs on the checked-in XML, so it needs no CODESYS
and no PLC, and it belongs in CI.

If a finding is genuinely safe - the value provably never exceeds 255 - do not
widen this check. Read the end of the string through a pointer instead, the way
``F_STRIP_JSON_ROOT`` and the fixed ``PublishEntityConfig`` do. A comment saying
"this one is fine" is exactly what was believed about the line above.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

# Declared over STRING(255) in the IEC standard function library, so each one
# silently narrows a wider argument.
NARROWING = ("LEN", "LEFT", "RIGHT", "MID", "CONCAT", "FIND",
             "INSERT", "DELETE", "REPLACE")

LIMIT = 255

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_XML = os.path.join(REPO, "src", "Exports", "PLCopen.xml")


def strip_ns(tree):
    """Drop XML namespaces so tags can be matched by plain name."""
    for el in tree.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return tree


def constants(root):
    """Integer constants declared in any GVL, keyed both bare and qualified.

    A string width may be written ``STRING(GVL_MQTT.MQTT_TOPIC_LEN)``, so the
    widths cannot be compared numerically until these are resolved.
    """
    found = {}
    for gvl in root.iter("globalVars"):
        owner = ""
        parent = gvl
        for cand in root.iter():
            for child in cand:
                if child is gvl and cand.get("name"):
                    owner = cand.get("name")
        for var in gvl.iter("variable"):
            name = var.get("name")
            init = var.find("initialValue/simpleValue")
            if not name or init is None:
                continue
            value = (init.get("value") or "").strip()
            if re.fullmatch(r"[-+]?\d+", value):
                found[name] = int(value)
                if owner:
                    found["%s.%s" % (owner, name)] = int(value)
    return found


def width_of(var, consts):
    """Declared width of a string variable, or None if it is not a string.

    Returns the symbolic name unresolved rather than guessing: an unknown width
    is reported separately instead of being assumed safe.
    """
    node = var.find("type/string")
    if node is None:
        node = var.find("type/wstring")
    if node is None:
        return None
    raw = (node.get("length") or "").strip()
    if raw == "":
        return 80          # a bare STRING is STRING(80)
    if re.fullmatch(r"[-+]?\d+", raw):
        return int(raw)
    for key in (raw, raw.split(".")[-1]):
        if key in consts:
            return consts[key]
    return raw             # symbolic and unresolved


def string_vars(scope, consts):
    """name -> width, for the variables declared directly by this scope."""
    out = {}
    iface = scope.find("interface")
    if iface is None:
        return out
    for var in iface.iter("variable"):
        name = var.get("name")
        if not name:
            continue
        width = width_of(var, consts)
        if width is not None:
            out[name] = width
    return out


def body_text(scope):
    node = scope.find("body/ST/xhtml")
    if node is None:
        return ""
    return "".join(node.itertext())


def strip_comments(text):
    """Remove (* *) and // comments so a mention in prose is not a finding."""
    text = re.sub(r"\(\*.*?\*\)", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def scan(text, wide, where, findings):
    """Report each narrowing call whose arguments name a wide string."""
    code = strip_comments(text)
    for lineno, line in enumerate(code.split("\n"), 1):
        for func in NARROWING:
            for call in re.finditer(r"\b%s\s*\(" % func, line, re.I):
                # Take the argument text up to the matching close paren, or the
                # end of the line - enough to see which names are mentioned.
                depth, end = 0, len(line)
                for i in range(call.end() - 1, len(line)):
                    if line[i] == "(":
                        depth += 1
                    elif line[i] == ")":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                args = line[call.end():end]
                for name, width in wide.items():
                    if not re.search(r"\b%s\b" % re.escape(name), args):
                        continue
                    findings.append({
                        "where": where,
                        "line": lineno,
                        "func": func.upper(),
                        "var": name,
                        "width": width,
                        "code": line.strip(),
                    })


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xml", default=DEFAULT_XML, help="PLCopen export to check")
    ap.add_argument("--list", action="store_true",
                    help="list every string declared wider than %d and exit" % LIMIT)
    args = ap.parse_args()

    if not os.path.exists(args.xml):
        print("export not found: %s" % args.xml, file=sys.stderr)
        return 2

    root = strip_ns(ET.parse(args.xml)).getroot()
    consts = constants(root)

    findings, unresolved, wide_all = [], [], []

    for pou in root.iter("pou"):
        pou_name = pou.get("name") or "?"
        pou_vars = string_vars(pou, consts)

        # A method or action sees its own locals plus the POU's interface.
        scopes = [(pou_name, pou, pou_vars)]
        for kind in ("Method", "Action"):
            for member in pou.iter(kind):
                member_vars = dict(pou_vars)
                member_vars.update(string_vars(member, consts))
                scopes.append(("%s.%s" % (pou_name, member.get("name") or "?"),
                               member, member_vars))

        for where, scope, seen in scopes:
            wide = {}
            for name, width in seen.items():
                if isinstance(width, str):
                    unresolved.append((where, name, width))
                elif width > LIMIT:
                    wide[name] = width
                    wide_all.append((where, name, width))
            if wide:
                scan(body_text(scope), wide, where, findings)

    if args.list:
        for where, name, width in sorted(set(wide_all)):
            print("%-60s %-24s STRING(%d)" % (where, name, width))
        print("\n%d string(s) wider than %d" % (len(set(wide_all)), LIMIT))
        return 0

    for where, name, raw in sorted(set(unresolved)):
        print("NOTE  %s: %s has unresolved width %r - not checked"
              % (where, name, raw))

    if not findings:
        print("OK  no STRING(>%d) is passed to a STRING(%d) function (%d wide "
              "string(s) examined)" % (LIMIT, LIMIT, len(set(wide_all))))
        return 0

    print("\n%d narrowing call(s) found:\n" % len(findings))
    for f in findings:
        print("  %s line %d" % (f["where"], f["line"]))
        print("      %s" % f["code"])
        print("      %s() is STRING(%d); %s is STRING(%d) - the argument is cut "
              "to its first %d bytes"
              % (f["func"], LIMIT, f["var"], f["width"], LIMIT))
        print("")
    print("Read the string through a pointer instead - see F_STRIP_JSON_ROOT and")
    print("FB_BASE_MQTT_DISCOVERY_DEVICE.PublishEntityConfig for the pattern.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
