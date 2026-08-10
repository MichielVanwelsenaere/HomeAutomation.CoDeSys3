---
name: update-fb-diagrams
description: Regenerate the function block diagrams in docs/FunctionBlocks/ from the PLCopen export, and check whether the docs still match the code. Use when a function block's inputs or outputs change, when src/Exports/PLCopen.xml is re-exported, when a block diagram looks wrong or out of date, or when asked to verify that the docs agree with the CODESYS project.
---

# Update function block diagrams

Block diagrams in `docs/FunctionBlocks/*.md` are **generated**, not drawn. The
source of truth is `src/Exports/PLCopen.xml` — the PLCopen export of the
CODESYS project — so a diagram cannot silently drift from the function block
it documents.

Each doc contains a generated region. Never hand-edit inside it:

    <!-- fb-diagram:start -->
    ```text
    ...the box...
    ```
    <!-- fb-diagram:end -->

## Commands

Run from the repo root:

| Task | Command |
|:--|:--|
| Regenerate every diagram | `python3 .claude/skills/update-fb-diagrams/scripts/gen_fb_diagrams.py` |
| Check without writing | `python3 .claude/skills/update-fb-diagrams/scripts/gen_fb_diagrams.py --check` |
| Preview one block | `python3 .claude/skills/update-fb-diagrams/scripts/gen_fb_diagrams.py --print FB_NAME` |

`--check` exits non-zero and names the stale docs. Use it to answer "do the
docs still match the code?" without touching the working tree.

## Workflow

1. **Confirm the export is current.** The script reads `PLCopen.xml`, not the
   `.project` binary. If someone changed a function block in CODESYS but did
   not re-export, the generated diagram reflects the *export*, not their
   change. Check whether `src/Exports/PLCopen.xml` is older than
   `src/HomeAutomation.project`:

   `git log -1 --format=%cd -- src/Exports/PLCopen.xml src/HomeAutomation.project`

   If the export is behind, say so and stop — regenerating would bake in stale
   pins. Re-exporting is a manual CODESYS step (see `docs/CONTRIBUTING.md`).

2. **Run the generator** (or `--check` first if the user only wants a report).

3. **Report what changed, and why.** A changed diagram means the documented
   interface disagreed with the code. Do not present it as cosmetic — show the
   pin that appeared, vanished, or was renamed, and flag it: either the code
   changed and the docs lagged, or the diagram was wrong to begin with.

4. **Verify.** Re-run with `--check`; it should pass. Confirm no file outside
   the markers changed: `git diff -- docs/FunctionBlocks/`.

## What the script does and does not touch

- Draws pin **names inside** the box and **datatypes outside**, IEC style.
- Reads only the function block's own `VAR_INPUT` / `VAR_OUTPUT` /
  `VAR_IN_OUT`. Method parameters are deliberately excluded — in the export a
  method is `<Method name="...">` nested inside `<addData>`, and its inputs are
  not pins. Document methods in the `METHOD(S)` prose instead.
- Skips function blocks with no pins (`FB_MQTT_LOG`,
  `FB_PLC_MQTT_DISCOVERY_DEVICE`) — they get no diagram.
- Leaves every other part of the markdown alone, including the wiring diagrams,
  which are real drawings kept in `docs/_drawio/` and exported to
  `docs/_img/`.

## Adding a new function block

Create `docs/FunctionBlocks/FB_NEW_THING.md`, add the two marker lines where
the diagram belongs (under `### **Block diagram**`), then run the generator. On
a doc that still has a legacy `<img src="../_img/FB_*.svg">` the script
replaces that image with the markers automatically.
