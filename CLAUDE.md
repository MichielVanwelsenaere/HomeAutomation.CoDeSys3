# CLAUDE.md

Guidance for AI agents working in this repository.

## What this project is

A CODESYS 3.5 (SP21) home-automation PLC project for WAGO PFC100/200 controllers.
Critical logic runs in the PLC; MQTT carries events out to a broker and commands
back in. `README.md` is the user-facing entry point; `docs/SoftwareArchitecture.md`
explains the layering. Function blocks are documented one per page under
`docs/FunctionBlocks/`.

| Path | What it is |
|:--|:--|
| `src/HomeAutomation.project` | The real project. A **binary** CODESYS file. |
| `src/Exports/PLCopen.xml` | Generated PLCopen XML export of all IEC content. Readable. |
| `src/Libraries/` | Vendored `.library` dependencies (MQTT, OSCAT, PRO_JSON). |
| `tools/ai/` | Headless CODESYS driver. |
| `.ai/` | Gitignored scratch: candidate blocks, sandbox copy, compiler reports. |

This project is the **reference**. Real buildings run separate *installation*
projects that reuse its function blocks but own their own logic, I/O and device
tree. `sync-implementation-project` is how one of those catches up; nothing in
this repository ever downloads to a building's PLC.

## The core constraint

`src/HomeAutomation.project` is a binary. It cannot be read, diffed or edited as
text. The way in and out is **PLCopen XML**, which CODESYS both exports and
imports — and since CODESYS ships a ScriptEngine and runs headless with `--noUI`,
the real compiler can check the result rather than you having to guess from the
XML.

## Skills — use them, don't improvise

| Task | Skill |
|:--|:--|
| Add or change a function block, refactor ST, check that something compiles, re-export the PLCopen XML, inspect the project structure | **`codesys-loop`** |
| Rename an object or a variable, with every reference to it | **`codesys-loop`** (the `rename` task) |
| Regenerate or check the generated regions of `docs/FunctionBlocks/*.md` | **`update-fb-docs`** |
| Check whether the logic actually *works* — lights, pushbuttons, covers, HVAC — on a real PLC | **`test-plc-logic`** |
| Bring a real building's installation project up to this project's function blocks, or check whether it is still version-compatible | **`sync-implementation-project`** |

**Naming is decided, not open.** Objects are `PREFIX_` + SCREAMING_SNAKE (`FB_`,
`F_`, `PRG_`, `I_`, `E_`, `ST_`, `A_`, `GVL_`); variables are a type prefix plus
PascalCase, with `b` for BOOL and `by` for BYTE per the CODESYS guide. The one
exemption is the `MQTT_DISCOVERY_*` structs, whose member names are published as
Home Assistant discovery keys. Do not re-derive any of this from the surrounding
code: [`docs/CodingStyle.md`](docs/CodingStyle.md) is the full version and
[`src/CLAUDE.md`](src/CLAUDE.md) the working summary, loaded automatically when
you edit the project.

Two things worth knowing before you start, both covered in detail by
`codesys-loop`:

- Run `./tools/ai/codesys.ps1 doctor` to check the toolchain.

  | Dependency | Needed by | Notes |
  |:--|:--|:--|
  | CODESYS 3.5 SP21 (3.5.21.30) + PFC200 SL package | everything | No licence needed for `--noUI` scripting. |
  | WAGO Device Support Package 2.0.8.9 | the build itself, since the DALI block landed | Supplies `WagoAppDALI`. **Not vendored** — WAGO's licence forbids redistributing it, so it is installed per machine: `docs/WagoPfcPrep.md#installing-the-wago-libraries-dali`. The version is pinned to the CODESYS patch level. |
  | Python 3.12 | `update-fb-docs` only | **Installed** at `C:\Program Files\Python312-arm64`. Invoke it as **`py`**. |
  | mosquitto clients | `Mqtt-Snapshot.ps1` and `check_mqtt_discovery.py` — the runtime checks | Not on `PATH`; the tooling also looks in `C:\Program Files\mosquitto`. |

  **Trust `doctor`, not a bare `python3`.** Windows ships an App Execution Alias
  stub at `WindowsApps\python3.exe` that prints *"Python was not found; run
  without arguments to install from the Microsoft Store"* and exits non-zero
  **even when Python is installed** — the python.org build provides `python.exe`
  and the `py` launcher but no `python3.exe`. `doctor` already skips anything
  under `WindowsApps`, so it reports the truth; a bare `python3 --version` does
  not. That stub is why this file used to claim Python was missing when it had
  been installed for days, and why a whole branch of docs got hand-maintained for
  no reason.
- A successful build does **not** always mean your code was checked — an
  unreferenced POU is never compiled. Read the `harness` section of the verify
  report, not just the result line.

