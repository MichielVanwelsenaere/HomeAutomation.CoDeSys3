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

- Run `./tools/ai/codesys.ps1 doctor` to check the toolchain. CODESYS 3.5 SP21
  with the PFC200 SL package is required; Python is needed only by
  `update-fb-docs`, and is **not currently installed on this machine** (the skill
  has the `winget` command and the Windows `python3` caveat).
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

  There is no 32-bit IDE in this install (`Common32` holds only proxy helpers)
  and no alternative device such as CODESYS Control Win V3, so there is nothing
  to host a 32-bit simulation. The `simulate` task is kept because it is what
  diagnosed this and would work if the library situation ever changed.

**Consequence: runtime behaviour can only be tested on real PFC hardware.**
Compile-checking via `verify` is the automated gate; anything behavioural needs a
PLC. The `scan` and `download` tasks exist for that — see `codesys-loop`. A
download stops the application and re-initialises non-persistent variables, so it
requires `-Force`, and the target must be confirmed with the user every time
rather than inferred from a device name.
