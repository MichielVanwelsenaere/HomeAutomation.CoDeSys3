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
| WAGO Device Support Package 2.0.8.9 | Supplies `WagoAppDALI`, which `FB_OUTPUT_DIMMER_DALI_MQTT` needs. Without it the build fails on that block, not just on DALI. It is not vendored — WAGO's licence forbids redistribution — so install it per machine: `docs/WagoPfcPrep.md#installing-the-wago-libraries-dali`. **`WagoAppDALI` is qualified-only**, unlike in e!COCKPIT: its types are `WagoAppDALI.typBallast`, `WagoAppDALI.FbDaliSendDimValue` and so on, so ST lifted out of an e!COCKPIT project does not compile until it is qualified. |
| Windows PowerShell 5.1 | The scripts avoid PowerShell 7-only syntax, so either works. |
| mosquitto clients | **Optional but the only runtime check available.** `winget install --id EclipseFoundation.Mosquitto --scope machine`. The installer registers a broker service that is not needed here (leave it stopped) and does **not** add itself to `PATH`; the tooling also looks in `C:\Program Files\mosquitto`. |

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
| `./tools/ai/codesys.ps1 device` | Report the device tree, the configured gateway, address and simulation flag. Connects to nothing. |
| `./tools/ai/codesys.ps1 device -AddModule <ModuleId> -Under <node> -Force` | Plug a module into the device tree. Builds first and refuses to save a project that does not build. |
| `./tools/ai/codesys.ps1 device -AddDevice <type:id:version> -NodeName <name> [-Under <node>] -Force` | Add a device — a module, or a whole second controller at the project root. |
| `./tools/ai/codesys.ps1 device -RemoveNode <name> -Force` | Unplug a device or module. |
| `./tools/ai/codesys.ps1 device -RenameNode <name> -NodeName <new> -Force` | Rename a device or module. Re-record the baseline afterwards: a device's name is in every message's object path. |
| `./tools/ai/codesys.ps1 scaffold -Scaffold <spec.json> -Force` | Create GVLs, programs and tasks inside an application. |
| `./tools/ai/codesys.ps1 scan` | List PLCs answering on each gateway. Read-only, needs no project. |
| `./tools/ai/codesys.ps1 download -Force` | Full download of the real project to the real PLC, then start it. |
| `./tools/ai/codesys.ps1 export` | Rewrite `src/Exports/PLCopen.xml` from the project. |
| `./tools/ai/codesys.ps1 verify -Baseline` | Build the untouched project, store its messages as the baseline. |
| `./tools/ai/codesys.ps1 verify` | Import `.ai/candidates/*.xml` into a sandbox copy, build, report. |
| `./tools/ai/codesys.ps1 simulate` | Download to a simulated PLC and run a test spec. **Currently blocked — see below.** |
| `./tools/ai/codesys.ps1 apply -Force` | Import candidates into the **real** project and save. |
| `./tools/ai/codesys.ps1 rename -Map <map.json> -DryRun` | Report what a rename would touch. Writes nothing, builds nothing. |
| `./tools/ai/codesys.ps1 rename -Map <map.json> -Force` | Rename objects and identifiers, rewriting every reference. Refuses to save unless it builds. |
| `./tools/ai/codesys.ps1 probe` | Dump real .NET signatures of the scripting API. |
| `./tools/ai/codesys.ps1 info` | Read-only: IDE version, libraries, devices, and a hash of every object's code. |
| `./tools/ai/codesys.ps1 compare -Project A -Against B` | CODESYS's own object-level diff between two projects. |
| `./tools/ai/codesys.ps1 libs` | Read-only: every library reference against every version installed on this machine. |
| `./tools/ai/codesys.ps1 libs -RemoveLib '#Name'` | Drop a library reference. Builds first, refuses to save if it does not build. |

### Working on another project

`-Project <path>` points any task at a different `.project` file — that is how
`sync-implementation-project` drives a building's installation project. Reports
are then stem-qualified (`baseline.SiteA.json`), so a foreign build
cannot overwrite this project's baseline. `download` **refuses** `-Project`.

Four companions to it:

| Flag | Why |
|:--|:--|
| `-Candidates <dir>` | A separate candidate set, so two pieces of work cannot import into each other's project. |
| `-Only <names>` | Export just some objects. Errors by name if one is not found rather than exporting less than asked. |
| `-ImportFolders` | Honour the folder structure in a candidate exported from another project. Without it the block lands at the project root, is never compiled, and the build stays green while the import achieved nothing. |
| `-ImportConflict replace` | Replace an object that already exists. Without a policy the importer has no say and files a **second** object of the same name, leaving the original compiled. |