Anything that writes `src/HomeAutomation.project`, `src/Exports/PLCopen.xml` or
`docs/` changes tracked files, one of them binary. Ask before landing those
unless the user has already said to.

## Options that were considered, tried and rejected

For the record, so this is not relitigated:

- **PLCopen XML as the only feedback channel** (generate XML, reason about it,
  never compile). Strictly worse than compiling: it cannot catch a type error, a
  missing library symbol, or a wrong `FB_init` signature. It is the fallback for
  when CODESYS is unavailable, not the mechanism.
- **An offline IEC 61131-3 compiler** (`matiec`, RuSTy) as a fast type-checker.
  Neither implements the CODESYS OO extensions this project leans on throughout
  — methods, `FB_init`, `EXTENDS`, references — and neither can see inside the
  vendored `.library` binaries. It would disagree with the real compiler exactly
  where the code is interesting.
- **A hand-written PLCopen linter** for a sub-second check before the ~60-second
  compile. It duplicates the compiler with a weaker model of the language, and
  the real compile is fast enough for an agent loop.
- **Editing ST through `textual_declaration` / `textual_implementation`** instead
  of importing XML. These work and suit surgical edits, but XML candidates are
  reviewable as files and survive a failed run, so they are the default. The
  verify harness does use the textual API.

- **Editing an SFC chart from a script, by any route.** `PRG_MAIN` is SFC and
  its chart cannot be touched: the object has a `textual_declaration` but **no
  `textual_implementation` at all** (`AttributeError` on access), so
  `replace_in_body` is out. Re-importing the POU as XML does not work either — a
  candidate file carries no folder structure, so the import files a *second*
  `PRG_MAIN` at the project root and leaves the real one in `PRG's/` alone.
  `import_conflict: "replace"` does not save it, because at the root there is
  nothing to conflict with; and the root copy is never compiled, since a program
  is only compiled where a task calls it. So the build stays green while the
  refactor has done nothing.

  Consequence: an action can be emptied from a script but **not removed**, because
  the step's action association is compiled and the name has to keep resolving —
  deleting the action alone fails with `Identifier 'X' not defined <... Action
  association X / Main (Impl)>`. Leave the action as a stub with a comment saying
  what to delete by hand.

  **Order matters when someone does it by hand**, and the obvious order is the
  wrong one: delete the association box from the step's action list *first*, then
  the action. Deleting the action first leaves a project that does not build, with
  no hint in the chart that anything is missing. `PRG_MAIN.PROCESS_VIRTUAL` was
  retired this way and is gone; that program's chart is the worked example.

## An instance's `FB_init` arguments live outside the declaration text

**Changing an existing `FB_init` argument from a script does not work, and looks
like it did.** This is the nastiest trap found in this project so far, because every
check you would normally trust agrees with you and the PLC still runs the old value.

CODESYS stores an instance's `FB_init` arguments in a separate structure —
`<addData>` → `plcopenxml/inputassignments` → `<InputAssignment><Value>` — and **the
compiler reads that, not the declaration text.** `textual_declaration.replace()`
updates the text only. So:

| | says |
|:--|:--|
| declaration text (what you edited, what a human reads) | `FB_HVAC_COLLECTOR_MQTT(T#5S)` |
| `InputAssignments` (what the compiler reads) | `TIME#3m0s0ms` |
| the running PLC | `TIME#3m` |

`apply` reported four successful replacements; **none** of the four reached the
compiler. The build was clean, `NEW vs baseline: 0`, and a plaintext export shows
the new values — because it serialises the text.

Adding arguments to an instance that had **none** does work: there is no stale
metadata to win, so CODESYS parses the text. That is why the cover's
`FB_OUTPUT_COVER_MQTT(T#1S, T#20S)` landed correctly and is in `InputAssignments`,
while changing the collector's existing `T#3M` did not.

There is no scripting API for `InputAssignments` — nothing in the ScriptEngine stubs
touches it — so this cannot be fixed in the harness. `apply` and `verify` now print
an **ADVISORY** whenever a `replace_in_decl` changes an argument list, because the
only available defence is refusing to let it pass in silence.

Three ways to actually change one:

1. **In the IDE.** Same class of blind spot as an SFC chart.
2. **Write the member at runtime**, which is right for anything test-only — see
   `hvac-fast-chain.json` in the `test-plc-logic` skill. It also keeps the
   production values in source, so short bench timings cannot be shipped by
   accident.
3. **Don't put tunable values in `FB_init` arguments.** Read them from a GVL
   constant inside the block instead; a GVL declaration is ordinary text with no
   input assignments behind it.

Ruled out along the way, so nobody re-tests them: it is not an online change
(`OnlineChangeOption.Never` is documented as forcing a full download), and it is not
`FB_init` failing to re-run (`download` now does a `reset(ResetOption.Cold)` and
reports `cold reset : True`; the value did not budge). The cold reset was kept
anyway — it makes a download an unambiguous fresh start, which is worth having on
its own.

