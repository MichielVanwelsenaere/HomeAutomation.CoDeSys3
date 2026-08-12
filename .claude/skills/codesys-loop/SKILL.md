---
name: codesys-loop
description: Read, write and compile-check CODESYS code in this project without opening the GUI, by driving CODESYS headlessly through its ScriptEngine. Use when adding or changing a function block, refactoring ST code, checking whether a change compiles, re-exporting src/Exports/PLCopen.xml, inspecting the project structure inside the binary .project file, or setting up the toolchain needed for any of that.
---

# CODESYS development loop

`src/HomeAutomation.project` is a **binary**. It cannot be read, diffed or edited
as text. The way in and out is **PLCopen XML**, which CODESYS both exports and
imports — and because CODESYS ships a ScriptEngine and runs with `--noUI`, the
real compiler can judge the result. Never reason about ST correctness from the
XML alone when you can compile it instead.

Two entry points, both committed at a normal path so CI and contributors can use
them too, not only agents:

- `tools/ai/codesys.ps1` — the wrapper you run.
- `tools/ai/codesys_task.py` — runs *inside* CODESYS (IronPython 2.7). Don't run
  it directly.

## Check the toolchain first

```powershell
./tools/ai/codesys.ps1 doctor
```

Fast, does not launch CODESYS. Required:

