#!/usr/bin/env python3
"""Catch mojibake in the PLCopen export before it reaches a broker.

A CODESYS `STRING` is a byte string, and `STRUCT_TO_JSON` escapes every byte
above 0x7F as `\\u00XX`. So one source character carrying U+00B0 publishes
`\\u00B0` - a degree sign - while the two characters `Â°` publish
`\\u00C2\\u00B0`, which reads back as `Â°`. The build is clean either way and
the export looks plausible either way; the difference only shows up on the
broker, and then only as an entity Home Assistant refuses.

That is not hypothetical. Six temperature sensors and one flow control on the
DucoBox block, plus the Pt1000 block, shipped `Â°C`. Home Assistant validates
`unit_of_measurement` against `device_class`, `Â°C` is not one of the three
units a `temperature` sensor may carry, and every one of those entities was
dropped - while the PLC went on publishing perfectly good readings to a state
topic nothing was listening to.

The signature is unambiguous: U+00C2 immediately followed by another non-ASCII
character is what a UTF-8 pair looks like after a trip through CP1252. No
legitimate text here contains it.

    py tools/ai/check_export_encoding.py [path/to/PLCopen.xml]

Exits non-zero on any finding.
"""

from __future__ import annotations

import re
import sys

DEFAULT_EXPORT = "src/Exports/PLCopen.xml"

# UTF-8 lead byte for U+00C2, then any continuation - i.e. `Â` glued to the
# character that should have stood alone.
MOJIBAKE = re.compile("Â[-ÿ]")
POU = re.compile(r'<pou name="([^"]+)"')


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else DEFAULT_EXPORT
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    pou = "?"
    findings = []
    for n, line in enumerate(lines, 1):
        match = POU.search(line)
        if match:
            pou = match.group(1)
        if MOJIBAKE.search(line):
            findings.append((n, pou, line.strip()))

    for n, pou, text in findings:
        print(f"{path}:{n}: {pou}: double-encoded character: {text[:100]}")

    if findings:
        print(
            f"\n{len(findings)} line(s) carry a UTF-8 pair that was read back as "
            "CP1252. Repair them to the single character they should be - and "
            "write the replacement as a pure-ASCII \\u escape in the edits spec, "
            "because feeding UTF-8 through the wrong reader is how this got in.",
            file=sys.stderr,
        )
        return 1

    print(f"{path}: no double-encoded characters")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
