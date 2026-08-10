#!/usr/bin/env python3
"""Generate IEC-style function block diagrams into the FunctionBlocks docs.

The diagrams are derived from src/Exports/PLCopen.xml, the PLCopen export of
the CODESYS project, so a block diagram can never drift from the code that
defines it. Each doc carries a generated region:

    <!-- fb-diagram:start -->
    ```text
    ...box...
    ```
    <!-- fb-diagram:end -->

Everything outside those markers is left untouched.

Usage:
    python3 gen_fb_diagrams.py            # rewrite the generated regions
    python3 gen_fb_diagrams.py --check    # exit 1 if any doc is out of date
    python3 gen_fb_diagrams.py --print FB_NAME [...]   # dump to stdout
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
EXPORT = REPO / "src" / "Exports" / "PLCopen.xml"
DOCS = REPO / "docs" / "FunctionBlocks"

START = "<!-- fb-diagram:start -->"
END = "<!-- fb-diagram:end -->"

# A method is <Method name="..."> nested in <addData>. Its parameters are NOT
# function block pins, so the interface scan must stop at the first one.
_METHOD = re.compile(r"<(?:Method|Action)\s+name=")
_VAR = re.compile(
    r'<variable name="([^"]+)">\s*<type>\s*(?:<derived name="([^"]+)"|<(\w+))'
)


def load_export() -> str:
    if not EXPORT.exists():
        sys.exit(f"error: {EXPORT} not found. Re-export the project first.")
    return EXPORT.read_text(encoding="utf-8", errors="replace")


def interface(xml: str, name: str):
    """Return the FB's own VAR_INPUT / VAR_OUTPUT / VAR_IN_OUT, or None."""
    i = xml.find(f'<pou name="{name}"')
    if i < 0:
        return None
    j = xml.find("<pou name=", i + 10)
    body = xml[i:(j if j > 0 else len(xml))]
    cut = min([m.start() for m in _METHOD.finditer(body)] or [len(body)])
    body = body[:cut]
    out = {}
    for section in ("inputVars", "outputVars", "inOutVars"):
        m = re.search(rf"<{section}>(.*?)</{section}>", body, re.S)
        out[section] = [
            (v.group(1), (v.group(2) or v.group(3) or "").upper())
            for v in _VAR.finditer(m.group(1))
        ] if m else []
    return out


def render(name: str, ifc) -> str:
    """Draw the block: pin names inside the box, datatypes on the outside."""
    ins = ifc["inputVars"] + ifc["inOutVars"]
    outs = ifc["outputVars"]
    lt = max([len(t) for _, t in ins] + [0])
    rt = max([len(t) for _, t in outs] + [0])
    ln = max([len(n) for n, _ in ins] + [0])
    rn = max([len(n) for n, _ in outs] + [0])
    inner = max(len(name) + 2, ln + rn + 5)
    gap = inner - ln - rn - 2
    # An input stub renders as "<type> ──┤" (lt + 4 chars), putting the wall on
    # column lt + 3; the header lines must start at the same offset.
    pad = " " * (lt + 3)
    lines = [
        pad + "┌" + "─" * inner + "┐",
        pad + "│" + name.center(inner) + "│",
        pad + "├" + "─" * inner + "┤",
    ]
    for k in range(max(len(ins), len(outs))):
        n_i, t_i = ins[k] if k < len(ins) else ("", "")
        n_o, t_o = outs[k] if k < len(outs) else ("", "")
        lead = (t_i.rjust(lt) + " ──┤") if n_i else (" " * (lt + 3) + "│")
        tail = ("├── " + t_o) if n_o else "│"
        lines.append(
            f"{lead} {n_i.ljust(ln)}{' ' * gap}{n_o.rjust(rn)} {tail}".rstrip()
        )
    lines.append(pad + "└" + "─" * inner + "┘")
    return "\n".join(lines)


def block(name: str, ifc) -> str:
    return f"{START}\n```text\n{render(name, ifc)}\n```\n{END}"


def splice(text: str, new_block: str) -> str | None:
    """Replace the generated region, or the legacy <img> if not yet migrated."""
    if START in text and END in text:
        return re.sub(
            re.escape(START) + r".*?" + re.escape(END), lambda _: new_block, text, flags=re.S
        )
    # First run: swap the hand-drawn SVG under "### **Block diagram**".
    # Match only the tag line — trailing \s* would eat the blank line that
    # separates the diagram from the next paragraph.
    img = re.search(r'^<img src="\.\./_img/FB_[A-Z0-9_]+\.svg"[^>]*>[ \t]*$', text, re.M)
    if img:
        return text[:img.start()] + new_block + text[img.end():]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify, do not write")
    ap.add_argument("--print", nargs="+", metavar="FB", help="print blocks to stdout")
    args = ap.parse_args()
    xml = load_export()

    if args.print:
        for name in args.print:
            ifc = interface(xml, name)
            if ifc is None:
                print(f"!! {name}: no such POU in the export")
                continue
            print(render(name, ifc), end="\n\n")
        return 0

    stale, wrote, skipped = [], [], []
    for doc in sorted(DOCS.glob("FB_*.md")):
        name = doc.stem
        ifc = interface(xml, name)
        if ifc is None or not any(ifc.values()):
            skipped.append(name)          # no pins: nothing to draw
            continue
        text = doc.read_text(encoding="utf-8")
        updated = splice(text, block(name, ifc))
        if updated is None:
            skipped.append(f"{name} (no diagram anchor)")
            continue
        if updated == text:
            continue
        if args.check:
            stale.append(name)
        else:
            doc.write_text(updated, encoding="utf-8")
            wrote.append(name)

    if args.check:
        if stale:
            print("Out of date with " + str(EXPORT.relative_to(REPO)) + ":")
            for s in stale:
                print("  -", s)
            print("\nRun: python3 " + str(pathlib.Path(__file__).relative_to(REPO)))
            return 1
        print("All function block diagrams match the export.")
        return 0

    print(f"updated {len(wrote)} diagram(s)")
    for w in wrote:
        print("  -", w)
    if skipped:
        print(f"skipped {len(skipped)}: {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