The last two fail the same way — silently, with a green build — and a candidate
lifted out of another project needs both.

## Workflow

1. **Confirm the export is current** before trusting it:

   ```
   git log -1 --format=%cd -- src/Exports/PLCopen.xml src/HomeAutomation.project
   ```

   If the project is newer, run `export` first. Regenerating docs or reasoning
   about pins from a stale export bakes in wrong interfaces.

2. **Record a baseline** once per session: `verify -Baseline`. The project builds
   with 9 pre-existing warnings — three OSCAT `CONSTANTS_SETUP` string-length
   warnings, three `IP_CONTROL2` sign conversions, `GVL_PERSISTENT`, one genuine
   sign conversion in `PRG_DMX_SEND` line 70, and one for
   `PRG_DALI_VERIFY.Dimmer.DimValue` having no persistent list on
   `Wago_PFC200_G2_Virtual`. That last one is **load-bearing**: it is only
   reported because the DALI block really is compiled there, so if it ever
   disappears, the verification application has stopped verifying. The
   application is never downloaded, so nothing needs retaining. With a baseline
   recorded, `verify` prints a `NEW vs baseline` section so your own changes
   stand out. Re-record after a library or CODESYS version change.

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

## Changing an existing POU: use edits, not candidates

**A candidate XML import REPLACES the whole object**, so it is right for a *new*
block and wrong for changing an existing one — a partial file silently drops
every method it omits, and appending to an existing POU's plaintext declaration is
ignored outright. For existing code use `.ai/edits/edits.json`, which drives the
ScriptEngine's textual API and is applied by both `verify` and `apply`:

```json
{ "edits": [
    { "pou": "FB_MQTT_BASE",  "decl_append_file": "base.decl",
      "skip_if_contains": "FriendlyName" },
    { "pou": "FB_OUTPUT_BINARY_MQTT", "body_prepend_file": "prologue.st",
      "skip_if_contains": "self-wiring prologue" },
    { "pou": "PRG_MAIN",  "decl_replace_file": "main.decl" },
    { "pou": "PRG_MAIN",  "member": "MAIN_INIT", "body_replace_file": "main_init.st" }
] }
```

| Key | Effect |
|:--|:--|
| `pou` | POU, program **or GVL** name. Must resolve to exactly one object that owns text. |
| `path` | Substring of the object path, matched case-insensitively, to disambiguate `pou`. |
| `member` | Target a method or action instead of the POU itself. |
| `decl_append` / `decl_replace` | Declaration, inline text or `*_file`. |
| `body_prepend` / `body_append` / `body_replace` | Implementation, same. |
| `skip_if_contains` | **Idempotence sentinel.** If the target text already contains it, that append/prepend is skipped. |

Notes that cost real time to rediscover:

- **Always set `skip_if_contains` on an append or prepend.** An edit spec gets
  re-run constantly during a refactor, and without the sentinel a second run
  duplicates the text. `*_replace` needs no guard.
- `*_file` paths resolve relative to the spec file, then to the repo root. Keep
  fragments in `.ai/edits/` — **never `.ai/work`, which `verify` deletes.**
- **A name stops identifying a POU as soon as a project has two controllers.**
  An installation with two PFCs has two `PRG_MAIN`, both real, both owning
  text, and every edit addressed by name alone is then refused as ambiguous.
  `"path": "Wago_G1_Annex/"` picks one. The refusal is the useful behaviour —
  the alternative is a coin flip over which building gets rewritten — so do not
  work around it by renaming a program. `delete_pou` has no such qualifier yet;
  it will report the same ambiguity and stop.
- `insert()` takes the **offset first**, the reverse of the shipped stub. Same trap
  as `export_xml`.
- **`create_method` works on an INTERFACE too**, which is how a method reaches
  `I_RS485_DEVICE` or `I_RS485_TRANSPORT` without hand-authoring interface XML: the
  interface object owns text, so `create_method` plus `decl_replace` is the whole
  job. Every implementer then needs the same method or the build fails by name —
  which is the useful failure, and how the six RS485 device blocks were kept in
  step when `GetCommissioning` was added.
- **A `///` doc comment written by `decl_replace` does not reach the export.**
  CODESYS only materialises `<documentation>` for a comment its own editor parsed,
  so a method created from a script exports with its plaintext declaration intact
  and no structured documentation — and `update-fb-docs` therefore shows it as
  `_TODO: describe this._` however carefully the fragment was commented. Write the
  description in the doc page, or in the generator's `GLOSSARY` when the method
  means the same thing on every block.
- `-Edits none` skips the spec, which is how you build the committed project
  standalone as a control. A `verify -Baseline` never applies edits.
