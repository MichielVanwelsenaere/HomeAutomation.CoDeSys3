# CLAUDE.md

Guidance for AI agents writing anything under `docs/`.

## A page describes the current state. Never the history.

Write what the code does **now**. Do not write what it used to do, what changed,
what an earlier version published, or what a value defaulted to before. This is
not a style preference — a reader cannot tell which half of a sentence is still
true, so every historical aside makes the page harder to trust than no page at
all, and it rots on the next change.

Phrases that mean the sentence has to be rewritten:

    it used to …            an earlier version …        previously …
    this changed …          no longer …                 as it did before …
    still works as before   was renamed to …            now announces …

The last one is the trap, because it reads as present tense. "It **now**
announces two entities" is a comparison with a past nobody can see; "It announces
two entities" is the fact.

The same applies to *reasons*: "state_class is empty because the old one produced
meaningless statistics" is history. "state_class is empty: this is a control
position, not a measurement, and a mean of it means nothing" is the reason,
stated from the present.

## Where the history goes instead

It is already recorded, in places built for it and dated:

| What | Where |
|:--|:--|
| what changed and why | the commit message |
| what a consumer has to do about it | the pull request description |
| when, and by whom | `git log`, `git blame` |
| a trap that will otherwise be re-hit in code | a comment at the code, or the root `CLAUDE.md` |

A **breaking change** is the case that tempts hardest, because it feels like the
reader must be warned. Warn them in the PR description, which is what people read
when they merge. The page gets the new behaviour, stated plainly — including
whatever a consumer now has to do — with no account of what it replaced. A rule
of thumb: if someone reading the page had never seen the old version, would the
sentence still earn its place? If not, it belongs in the PR.

## What this does not forbid

- **Rationale.** Why a design is the way it is, argued from how things are today,
  is the most valuable thing on most of these pages. Keep it.
- **Naming a limitation.** "A front end frozen at a believable temperature cannot
  be detected" is current state, not history.
- **Pointing at the alternative.** "`FB_OUTPUT_DIMMER_MQTT` is the block to reach
  for when Home Assistant must set the level" is current state too.
- **Genuinely dated facts**, where the date is the point: a device description
  version, a Home Assistant release that introduced a device class, a firmware
  requirement.

## Generated regions

`docs/FunctionBlocks/*.md` and `docs/AdditionalFunctionality/MQTT_General.md`
carry machine-owned regions between `<!-- fb-badge -->`, `<!-- fb-interface -->`
and `<!-- gvl -->` markers. Never hand-edit their structure — regenerate with the
`update-fb-docs` skill. Pin and parameter **descriptions** do live inside those
regions, and are carried across regenerations by name, so that is where to write
them.