## `verify` passes and `apply` fails: delete the precompile cache

**Not an editing problem at all, and it looks exactly like one.** `verify` copies
the project to `.ai/work` and builds the copy, alone in an empty folder. `apply`
builds the real project **in place**, where CODESYS keeps
`<name>_project.precompilecache` beside it — and that cache can serve a stale
compiled interface for a block whose declaration the same run just changed.

The symptom is an error describing code that no longer exists anywhere:

    'Invert' is no valid assignment target                          x3
    Identifier 'Invert' not defined                                 x3
    <Wago_G1_Annex/Plc Logic/HomeAutomation/PRG's/PLC_PRG_MAIN>

after a run that had already rewritten every `Invert` to `RelayType`, in a project
whose source contained the string `Invert` only inside a comment. Deleting
`SiteA_project.precompilecache` and re-running the identical spec built
clean and saved.

Three hours went into the wrong theory first, so it is written down: the same six
errors survived `replace_in_decl` per line, a whole-declaration `decl_replace`,
**and** a `decl_replace` that deleted the initialiser outright — which reads as
overwhelming evidence that a structured initialiser `:= (Name := ...)` is stored
outside the text like an `FB_init` argument list. It is not. Every one of those
runs simply hit the same stale cache. What actually proved it was a `verify
-Baseline` on the untouched project: `ok=True`, no errors. A project that builds
clean untouched, and fails an edit-free `apply`, is telling you the difference is
the folder, not the edit.

`do_apply` now clears the cache and rebuilds once when the first build fails, and
reports `precompile cache cleared, rebuilt` when it does. If that line appears,
nothing was wrong with the edit.

Related, and the reason this was so easy to misdiagnose: `apply` refuses to save a
project that does not build, so all of those failed runs left the project
untouched and correct. The guard works. It also means a wrong theory costs nothing
but time.

**Do not let this section talk you out of the next one.** Having found the cache,
this file briefly claimed the structured-initialiser trap below was *not* real.
That was an over-correction and it was wrong. The two are separate faults with
opposite symptoms, and both happen:

| | cache | structValue |
|:--|:--|:--|
| build | **fails**, citing an identifier the source no longer contains | **succeeds** |
| save | refused | succeeds, `saved=True` |
| what changed | nothing (guard held) | the text only |

## A structured initialiser goes stale exactly like `FB_init` — `:= (Name := ...)`

**Changing a value inside an existing initialiser does not reach the compiler.**
Same storage trick as `FB_init` arguments: CODESYS keeps the initialiser in
`<initialValue><structValue>` beside the declaration, and reads *that*.

Proven on the annex `PLC_PRG_MAIN`, renaming four `FriendlyName` values. `apply`
reported `decl_replace` applied, `errors=0`, `saved=True`, and afterwards:

| | says |
|:--|:--|
| declaration text (what `info` shows, what a human reads) | `'Smoke detector landing'` |
| `structValue` (what the compiler reads, what the PLC runs) | `'Landing'` |

**The discriminator is whether the initialiser's *shape* changes**, and it explains
every case seen so far:

- new instance → no stored entry to win → text is parsed. The whole annex
  migration landed this way, 37 instances at once.
- **existing instance that had no initialiser** → also no stored entry → also
  parsed. `GVL_RS485.FB_RS485_EASTRON_SDM220_1` had been declared bare since
  it was written; a scripted `replace_in_decl` adding `:= (FriendlyName := '...')`
  reached `structValue` and the PLC ran it. So the test is whether a stored entry
  **exists**, not whether the instance is new — which is the more useful form of
  the rule, because adding a `FriendlyName` to an old instance is exactly what
  self-wiring a block asks you to do.
- member **renamed** (`Invert` → `RelayType`) → the stored entry names a member
  that no longer exists → re-derived. That rename landed, `RelayType` and all.
- same members, **different value** → shape unchanged → silently dropped.

### Verifying it: `info` cannot see this, `export` can

This is why it went unnoticed. `info -Full` returns the declaration **text**, which
is updated and looks right. The check that works is a PLCopen `export`, whose
`<variable>` elements carry the `<structValue>`:

```
./tools/ai/codesys.ps1 export -Project <path> -Output .ai/scratch.xml
```

Two traps in reading that export. It carries **no declaration text at all** — no
`interfaceasplaintext` — so grepping it for a comment proves nothing either way.
And bound each `<variable>` element properly when parsing: an instance with no
initialiser has no `<structValue>`, so a fixed-size window silently reads the
*next* instance's values. That produced a first draft of this finding that showed
a binary sensor with an `EntityType` and an uninitialised block with a name.

### There is no scripted way round it. Three were tried.