- Generating the fragments from a script (see `.ai/edits/gen.ps1` in history) beats
  hand-writing 14 near-identical prologues.

## Renaming: `rename`, not edits

Renaming is its own task because `node.rename()` renames an object and updates
**nothing** that refers to it — CODESYS's IDE refactoring is not exposed to the
ScriptEngine. The references are the harness's job:

```powershell
./tools/ai/codesys.ps1 rename -Map tools/ai/rename/179-objects.json -DryRun
./tools/ai/codesys.ps1 rename -Map tools/ai/rename/179-objects.json -Force
```

The map holds `objects` (a type, block, program or GVL — the name is
project-unique, so every occurrence of the token is that object) and
`identifiers` (variables inside one declaring object). An identifier group's
`mode` decides how far it reaches:

| mode | rewrites | right for |
|:--|:--|:--|
| `local` | the declaring object and its methods and actions | a program's own instances, a block's internals |
| `qualified` | also `Owner.name` project-wide | GVL members, enumeration values |
| `loose` | also `.name` and `name :=` project-wide | a function block's pins, whose qualifier is an instance name nothing can enumerate |

Five things learned building it, all of which cost a run:

- **A program rename is two renames.** The task configuration calls a program
  through a separate object that carries the program's name and owns no code, so
  every text-owning filter misses it. Renaming the program alone gives
  `Identifier 'PLC_PRG_MAIN' not defined <.../Task Configuration/MainTask>`. The
  task now renames the call twin too, and reports it as `(task call)`.
- **One name can mean several objects.** Two applications mean two
  `MqttVariables`, and `FB_MQTT_BASE` declares
  `STRING(GVL_MQTT.MQTT_TOPIC_LEN)`, so the name has to resolve in both.
  Ambiguity is refused unless the map says `{"new": ..., "all": true}` — or
  `"path"` to pick one.
- **A shadow is the one mistake that compiles.** `PRG_DALI_VERIFY` declared an
  instance called `Dimmer` while the enumeration `Dimmer` was becoming
  `E_DIMMER`; a blind sweep renames the instance too, consistently, and the
  build stays clean with a variable now called `E_DIMMER`. The task refuses an
  object rename whose old name is also declared as a variable, and identifier
  groups run **first** so one map can move the variable out of the way.
- **Dry-run counts are an upper bound.** Passes do not compose without writing,
  so a map that renames both a variable and an object of the same name
  double-counts: 515 references in `-DryRun` versus 473 actually rewritten.
- **String literals are never touched, comments always are.** Topics, discovery
  keys and JSON live in literals; a comment still naming the old object is worse
  than no comment.

Afterwards: `verify -Baseline` (object paths moved, so the old baseline reads
every unchanged warning as NEW), `export`, then `update-fb-docs`. The docs
generator keys the GVL region on the list's name, so a GVL rename means editing
`gen_fb_docs.py` too.

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
- **A `<dataType>` takes `<baseType>` then `<addData>`, and nothing else.** There
  is no `<documentation>` child on a DUT in `tc6_0200`; adding one fails the whole
  file with

      The element 'dataType' ... has invalid child element 'addData'

  which names the wrong element and reads like an ordering problem, so the obvious
  fix — shuffling the children — does not help. Put a type's prose in the
  per-value `enumvaluedocumentation` block instead. **The import failure is easy
  to miss**: `verify` reports it in `imports[].errors`, then the build fails with
  a hundred `Identifier not defined` errors for the type, and the real message is
  the first one, not the hundred. `E_RELAY_TYPE` was authored this way — copy it.
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
- **`qualified_only` is set on every GVL here** (`GVL_MQTT`,
  `GVL_DALI`, `GVL_PERSISTENT`, `GVL_DMX`, `GVL_RS485`), so a POU
  body must write `GVL_MQTT.fbMqttPublishQueue`, never the bare name.

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
- Precedent worth copying: `GVL_MQTT.PLC_Device` is declared inside the GVL
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

**Delete them when the work they supported is finished.** They are gitignored and
machine-local, they are injected into *every* `verify` from then on, and nothing
reports that they exist. Two ways that bites:

- **`verify` compiles more than the project does.** A harness left over from an
  old refactor keeps an otherwise-unreferenced block compiled on your machine
  only. Your `verify` is green, a colleague's or CI's is green for a different
  reason, and the shipped project never compiles that block at all. `apply`
  injects no harness, so it is the honest answer to "is this block compiled?"
- **They break the next refactor and blame the wrong thing.** A leftover harness
  calling `InitRS485(...)` failed a run that had just moved that configuration
  into `FB_init` - four errors pointing at a program nobody had touched, in code
  that is not in the repository.

