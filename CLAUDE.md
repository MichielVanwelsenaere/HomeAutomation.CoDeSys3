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
| `src/Exports/archive/` | Standalone exports of blocks not in the reference project (DALI). |
| `src/Libraries/` | Vendored `.library` dependencies (MQTT, OSCAT, PRO_JSON). |
| `tools/ai/` | Headless CODESYS driver. |
| `.ai/` | Gitignored scratch: candidate blocks, sandbox copy, compiler reports. |

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
| Regenerate or check the generated regions of `docs/FunctionBlocks/*.md` | **`update-fb-docs`** |

Two things worth knowing before you start, both covered in detail by
`codesys-loop`:

- Run `./tools/ai/codesys.ps1 doctor` to check the toolchain.

  | Dependency | Needed by | Notes |
  |:--|:--|:--|
  | CODESYS 3.5 SP21 (3.5.21.30) + PFC200 SL package | everything | No licence needed for `--noUI` scripting. |
  | Python 3.12 | `update-fb-docs` only | **Installed** at `C:\Program Files\Python312-arm64`. Invoke it as **`py`**. |
  | mosquitto clients | `Mqtt-Snapshot.ps1` — the only runtime check there is | Not on `PATH`; the tooling also looks in `C:\Program Files\mosquitto`. |

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

- **Editing an SFC chart from a script, by any route.** `PLC_PRG_MAIN` is SFC and
  its chart cannot be touched: the object has a `textual_declaration` but **no
  `textual_implementation` at all** (`AttributeError` on access), so
  `replace_in_body` is out. Re-importing the POU as XML does not work either — a
  candidate file carries no folder structure, so the import files a *second*
  `PLC_PRG_MAIN` at the project root and leaves the real one in `PRG's/` alone.
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
  no hint in the chart that anything is missing. `PLC_PRG_MAIN.PROCESS_VIRTUAL` was
  retired this way and is gone; that program's chart is the worked example.

## Open: an edit that reports success and does not take effect

Not resolved, so do not assume an edit landed just because the report says so —
read the compiler messages, which is the advice for the `harness` section too.

Seen on `PLC_PRG_HVAC.HVAC_INIT` while splitting the publish queue: both
`replace_in_body` (`x1`) and a whole-body `body_replace` reported success, and the
compiler went on reporting the *old* text at that line. A diagnostic run that
deleted only the referenced GVL member showed the same reference in `HVAC_INIT` at
**two different line numbers at once** (14 and 25), i.e. that action gets compiled
from more than one source. The same mechanism edits the same action correctly
elsewhere — the collector-array change went through `HVAC_INIT` and is verified on
hardware — so this is specific to some combination, not to the action.

Worth checking next time: whether `find_editable` can return the
`Task Configuration/HvacTask/PLC_PRG_HVAC` node rather than the `PRG's/` program
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