| Attempt | Result |
|:--|:--|
| `decl_replace` with the new values | text updated, `structValue` unchanged |
| `decl_replace` dropping the initialiser entirely, then a second `apply` re-adding it | **both saved clean, `structValue` unchanged by either** |
| (for `FB_init`, previously) `replace_in_decl` per line | same |

The second is the decisive one: removing `:= (...)` from the text does not remove
the stored members, so there is no clear-and-re-add trick. The store is simply
unreachable from `textual_declaration`.

Which retires the "shape change" theory this file carried for one revision. The
cases that *did* land are better explained without it:

- the 37 migrated instances were **new**, so there was no store to lose to;
- `Invert := TRUE` becoming `RelayType := E_RELAY_TYPE.NC` was almost certainly
  CODESYS re-binding the existing entry through the renamed member and keeping its
  ordinal — and `TRUE` and `NC` are both `1`. It came out right by luck, not
  because a script wrote it. Do not build on it.

**Remedy: the IDE**, same as `FB_init`. If the declaration text is already correct
and only the store is stale, that is a small job — open the POU, touch the
declaration and save, and the editor re-parses it. Better still, design so a value
someone will want to change does not live in an initialiser at all.

And whatever you do, **confirm with `export` and `structValue`, never with `info`**
— `info` returns the text, which is exactly the half that lies.

## An application's dynamic-memory setting is IDE-only

Adding a device, and filling its application with a GVL, a program and a task,
are all scriptable — see `device -AddDevice` and `scaffold` in `codesys-loop`.
**Enabling dynamic memory on an application is not.** Any application that
compiles a block reaching `FB_MQTT_BASE` needs it, because the MQTT library's
`CallbackCollector` uses `__NEW`, and without it the build fails with:

    No memory for dynamic object creation defined for application 'X.Application'
    <MQTT/Function Blocks/CallbackFBs/Callback Collector/CallbackCollector/put>

The setting is *Application → Properties → Dynamic memory settings → Use dynamic
memory allocation*. `Wago_PFC200_G1_Lab`'s application has it; a newly added device's
does not. Three property names were tried from a script — `dynamic_memory_size`,
`SizeForDynamicMemory`, `size_for_dynamic_memory` — and all three were rejected
*and* unreadable, so this is not a naming problem. Nor can the name be discovered:
**`dir()` on a ScriptEngine object returns nothing at all**, which is worth
knowing before spending a run on it.

It is a one-time click that then lives in the committed binary forever, like the
`Wago_PFC200_G2_Virtual` device it belongs to.

## Open: an edit that reports success and does not take effect

Not resolved, so do not assume an edit landed just because the report says so —
read the compiler messages, which is the advice for the `harness` section too.

Seen on `PRG_HVAC.HVAC_INIT` while splitting the publish queue: both
`replace_in_body` (`x1`) and a whole-body `body_replace` reported success, and the
compiler went on reporting the *old* text at that line. A diagnostic run that
deleted only the referenced GVL member showed the same reference in `HVAC_INIT` at
**two different line numbers at once** (14 and 25), i.e. that action gets compiled
from more than one source. The same mechanism edits the same action correctly
elsewhere — the collector-array change went through `HVAC_INIT` and is verified on
hardware — so this is specific to some combination, not to the action.

Worth checking next time: whether `find_editable` can return the
`Task Configuration/HvacTask/PRG_HVAC` node rather than the `PRG's/` program
(both are exported as roots), and whether `get_children(False)` should be `True`.

- **Behavioural tests in CODESYS simulation.** Built as the `simulate` task, then
  found to be a dead end for *this* project, so do not spend time on it again.
  Enabling simulation retargets the application from the PFC200's 32-bit ARM
  runtime to the in-process Windows simulation runtime, which is 64-bit
  (`CODESYS.exe` is x86-64 and `SimulationRts.dll` sits in the 64-bit `Common`
  folder). The vendored `SysFile23` and `SysSocket23` compatibility libraries —
  which exist because the PFC200 runs a 3.5.13-era 32-bit runtime, and which the
  MQTT library needs for sockets and files — are 32-bit only, so the build fails
  hard:

      The Library 'syssocket23, 3.5.13.0 (system)' is only supported in 32 bit applications

  There is no 32-bit IDE in this install (`Common32` holds only proxy helpers),
  and the one Windows runtime present is the **x64** `CODESYS Control Win V3`
  service, so there is nothing here that could host a 32-bit application either.
  The `simulate` task is kept because it is what diagnosed this and would work if
  the library situation ever changed.

**Consequence: runtime behaviour can only be tested on real PFC hardware.**
Compile-checking via `verify` is the automated gate; anything behavioural needs a
PLC. The `scan` and `download` tasks exist for that — see `codesys-loop`. A
download stops the application and re-initialises non-persistent variables, so it
requires `-Force`, and the target must be confirmed with the user every time
rather than inferred from a device name.