## Library references

`libs` is the way in and out of the Library Manager, which is otherwise only
reachable from the IDE.

```powershell
./tools/ai/codesys.ps1 libs                        # what is referenced, and what is installed
./tools/ai/codesys.ps1 libs -LibFilter modbus      # also: every installed Modbus library
./tools/ai/codesys.ps1 libs -RemoveLib '#IoDrvModbus'
./tools/ai/codesys.ps1 libs -AddLib 'SysCom, 3.5.17.0 (System)'
./tools/ai/codesys.ps1 libs -UpdateLib 'PRO_JSON'  # repoint a PLACEHOLDER at the newest installed
```

Read-only without `-RemoveLib` / `-AddLib` / `-UpdateLib`. With any of them it
behaves like `apply`: it builds first and **refuses to save a project that does
not build**, which is what makes "is anything still using this?" a question you
can answer by trying it.

Four things about the report are worth knowing before acting on it:

- **`-LibFilter` only sees this machine.** The repository query lists what is
  *installed*, not what the CODESYS Store has. "Nothing newer" means "none
  here", never "none exists" — installing a newer library is still an IDE job.
- **A `*` version floats.** `PRO_JSON, * (Pro Electric)` already resolves to the
  newest installed version, so it is never reported as behind one. What pins it
  to something older is a *redirection*, which the report shows separately.
- **`(not resolved in this project)` is not `outdated`.** Several visualisation
  placeholders carry a default resolution but resolve to nothing, because
  nothing uses them. Reporting those as outdated would send you after a version
  no build is reading.
- **Names must match the Library Manager exactly**, `#` included for a
  placeholder. `libs` with no arguments prints the exact strings.

`-UpdateLib` takes a **placeholder** name only. A fixed reference carries its
version inside its name, so moving one means `-RemoveLib` then `-AddLib`.

### The repository global is called `librarymanager`

Not `library_manager`, which is what the shipped `.pyi` stub says and what does
not resolve — the same class of stub-versus-reality gap as `export_xml`'s
argument order and `insert()`'s parameter order. `repository_manager()` in
`codesys_task.py` tries the names and then falls back to finding whatever object
answers `get_all_libraries`, so this should not need rediscovering.

Also: a repository entry's `displayname` is the **full** `"IoDrvModbus, 4.5.0.0
(CODESYS)"` string, not a bare name. Grouping on it directly yields one entry
per version and matches nothing.

## The device tree

`device -AddModule` plugs a K-bus module in, which was the last part of the
project only the IDE could reach:

```powershell
./tools/ai/codesys.ps1 device                                   # read-only: the tree
./tools/ai/codesys.ps1 device -AddModule '0287_75x_647' -Under 'Pfc200Bus' -Force
```

A whole device, including a second controller, goes in the same way — but a
device carries its own identification, so it has to be given:

```powershell
# type:id:version, read out of the device description
./tools/ai/codesys.ps1 device -AddDevice '4096:1006 1209:6.4.5.11' -NodeName 'Wago_PFC200_G2_Virtual' -Force
./tools/ai/codesys.ps1 device -AddDevice '32776:07530647000000002424:2.0.0.20' -Under 'Kbus' -NodeName 'DALI_753_647' -Force
./tools/ai/codesys.ps1 device -RemoveNode '_75x_647' -Force        # and back out again
```

**A second controller is how an otherwise-uncompiled block gets covered.** A
project can hold several devices, and an application that is never downloaded is
still compiled. Adding a controller creates `Plc Logic/Application` with a
Library Manager and nothing else, so `scaffold` fills it in:

```powershell
./tools/ai/codesys.ps1 scaffold -Scaffold tools/ai/scaffold/g2-dali-verify.json -Force
```

A scaffold spec creates GVLs, programs and tasks inside a named application,
idempotently by name, and it takes `*_file` fragments exactly as an edits spec
does. `Wago_PFC200_G2_Virtual` in this project is the worked example.

Four things learned building that, each of which cost a run:

- **A pool POU still needs an instance.** Landing a block in the project is not
  the same as getting it compiled; see *A clean build does not always mean
  checked* below. That is the whole reason the second controller exists.
- **Task priority is capped per device.** The WAGO G2 description sets
  `maxtaskpriority` to 15, and CODESYS rejects anything higher with *"The task
  priority is invalid"* without mentioning a range. Read the limit from
  `<ts:setting name="maxtaskpriority">` in the device description.