| Item | Notes |
|:--|:--|
| CODESYS 3.5 SP21 (3.5.21.30) | Includes the ScriptEngine and the IronPython stdlib. No extra license needed for `--noUI` scripting. |
| `ScriptEngine.dll` | Under `CODESYS\Common\`. The entire harness depends on it. |
| CODESYS Control for PFC200 SL | The project's device. Without it the device will not resolve and the build fails. |
| Windows PowerShell 5.1 | The scripts avoid PowerShell 7-only syntax, so either works. |

Override discovery with `-Exe` / `-CodesysProfile`, or set `$env:CODESYS_EXE`.

**Python is not needed by this harness** — only by the `update-fb-docs` skill.
`doctor` reports it as a warning, not a failure.

### Installing Python (for the docs generator only)

`gen_fb_docs.py` needs **3.7+** (it uses f-strings and
`from __future__ import annotations`). Install a current release:

```powershell
winget install --id Python.Python.3.12 --scope machine
```

Then open a **new** shell and verify:

```powershell
py --version
```

Two Windows gotchas worth knowing before you debug a "Python was not found"
message:

- `winget` installs the python.org build, which provides `python.exe` and the
  `py` launcher but **no `python3.exe`**. On this machine, invoke the docs
  generator as `py .claude/skills/update-fb-docs/scripts/gen_fb_docs.py`.
- Windows ships an App Execution Alias stub for `python`/`python3` that opens the
  Microsoft Store instead of running anything. If a bare `python` still opens the
  Store after installing, turn the aliases off under
  *Settings → Apps → Advanced app settings → App execution aliases*. `doctor`
  already ignores anything resolving inside `WindowsApps` for this reason.

## Tasks

Each task boots CODESYS, so budget **40–90 seconds**. A `--noUI` process has no
usable stdout: results go to `.ai/reports/<task>.json`, with a progress log at
`<task>.json.log` that survives a crash. `.ai/` is gitignored.

**`.ai/work` is wiped at the start of every `verify` and `simulate`** — it is the
sandbox. Never keep anything there. Edit fragments belong in `.ai/edits/`.

| Command | Effect |
|:--|:--|
| `./tools/ai/codesys.ps1 doctor` | Toolchain check. No CODESYS launch. |
| `./tools/ai/codesys.ps1 tree` | Dump the project object tree. |
| `./tools/ai/codesys.ps1 device` | Report the configured gateway, address and simulation flag. Connects to nothing. |
| `./tools/ai/codesys.ps1 scan` | List PLCs answering on each gateway. Read-only, needs no project. |
| `./tools/ai/codesys.ps1 download -Force` | Full download of the real project to the real PLC, then start it. |
| `./tools/ai/codesys.ps1 export` | Rewrite `src/Exports/PLCopen.xml` from the project. |
| `./tools/ai/codesys.ps1 verify -Baseline` | Build the untouched project, store its messages as the baseline. |
| `./tools/ai/codesys.ps1 verify` | Import `.ai/candidates/*.xml` into a sandbox copy, build, report. |
| `./tools/ai/codesys.ps1 simulate` | Download to a simulated PLC and run a test spec. **Currently blocked — see below.** |
| `./tools/ai/codesys.ps1 apply -Force` | Import candidates into the **real** project and save. |
| `./tools/ai/codesys.ps1 probe` | Dump real .NET signatures of the scripting API. |

## Workflow

1. **Confirm the export is current** before trusting it:

   ```
   git log -1 --format=%cd -- src/Exports/PLCopen.xml src/HomeAutomation.project
   ```

   If the project is newer, run `export` first. Regenerating docs or reasoning
   about pins from a stale export bakes in wrong interfaces.

2. **Record a baseline** once per session: `verify -Baseline`. The project builds
   with 8 pre-existing warnings — three OSCAT `CONSTANTS_SETUP` string-length
   warnings, three `IP_CONTROL2` sign conversions, `PersistentVars`, and one
   genuine sign conversion in `DMX_SEND` line 70. With a baseline recorded,
   `verify` prints a `NEW vs baseline` section so your own changes stand out.
   Re-record after a library or CODESYS version change.

3. **Read** the current code from `src/Exports/PLCopen.xml`: declarations, ST
   bodies, methods and the task configuration are all there.

4. **Write** the change as a single-block PLCopen file in `.ai/candidates/`.
   Start from `tools/ai/templates/FB_TEMPLATE.xml`, which documents the dialect.
   For anything non-trivial, copy the shape of a comparable existing block out of
   `PLCopen.xml` rather than inventing structure.

5. **Verify** — `./tools/ai/codesys.ps1 verify`. This copies the project to
   `.ai/work`, imports the candidates, builds, and reports every message with
   object, line and column. Iterate here; the real project is untouched. Read the
   `harness` section of the report, not just the result line (see below).

6. **Apply** only once verify is clean: `apply -Force`. It refuses to save if the
   build fails. Then **re-export** so the XML matches the binary again, and update
   the docs with the `update-fb-docs` skill.

Steps 6 onwards change tracked files, including a binary. Ask before running them
unless the user has already said to land the change.

## Authoring candidates: what the importer actually accepts

Established by compile probe, not by reading documentation:

- **Plaintext declarations work for a NEW POU, but do not reliably override an
  existing one.** Authoring a brand-new block with a plaintext declaration and an
  empty `<interface />` works (proven). But taking an existing POU out of the
  export, appending a `VAR_INPUT` block to its plaintext declaration and
  re-importing it does **not** apply the new members: the block keeps exactly its
  old declaration, the import still reports `replaced 1`, and the only symptom is
  `Identifier 'X' not defined` in whatever referenced the new member. Emptying the
  structured `<interface>` did not change this. **Unresolved** — the next attempt
  should isolate it by (a) removing the `<interface>` element entirely rather than
  emptying it, (b) trying a plain `INT` member to rule out the enum type, and
  (c) comparing against editing the structured `<interface>` instead, which is
  the safer default until this is understood. Prefer the ScriptEngine textual API
  (`textual_declaration.append`) for editing an existing POU's declaration; that
  path is already proven by the verify harness, which injects into a real program
  this way on every run.
- For a NEW POU, put the plaintext declaration in an `<addData>` block on the
  `<pou>`:

      <data name="http://www.3s-software.com/plcopenxml/interfaceasplaintext" handleUnknown="implementation">
        <InterfaceAsPlainText>
          <xhtml xmlns="http://www.w3.org/1999/xhtml">FUNCTION_BLOCK FB_X EXTENDS FB_MQTT_BASE
      VAR
      	x : INT;
      END_VAR</xhtml>
        </InterfaceAsPlainText>
      </data>

  The importer prefers it over the structured `<interface>`, it is lossless, and
  `EXTENDS` works. Get a template by running `export -Plaintext`, which writes
  `.ai/reports/PLCopen.plaintext.xml` with every POU in this form.
- **A METHOD's interface must be structured XML.** A nested
  `InterfaceAsPlainText` inside a `<Method>` is silently ignored, so the method
  is built from the structured `<interface>` instead — which produced a
  malformed `FB_init` that failed in four different ways at once. For `FB_init`
  that means `<returnType><BOOL /></returnType>` plus `bInitRetains`,
  `bInCopyCode` and your own parameters as `<inputVars>`.
- **`qualified_only` is set on every GVL here** (`MqttVariables`,
  `DALIVariables`, `PersistentVars`, `DMXVariables`, `RS485Variables`), so a POU
  body must write `MqttVariables.fbMqttPublishQueue`, never the bare name.

### FB_init and inheritance, as this compiler actually behaves

- A **derived** FB that declares no `FB_init` of its own still accepts the
  **base's** `FB_init` parameters at the declaration site:
  `inst : FB_DERIVED(sFriendlyName := 'Kitchen');`. Declare `FB_init` once on the
  base and the whole hierarchy inherits the parameter.
- `FB_init` may read a GVL value and may take `ADR()` of a GVL member. It
  compiles — but *runtime* initialisation order between a GVL and an instance in
  another POU is not something the compiler checks. Prefer storing only literals
  passed into `FB_init` and doing GVL-dependent wiring lazily on the first cycle,
  which is order-proof.
- Precedent worth copying: `MqttVariables.PLC_Device` is declared inside the GVL
  with a full `FB_init` argument list including `pMqttPublishQueue := ADR(fbMqttPublishQueue)`.

## Instantiating a block the harness cannot

Auto-instantiation cannot declare a block whose `FB_init` takes parameters. Two
optional files let you take over:

| File | Effect |
|:--|:--|
| `.ai/candidates/_harness.decl` | Appended verbatim to the host program's declaration. Give a complete `VAR ... END_VAR` block. |
| `.ai/candidates/_harness.impl` | Appended verbatim to a body, so you can actually call the block. |

Any candidate block named in these files is counted as covered and drops out of
`not_instantiated`. Note the programs here keep their logic in **actions**, so a
program's own body is often empty and exposes no implementation; the harness
falls back to the first action that has one and reports it as `impl_host`.

## A clean build does not always mean checked

**An unreferenced POU is never compiled.** A block imported into the
project-level POU pool belongs to no application, so CODESYS generates no code
for it and reports a successful build for code that does not compile. This is the
most dangerous failure mode in the whole loop.

`verify` works around it by declaring an instance of each candidate function
block inside a program the task configuration already calls, which forces a full
check of the body. Two cases cannot be handled that way and are reported instead:

- a `pouType` other than `functionBlock` (a function or program is only compiled
  where it is called), and
- an `FB_init` that takes parameters, since the instance cannot be declared
  without supplying them.

Those appear as `NOT COMPILE-CHECKED` in the console and under
`harness.not_instantiated` in the report, and the result line degrades to
`BUILD OK, but N candidate block(s) were not compile-checked`. **Treat that as
unverified.** Exercise such a block from a real call site instead. Note that
`apply` injects no harness at all, by design — verify before you apply.

## Running the application — what is and isn't possible

**Compile-checking is the automated gate. Behavioural testing needs real
hardware.** Don't rediscover this the hard way:

`simulate` is implemented and mechanically works — it enables simulation on a
sandbox copy, builds, and would log in, start, and run a JSON test spec. But this
project cannot run in simulation. Enabling simulation retargets the application
from the PFC200's 32-bit ARM runtime to the in-process Windows simulation
runtime, which is 64-bit, and the vendored `SysFile23` / `SysSocket23`
compatibility libraries that the MQTT library needs are 32-bit only:

    The Library 'syssocket23, 3.5.13.0 (system)' is only supported in 32 bit applications

There is no 32-bit IDE in this install, and the one Windows runtime present is
the **x64** `CODESYS Control Win V3` service, so nothing here can host a 32-bit
application. The task is kept for the diagnosis and in case the library
situation changes.

`scan` relies on a gateway broadcast and is not reliable — it listed three PLCs
once and nothing at all twenty minutes later, on a machine with two NICs on the
same subnet. When it comes up empty, find the PLC out-of-band instead: `arp -a`
filtered on WAGO's `00-30-de` MAC prefix maps IPs to the device names the CODESYS
scan reports, and `Test-NetConnection <ip> -Port 11740` confirms the runtime is
listening. Then use `download -Ip <ip>`, which resolves the node through the
gateway directly and needs no broadcast.

The spec format, for when it is usable — or as the model for a device-side test:

```json
{ "steps": [
    { "label": "press",  "write": {"MqttVariables.clientID": "'test'"}, "delay_ms": 300 },
    { "label": "assert", "expect": {"MqttVariables.clientID": "test"} }
] }
```

Run with `./tools/ai/codesys.ps1 simulate -Spec path\to\spec.json`. Values are
strings in both directions. A failed `expect` lands in `test_failures` and fails
the run, distinct from a compiler error.

## Downloading to the real PLC

`download` performs a **full download of `src/HomeAutomation.project`** to the
physical PLC and starts it. A download stops the running application and
re-initialises non-persistent variables, and this project drives HVAC, a burner,
covers and lights. So:

- `-Force` is required. Without it the task refuses and explains why.
- It **never saves the project** — no run can leave the binary altered.
- It **refuses to run if the device is in simulation mode**, which would
  otherwise mean downloading into a simulated PLC while reporting success.
- It builds first and aborts if the build is not clean.
- On success it logs out but leaves the PLC **running**; only the connection
  closes. `-NoStart` loads without starting, `-BootApplication` also writes a
  boot application so the PLC comes back up running this project.
- **Confirm the target with the user every time.** Bench versus live is not
  something to infer from a device name.

```powershell
./tools/ai/codesys.ps1 scan                              # what is actually reachable
./tools/ai/codesys.ps1 download -Force -Address 003E     # target one node, this run only
```

**The stored address goes stale.** The committed project points at node `00E8`,
which no longer answers; a scan found three PFC200s on `003C`–`003E`. Run `scan`
first and check the runtime column — only a device reporting *CODESYS Control for
PFC200 SL* matches this project; the WAGO 750-8202 entries run a different
runtime. `-Address` (node, as `scan` prints it) and `-Ip` retarget for a single
run without touching the committed settings.

**Credentials** come from `$env:PLC_USER` / `$env:PLC_PASS` when set, otherwise
CODESYS's cached device login is used. They are passed through the task file in
gitignored `.ai/`, which the wrapper shreds immediately after the run. Never put
a device password in a committed file.

## Report format

`.ai/reports/<task>.json`:

| Key | Meaning |
|:--|:--|
| `ok` | No tool errors and no compiler errors. |
| `messages[]` | `severity`, `text`, `object`, `position`, `number`, `occurrences`. |
| `error_count` / `warning_count` | Counts over `messages`. |
| `imports[]` | Per candidate file: `added`, `replaced`, `skipped`, `errors`. |
| `harness` | `host`, `instantiated`, `not_instantiated` — read this. |
| `built` | Applications that compiled. |
| `errors[]` | Tool-level failures, distinct from compiler messages. |
| `test_failures[]` | Failed `expect` assertions from a `simulate` spec. |
| `online` | `simulate` only: login state, application/operating state, per-step results. |
| `devices` / `gateways` | `device` only: configured target and known gateways. |

`occurrences` counts identical messages collapsed across message categories, so
a mismatch against CODESYS's own "N errors, M warnings" line is explainable
rather than a sign that something was hidden.

## Scripting API traps

- **The shipped `.pyi` stubs have wrong argument orders.** `export_xml` and
  `import_xml` really take `reporter` **first**, and the .NET binding rejects
  those names as keywords — pass them positionally.
- **Reporter classes must subclass** the injected `ImportReporter` /
  `ExportReporter`. A duck-typed class is refused with `expected IExportReporter`.
- **Folders are not exportable.** Passing one as an export root makes CODESYS
  skip its entire subtree, which silently drops every function block. The driver
  walks through folders and passes leaf objects.
- **IronPython 2.7, not CPython.** No f-strings; its `json` refuses .NET integers
  and ASCII-encodes text, which non-ASCII compiler messages break. Everything
  entering the report goes through the `u()` helper.
- Settle any further API question with `probe`, which dumps the real .NET
  overloads, rather than guessing across 80-second round trips.

## Export fidelity

Re-exporting an unchanged project reproduces the committed
`src/Exports/PLCopen.xml` byte for byte **except two header timestamps**, so
expect a 2-line diff and nothing more. A larger diff means the project really
changed. Object order is sorted deliberately — with `_` folded below
alphanumerics, matching the order CODESYS itself produced — so the file stays
diffable.
