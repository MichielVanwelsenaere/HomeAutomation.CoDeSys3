---
name: update-fb-docs
description: Regenerate the machine-owned parts of the function block docs from the PLCopen export, scaffold a page for a new function block, and check whether the docs still match the code. Use when a function block's inputs, outputs or methods change, when src/Exports/PLCopen.xml is re-exported, when a new function block is added, when a doc page looks wrong or out of date, or when asked to verify that the docs agree with the CODESYS project.
---

# Update function block docs

The mechanical parts of `docs/FunctionBlocks/*.md` are **generated** from
`src/Exports/PLCopen.xml`, so they cannot drift from the code they document.
Two regions per page are machine-owned — never hand-edit inside them:

    <!-- fb-badge:start -->      the MQTT Discovery badge, if the block has one
    <!-- fb-badge:end -->

    <!-- fb-interface:start -->  block diagram, inputs, outputs, methods
    <!-- fb-interface:end -->

`docs/AdditionalFunctionality/MQTT_General.md` has a third, `<!-- gvl:start -->`,
holding the `MqttVariables` global variable list.

Everything else — General, callouts, MQTT behaviour tables, code examples,
wiring — is hand-written and left alone.

## Commands

Run from the repo root:

| Task | Command |
|:--|:--|
| Regenerate everything | `python3 .claude/skills/update-fb-docs/scripts/gen_fb_docs.py` |
| Check without writing | `python3 .claude/skills/update-fb-docs/scripts/gen_fb_docs.py --check` |
| Scaffold a new page | `python3 .claude/skills/update-fb-docs/scripts/gen_fb_docs.py --new FB_NAME` |
| Preview one block | `python3 .claude/skills/update-fb-docs/scripts/gen_fb_docs.py --print FB_NAME` |

`--check` exits non-zero and names what is stale. Use it to answer "do the docs
still match the code?" without touching the working tree.

## Where descriptions live

Only 2% of pins carry `<documentation>` in the export, so descriptions cannot be
generated. **The generated region is their store.** Each run rebuilds the
structure from the export and carries existing descriptions across by name:

- a pin or parameter that gains a description keeps it across regenerations
- one that disappears from the code takes its description with it
- a new one arrives as `_TODO: describe this._`, so gaps are obvious

Two mechanisms cut the amount of hand-writing, both in the script:

- **`GLOSSARY`** — descriptions for things that mean the same on every block
  (`pMqttPublishQueue`, `Device`, `Invert`, `DeviceClass`…). A page-specific
  description always wins. This is why a **new** function block is already
  documented for all its standard MQTT plumbing the moment it is scaffolded.
  Key an entry `Method.param` to scope it, or `param` to apply anywhere.
- **Wildcards** — a trailing number is matched by `*`, so one `VALVE_*` entry
  covers `VALVE_1` … `VALVE_8`.

## Workflow

1. **Confirm the export is current.** The script reads `PLCopen.xml`, not the
   `.project` binary. If someone changed a block in CODESYS without re-exporting,
   the output reflects the *export*:

   `git log -1 --format=%cd -- src/Exports/PLCopen.xml src/HomeAutomation.project`

   If the export is behind, say so and stop — regenerating would bake in stale
   pins. Re-exporting is a manual CODESYS step (see `docs/CONTRIBUTING.md`).

2. **Run the generator**, or `--check` first if only a report is wanted.

3. **Deal with what it reports.**
   - `MISSING DESCRIPTIONS` — write them, or add the term to `GLOSSARY` if it
     recurs across blocks.
   - `ORPHANED` — a page has a generated region for a block no longer in the
     export. Establish which happened before advising: a deliberate removal, or
     an export taken without the block. Check whether the call sites still
     reference it — a declared instance points at a bad export, commented-out
     call sites point at a real removal. Nothing is deleted automatically.
   - `HA YAML on a discovery-capable block` — blocks that publish discovery
     configs do not need the hand-written YAML fallback; it is schema-volatile
     and drifts. Remove the `### **Home Assistant YAML**` section.

4. **Verify.** Re-run with `--check`; it should pass. Confirm nothing outside
   the markers moved: `git diff -- docs/`.

## Adding a new function block

```
python3 .claude/skills/update-fb-docs/scripts/gen_fb_docs.py --new FB_NEW_THING
```

This writes a complete page: badge, block diagram, interface tables and method
tables, with standard parameters already described from the glossary. Fill in
the General section, the code example, and any remaining `_TODO_` rows.

## Deciding what is public

The export carries no access specifier, so "public API" and "implementation
detail" cannot be told apart automatically. Internal helpers are listed in
`HIDDEN_METHODS` in the script. A **new** method is deliberately not hidden by
default — it appears with a TODO so the author has to decide: describe it, or
add it to `HIDDEN_METHODS` with a comment saying why.

## What the generator does not touch

- Pages for blocks not in the export, such as the archived
  `FB_OUTPUT_DIMMER_DALI_MQTT` — it reports them and leaves them alone.
- Wiring diagrams, which are real drawings in `docs/_drawio/`.
- The Home Assistant YAML fallback on blocks **without** discovery support
  (the virtual and RS485 blocks), which genuinely need it.