- **Libraries resolve from the project-level Library Manager.** A program in a
  second application referenced `WagoAppDALI` and `FB_OUTPUT_DIMMER_DALI_MQTT`
  with no library reference of its own and compiled. What does *not* carry over
  is a GVL: those belong to an application, so the second one needs its own
  `GVL_MQTT` — only the two constants `FB_MQTT_BASE` actually reads.
- **`dir()` on a ScriptEngine object returns nothing**, so the usual way of
  finding an undocumented member does not work here. `probe` dumps it anyway, and
  it comes back empty; a name has to be tried and read back instead. That is what
  a scaffold item's `"set"` is for.

Three things about `-AddModule`, all of which cost a run to learn:

- **A module is not identified the way a device is.** `add` takes the *parent's*
  `(type, id, version)` plus the module's own `ModuleId`, which is why every
  module under `Pfc200Bus` reports the bus's identification (`288`,
  `0000 0001`, `4.19.0.0`) and differs only in name. The harness therefore reads
  the identification off the parent instead of asking for it — there is exactly
  one right answer and it is already in the project.
- **ModuleIds come from the device description**, not from a catalogue the API
  exposes. For this project's bus that file is
  `C:\ProgramData\CODESYS\Devices\288\0000 0001\4.19.0.0\device.xml`, or the copy
  under `CODESYS Control for PFC200 SL\...\WagoPFC200Internalbus.devdesc.xml`;
  grep it for `<ModuleId>`. `0287_75x_647` is the 753-647 DALI multi-master.
- **`-Under` prefers an exact node name.** Without that precedence `Pfc200Bus`
  is ambiguous by way of its own children, whose *paths* all contain it — the
  obvious query refused by the modules already on the bus.

Writing needs `-Force`, and like `libs` it builds first and refuses to save a
project that does not build.

### Two things a second application broke, and how they are fixed

Both were latent for as long as the project had exactly one application, and both
made the harness quietly report less than it had checked:

- **`build()` is incremental, `rebuild()` is not.** An application CODESYS
  considers up to date compiles nothing and says nothing, while still landing in
  `built`. A baseline recorded straight after a save therefore came back with the
  new application's messages only. `build_and_collect` now calls `rebuild()`.
- **A build CLEARS the message store.** Sweeping once after building every
  application returned the *last* one's messages and dropped the rest — which is
  how a baseline came back with none of this project's eight known warnings.
  Messages are now collected after each application and accumulated.

The second fix also surfaced the library `Information` messages (MQTT's `TODO`
and `semaphore` notes) that had been swallowed all along. They are in the
baseline now, so they do not read as new.

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
    { "label": "press",  "write": {"GVL_MQTT.clientID": "'test'"}, "delay_ms": 300 },
    { "label": "assert", "expect": {"GVL_MQTT.clientID": "test"} }
] }
```

Run with `./tools/ai/codesys.ps1 simulate -Spec path\to\spec.json`. Values are
strings in both directions, and `download -Spec` runs the same format against real
hardware. A failed `expect` lands in `test_failures` and fails the run, distinct
from a compiler error.

**An `expect` is compared against the value as the runtime prints it, so it needs
the type prefix and, for a string, the apostrophes:** `INT#4`, `UDINT#1`,
`TIME#10s`, `'probes=1 found=9600/255'`. Writing `4` against an `INT` reports
`expected 4, got INT#4`, which reads as a behavioural failure and is nothing of the
kind — and each retry is a full download, so it costs three minutes to learn twice.

## Verifying runtime behaviour over MQTT

The compiler is the only automated gate on the PLC side, but **the broker sees
everything the PLC publishes** — which is the one runtime check available here.
Use it around every download:

```powershell
./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/before.txt      # BEFORE the download
./tools/ai/codesys.ps1 download -Force -Ip 10.101.1.232
./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/after.txt       # after, once settled
./tools/ai/Mqtt-Snapshot.ps1 -Diff .ai/mqtt/before.txt,.ai/mqtt/after.txt
```

The snapshot captures **retained** topics only (`--retained-only`), so it is
reproducible rather than a race: discovery configs and last-known states survive a
reconnect. Topics are sorted, so two snapshots diff cleanly. `-Watch` prints live
traffic instead, for checking that a pushbutton event actually publishes.

Read the diff's **GONE** section first. A discovery config that was retained
before and is absent now means an entity Home Assistant still shows and nothing
publishes to any more — exactly the silent regression an `EntityType` mistake
causes, and exactly what a clean compile cannot tell you.

Broker for this project is `10.101.1.11:1883` (`GVL_MQTT.broker`), and the
trees worth watching are `homeassistant/#` and `Devices/PLC/Lab/#`
(`GVL_MQTT.MqttBaseTopic`). Credentials via `-User` / `-Password` if the
broker needs them.

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
