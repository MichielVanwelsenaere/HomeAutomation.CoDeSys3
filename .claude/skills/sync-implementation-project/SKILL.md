---
name: sync-implementation-project
description: Bring an installation's CODESYS project up to date with this reference project's function blocks, without changing what that installation does. Use when an implementation project (a real building, e.g. SiteA.project) has fallen behind the reference, when checking whether such a project is still CODESYS-version-compatible with the reference, or when comparing an installation project against this one.
---

# Syncing an installation project to the reference

This repository is the **reference project**. Real buildings run **installation
projects** — separate `.project` files, in other repositories, each wired to its
own I/O, its own rooms, its own equipment. They share the function blocks and
data types; they do not share logic.

A sync moves the shared half and leaves the other half exactly as it was:

| | Owned by | Synced |
|:--|:--|:--|
| `FUNCTION_BLOCK`, `FUNCTION`, `TYPE`, `INTERFACE` in the project-level POU pool | the reference | **yes** |
| `PROGRAM` (`PLC_PRG_MAIN`, …) — which blocks exist, on which channels | the installation | never rewritten; call sites migrated when an interface changed (§6b) |
| `VAR_GLOBAL` (`MqttVariables`, `PersistentVars`) — the instance declarations | the installation | never rewritten; **appended** with shared constants the blocks need (§4) |
| Task configuration, device tree, I/O modules, I/O mapping | the installation | never |
| Blocks the installation invented for itself | the installation | never |

The two qualified rows are where the real work is. Both are append-or-migrate
only, both are checked afterwards, and neither ever changes what the building
does.

The dividing line is structural, not a naming convention: **anything filed under
a device node belongs to the installation; anything at project level is shared
library code.** The planner applies that rule plus the declared kind, so a
site's own `FB_VIRTUAL_BOOL_MQTT` under `VIRTUAL/` is left alone and a site's
`PLC_PRG_MAIN` is never touched.

### The names on this page are the installation's, not the reference's

The reference project renamed its objects to the convention in
[docs/CodingStyle.md](../../../docs/CodingStyle.md): `MqttVariables` is
`GVL_MQTT` there, `PersistentVars` is `GVL_PERSISTENT`, `PLC_PRG_MAIN` is
`PRG_MAIN`. An installation keeps its own spelling until it is migrated, which is
exactly why the names above are still the old ones — they name objects this skill
promises never to rewrite.

Consequence for a sync across that boundary: a synced block now refers to
`GVL_MQTT`, so the installation's GVL has to be renamed in the same window or
every synced block fails with `Identifier 'GVL_MQTT' not defined`. Use the
`rename` task for it (see the `codesys-loop` skill), against the installation
project, before syncing the blocks. That is a breaking, one-off migration and it
belongs to the major release, not to a routine sync.

## Before anything else

An installation project is a building's running control program. Two rules, and
neither is negotiable:

- **Never download.** `codesys.ps1 download` refuses a `-Project` override
  outright. Do not work around it. This skill changes files on disk and nothing
  else.
- **Never sync in place.** The installation project may not be under source
  control. Work on a copy in `.ai/sync/`, and only replace the original once the
  copy has built cleanly, passed the logic-unchanged check, *and* the user has
  said in so many words to replace it.

Read `codesys-loop` first if you have not — the tasks below are its tasks, with
`-Project` pointed elsewhere. Its warnings apply here too, especially: **a clean
build does not mean checked**, and **an edit can report success without taking
effect**.

**A sync is two passes, not one.** Pass one brings the blocks across (§1–§7).
Pass two brings the installation onto the *way* the reference now configures
those blocks (§6c) — a refactor the compiler cannot ask for, because the old
style still works. Skipping pass two produces a project that builds clean,
passes every check, and has not caught up. Plan for both from the start.

## The loop

Each CODESYS task boots the IDE, so budget 60–120 seconds per step. Everything
lands in `.ai/`, which is gitignored.

### 1. Toolchain and working copy

```powershell
./tools/ai/codesys.ps1 doctor
$impl = 'C:\path\to\SiteA.project'
./.claude/skills/sync-implementation-project/scripts/Working-Copy.ps1 new -Target $impl
```

The copy lands at `.ai/sync/<stem>/<stem>.project`. Everything from here on
targets the **copy**, except the `info` in step 2, which reads the original
read-only to describe what is actually deployed.

### 2. Describe both projects

```powershell
$copy = '.ai\sync\SiteA\SiteA.project'
./tools/ai/codesys.ps1 info -Full -Output .ai\sync\reference.json
./tools/ai/codesys.ps1 info -Full -Project $copy -Output .ai\sync\before.json
```

`info` opens a project **read-only with `VersionUpdateFlags.NoUpdates`**, so
looking at an older installation project never converts it as a side effect.
`-Full` includes source text, which the planner needs to work out dependencies.

The report carries: the IDE version that read it, every library reference, every
device with its id and version, and every code-bearing object with a hash of its
declaration, implementation and members. That hash is what "this block differs
from the reference" means here — not a text diff, not the XML.

### 3. Does the installation project still build as it is?

```powershell
./tools/ai/codesys.ps1 verify -Baseline -Project $copy
```

**This is the version-compatibility gate, and it is the one that matters.** The
compiler version a project stores is not reachable from the scripting API — a
reflection sweep over the application object finds nothing, so do not go looking
again. Building it with the installed IDE answers the question directly: if the
project needs a compiler version, device description or library this install
does not have, the build says so by name.

It also records the baseline, so the post-sync build reports only what the sync
caused. Reports for a foreign project are stem-qualified
(`baseline.SiteA.json`), so this cannot overwrite the reference
project's own baseline.

**If this build is not clean, stop.** A sync onto a project that was already
broken cannot be assessed, because every later message is ambiguous.

### 4. Plan

```powershell
py .claude/skills/sync-implementation-project/scripts/plan_sync.py `
   --reference .ai/sync/reference.json `
   --implementation .ai/sync/before.json `
   --out .ai/sync/plan.json --emit-edits .ai/sync/edits
```

The plan prints a compatibility verdict and five lists: what to update, what was
pulled in as a dependency, what is already identical, what belongs to the
installation, and what needs a human. Exit codes: `0` clean, `2` incompatible,
`3` something needs a decision.

Read it before running anything else, and **show the user the update list and
the left-alone list**. This is the point where a misclassification is cheap to
catch and expensive to miss.

Two behaviours worth knowing:

- **Dependencies are pulled in automatically.** If an updated block references a
  type the installation has never had — `E_MQTT_ENTITY` is the real example —
  the type is added too, transitively. Without that the sync produces
  `Identifier 'E_MQTT_ENTITY' not defined` and nothing in the plan explains why.
- **Unreferenced new blocks are not.** A block the installation never used is
  dead code there; adding it is a scope decision. `--add-missing` includes them
  if the user asks for that.

`--emit-edits` additionally writes `.ai/sync/edits/` with the **global-variable
members the synced blocks need and the installation lacks**. The shared/logic
split is not clean at the GVL boundary: `MqttVariables` holds a building's
instance declarations *and* shared infrastructure the blocks read, such as the
`MQTT_TOPIC_LEN` / `MQTT_SUFFIX_LEN` string-length constants. Without them every
synced block fails with `Identifier 'MqttVariables.MQTT_TOPIC_LEN' not defined`
and the GVL is the last place anyone looks, because the GVL is on the
do-not-touch list.

The generated edit is an **append with an idempotence sentinel** — nothing
existing is rewritten, so no instance declaration can be lost, and re-running
does not declare anything twice. `check_logic_unchanged.py` re-verifies that
append-only property line by line afterwards. Anything beyond an append is a
human's call.

### 5. Lift the blocks out of the reference

```powershell
$plan = Get-Content .ai/sync/plan.json -Raw | ConvertFrom-Json
Remove-Item .ai\sync\candidates -Recurse -Force -ErrorAction SilentlyContinue
./tools/ai/codesys.ps1 export -Only $plan.export -Output .ai\sync\candidates\shared.xml
```

`-Only` exports exactly those objects and errors out by name if one is not
found, rather than quietly exporting less than asked. The export carries folder
structure, which the import needs.

### 6. Verify the sync on a sandbox

```powershell
./tools/ai/codesys.ps1 verify -Project $copy -Candidates .ai\sync\candidates `
    -ImportFolders -ImportConflict replace -Edits none
```

All four flags are load-bearing:

- **`-ImportConflict replace`** — without a conflict policy the importer has no
  say in what happens when the object already exists, and what it does is add a
  *second* one. The installation keeps compiling its old block and the sync
  achieves nothing.
- **`-ImportFolders`** — a candidate exported from another project carries
  folders; without the flag the block lands at the project root beside the real
  one, is never compiled, and the build stays green while the sync has done
  nothing. The two flags fail the same way and are needed together.
- `-Candidates` keeps the sync's set separate from `.ai/candidates`, so a
  half-finished block edit cannot ride along into a building's project.
- `-Edits none` because this repo's edit spec targets the reference project.

`verify` sandboxes into `.ai/work` — the working copy is not written yet.

Read `NEW vs baseline`, not just the result line. Expect breakage here — see the
next section, which is where most of the work in a real sync actually is.

### 6b. Call-site migrations

A block whose interface changed leaves the installation's programs calling
something that no longer exists. On the first real sync of SiteA that
was four errors in two programs: `FB_OUTPUT_COVER_MQTT` had replaced
`ConfigureFunctionBlock` with `FB_init` parameters, and `FB_MqttPublishQueue`
had replaced an `EMPTY` flag with `HasMessage()`.

These have to be fixed for "all blocks updated" to mean anything — an
un-buildable project is not a delivered sync. But they edit the installation's
own code, so:

- **Behaviour-preserving only.** Same values, same conditions, different
  spelling. `EMPTY` becomes `NOT HasMessage()`, not "roughly equivalent".
  A timing moves from a runtime call to an `FB_init` argument at the same value.
- **Never invent behaviour** to satisfy a new parameter. If the new interface
  needs a value the installation never had, that is a question for the user.
- **Every migration is reported by name** and is listed in the check output.

Author them in `.ai/sync/edits/migrations.json`, which `plan_sync.py` folds into
the generated `edits.json` — its own file, so re-running the planner cannot wipe
it:

```json
{ "edits": [
  { "pou": "PLC_PRG_MAIN",
    "replace_in_decl": [
      { "find": "FB_DO_COVER_001\t\t\t\t:FB_OUTPUT_COVER_MQTT;",
        "with": "FB_DO_COVER_001\t\t\t\t:FB_OUTPUT_COVER_MQTT(T#1S, T#20S);",
        "count": 1 } ] },
  { "pou": "PLC_PRG_MQTT", "member": "MQTT_PUBLISH",
    "replace_in_body": [
      { "find": "NOT(MqttVariables.fbMqttPublishQueue.EMPTY)",
        "with": "MqttVariables.fbMqttPublishQueue.HasMessage()", "count": 1 } ] }
] }
```

`count` is worth setting every time: it turns "I expected one call site and there
were three" from a silent over-edit into a failure.

**Never hand-type a `find` string.** ST here is tab-aligned, and the tabs do not
survive being read off a screen — the first attempt at the cover migration used
seven tabs where the source had eleven, and `replace_in_body` refused it. Extract
the exact substring from the `-Full` info report instead:

```python
impl = <the member's "impl" text from before.json>
i = impl.find("FB_DO_COVER_001.ConfigureFunctionBlock")
find = impl[i:impl.find(");", i) + len(");\n\n")]
assert impl.count(find) == 1
```

A miss is an error, not a no-op, which is the one thing that makes this safe:
a half-applied migration cannot pass as a success.

**`FB_init` arguments: adding is safe, changing is not.** Giving an instance that
had *no* arguments a `FB_init` list works — CODESYS parses it from the
declaration text, and the cover migration above is verified to land. **Changing
an argument an instance already has does not reach the compiler at all**; the
value lives in `InputAssignments` metadata that no script can touch. `apply` and
`verify` print an ADVISORY when an edit changes an existing argument list. If
you see one, that edit did nothing — do it in the IDE. `CLAUDE.md` has the full
account.

### 6c. Configuration-style migrations — a green build is not "done"

**This is the step most likely to be skipped, and skipping it is invisible.**

The reference does not only change what is *inside* a block. It changes **how a
block is configured**, and those refactors are deliberately backwards
compatible — the old way keeps working. So the project compiles, `NEW vs
baseline` reads 0, every check passes, and the installation is still written in
the previous generation's style. Nothing fails. It just never catches up.

The case in this project is **self-wiring**. A block that carries the
`self-wiring prologue` in its body and inherits `FriendlyName` from
`FB_MQTT_BASE` configures itself from its declaration:

```iecst
FB_DO_LIGHT_001  :FB_OUTPUT_BINARY_MQTT := (FriendlyName := 'Landing spots',
                                            EntityType := E_MQTT_ENTITY.Light);
```

…which replaces roughly thirty lines of `InitMqtt` / `InitMqttDiscoveryAsLight`
in `MAIN_INIT` per instance. Detect and generate it:

```powershell
py .claude/skills/sync-implementation-project/scripts/plan_declaration_migration.py `
   --implementation .ai/sync/after.json --out .ai/sync/decl/migrations.json
```

Run it **after** the block sync, against the post-sync inventory — the
self-wiring prologue only exists in the project once the blocks have landed.
Then verify and apply it as a second pass, exactly like §6b but with no
candidates.

Three things it gets right that a careless hand edit does not:

- **The friendly name comes from the `Name :=` argument, never from the
  trailing comment.** In SiteA, `FB_DO_LIGHT_005` is commented
  `// Hall` and announces to Home Assistant as `'Landing'`. Believe the code.
  Copy the name **verbatim**, including what looks like a typo — that site's
  pushbutton 002 announces as `'Kithcen'` where the comment says `Kitchen`, and
  "fixing" it renames a live Home Assistant entity. Mention it; do not correct
  it.
- **`InitMqttDiscoveryAsLight` becomes `EntityType := E_MQTT_ENTITY.Light`.**
  A binary output's default platform is Switch. Drop the `EntityType` on a
  block that was announcing as a Light and you orphan its retained
  `light/.../config` topic and create a *second*, switch entity in Home
  Assistant. No compiler and no build catches that; only an MQTT snapshot diff
  does.
- **An instance that is never called cyclically is refused.** Self-wiring
  happens on the block's first cyclic call, so moving a never-called instance
  onto its declaration would silently remove it from Home Assistant, where the
  init action used to wire it regardless. It is left as an explicit call and
  reported.

The generated edits are ordinary `replace_in_decl` / `replace_in_body` rules —
read them before applying, and note that the script *appends* to an existing
`migrations.json` rather than overwriting your hand-written ones.

**Then tidy the init action by hand.** Deleting thirty statements leaves the
section comments that headed them (`(* Light 001 *)`, `(* INIT COVERS STUFF *)`)
pointing at nothing. The script collapses the blank runs, because that is
mechanical; it cannot tell which comments are now lies. Replace what is left
with a short header saying where the wiring went, modelled on the reference's own
`MAIN_INIT` — otherwise the next person reads an action full of headings for
code that is not there and goes looking for it. A comments-only `body_replace`
carrying the remaining executable statements across verbatim cannot change
behaviour, and the before/after check still proves only that program moved.

**Check the result over MQTT.** This is the one migration where a clean build
proves the least: it changes which discovery topics get published and under
which platform. Snapshot the broker before and after with
`tools/ai/Mqtt-Snapshot.ps1` and read the **GONE** section — a discovery config
that was retained before and is absent after is an entity Home Assistant still
shows and nothing publishes to any more. See `codesys-loop`.

**Generalising.** The detector encodes one specific pattern because that is the
one this reference uses. When the reference introduces the *next* configuration
refactor, the sync will again compile clean and again be incomplete. The
question to ask at the end of every sync is not "does it build" but **"is the
installation now written the way the reference is written?"** — compare the
reference's own `PLC_PRG_MAIN` declaration and init action against the
installation's and see whether they are the same shape.

### 7. Apply to the working copy

```powershell
./tools/ai/codesys.ps1 apply -Project $copy -Force -Candidates .ai\sync\candidates `
    -ImportFolders -ImportConflict replace -Edits none
```

Writes and saves the **copy**. `apply` refuses to save if the build fails, and
injects no harness — so verify first, always.

### 8. Prove it changed only what it was supposed to

```powershell
./tools/ai/codesys.ps1 info -Full -Project $copy -Output .ai\sync\after.json
py .claude/skills/sync-implementation-project/scripts/check_logic_unchanged.py `
   --before .ai/sync/before.json --after .ai/sync/after.json `
   --plan .ai/sync/plan.json --migrations .ai/sync/edits/migrations.json
```

A clean build says the project compiles. It does not say the sync left the
programs, the GVLs and the I/O alone. Only this does. It fails on four things,
each of which has actually happened somewhere in this toolchain:

- an object changed that was not on the plan,
- an object was removed, added or moved that was not on the plan,
- an object on the plan did **not** change — the import silently did nothing,
- a GVL append that turned out not to be append-only, checked line by line,
- a listed migration that did not actually change its object,
- anything else the installation owns differing at all.

It also prints **compile coverage**, which is how to read `verify`'s
`NOT COMPILE-CHECKED` list. On a sync that warning is usually a false alarm: the
harness cannot auto-declare a block whose `FB_init` takes parameters, but the
installation's own programs and GVLs declare those blocks for real and those
objects *are* compiled. The coverage check works out which planned blocks the
installation's own compiled code actually names, instead of assuming. A block in
the uncovered list is genuinely unverified — nothing instantiates it, so nothing
compiled it — and must be reported as such.

Run `codesys.ps1 compare -Project $copy -Against src\HomeAutomation.project` if
you want CODESYS's own object-level diff as a second opinion; it is slower and
coarser, but it is independent of the hashing above.

### 9. Hand it back

Report to the user: the compatibility verdict, the list of blocks updated, any
compiler messages new versus baseline, and the check result. Then **ask** whether
to replace the original. Only after they say yes:

```powershell
./.claude/skills/sync-implementation-project/scripts/Working-Copy.ps1 promote -Target $impl -Force
```

`promote` takes a timestamped backup of the original into
`.ai/sync/<stem>/backups/` first. It replaces a file and nothing more — the PLC
keeps running whatever was last downloaded to it until someone opens the project
in the IDE and downloads it deliberately.

## Things that will bite

**Programs appear twice.** A program lives under `PRG's/` and is *called* from a
node under `Task Configuration/<task>/`, and both objects carry the same name.
The call node holds no code. Indexing an inventory by name without filtering it
hands you the empty one for every program in the project, and they all read as
"no declaration, no kind" and get misclassified. The reports carry
`is_task_call` for exactly this; the planner filters on it and reports any name
that is still ambiguous rather than picking one.

**`FB_init` arguments are not in the declaration text.** The reference project's
`CLAUDE.md` documents this at length and it applies double here: an instance in
the installation's GVL carries its `FB_init` arguments in `InputAssignments`
metadata that no script can reach. A synced block whose `FB_init` signature
changed will therefore compile against stale argument values on the installation
side. If a plan touches a block with an `FB_init`, say so explicitly — that one
needs the IDE.

**The installation may extend a reference block.** `FB_VIRTUAL_*` in
SiteA sit in the site's own folder but derive from `FB_MQTT_BASE`. A
change to the base surfaces as an error in a site-only block, which looks like
the sync broke something it never touched. It did not — the base changed, and
the site's derived block has to catch up. That is a report-to-the-user outcome.

**Placeholders make the library check meaningful, not vacuous.** Both projects
reference libraries almost entirely as placeholders (`#MQTT`, `#OSCAT_BASIC`),
which resolve through the installed library repository. Two projects opened by
the same IDE resolve them identically, so an identical reference set really is a
guarantee. A *fixed* reference (`NETWORK, 1.3.5.3 (OSCAT)`) pins a version and
must match exactly; the planner treats a missing one as blocking.

**Prove an initialiser landed — do not assume it.** A declaration edit that the
compiler ignores produces a clean build, a correct-looking export and a PLC
running the old value; that is the `FB_init` trap, and a structured initialiser
is close enough to it to be worth checking rather than trusting. Export the
program and look at how CODESYS stored it:

```powershell
./tools/ai/codesys.ps1 export -Project $copy -Only PLC_PRG_MAIN -Output .ai\sync\decl\PLC_PRG_MAIN.xml
```

Two things to find, and both were confirmed present for SiteA:

```xml
<variable name="FB_DO_LIGHT_001">
  <type><derived name="FB_OUTPUT_BINARY_MQTT" /></type>
  <initialValue><structValue>
      <value member="FriendlyName"><simpleValue value="'Landing spots'" /></value>
      <value member="EntityType"><simpleValue value="E_MQTT_ENTITY.Light" /></value>
  </structValue></initialValue>
```

A `:= (...)` initialiser is stored as `<initialValue><structValue>`, which **is**
what the compiler reads — so unlike an `FB_init` argument, this migration is
safe to make from a script. And on the covers, `InputAssignments` reads
`TIME#1s0ms` / `TIME#20s0ms`, which proves the §6b `FB_init` arguments reached
the compiler too, not merely the text. That is the check that distinguishes
"added arguments to an instance that had none" (works) from "changed an existing
argument" (silently does not).

**A block's inputs are declared on its base, not on itself.** Anything that asks
"does this block have `FriendlyName`?" has to walk `EXTENDS` — the input is
declared once on `FB_MQTT_BASE` and inherited by fifteen blocks. Looking at a
derived block's own declaration finds nothing, and a detector written that way
reports cheerfully that there is nothing to migrate. That is exactly how the
first version of `plan_declaration_migration.py` found zero instances in a
project with thirteen.

**Do not run this against `src/HomeAutomation.project`.** It is the source, not a
target. `compare` refuses when both sides are the same file; nothing else checks,
so pass `-Project` deliberately.

## Worked example: SiteA, first sync

> **`SiteA` is a placeholder, and so is every room and device name in this
> file.** An installation project is named after the building it runs, and a
> building is somebody's address — as are the names on its lights and
> pushbuttons. This repository is public. Keep real ones out of it: out of the
> skills, out of commit messages, out of PR descriptions. Nothing here needs a
> real name to make sense, and the examples are written so that placeholders
> lose nothing.

The numbers a real run produced, as a sanity check that yours is in the right
shape:

| | |
|:--|:--|
| Compatibility | same IDE 3.5.21.30, identical 36-library reference set, same PFC200 `0013 / 4.19.0.0`. Untouched project built clean with 5 pre-existing warnings. |
| Shared blocks updated | 24 |
| Types pulled in as dependencies | 2 (`E_MQTT_ENTITY`, `MQTT_DISCOVERY_FAN`) |
| Already identical | 27 |
| Global constants appended | 2 into `MqttVariables` (+12 lines, append-only verified) |
| Call sites migrated | 2 programs, 5 substitutions |
| Left alone | 5 site-only blocks under `VIRTUAL/`, 3 device nodes, the whole task configuration and I/O tree |
| Result | `NEW vs baseline: 0`, logic-unchanged check passed |

**Read the coverage line.** In that run only 15 of the 26 synced objects are
reachable from SiteA's own code — it has binary outputs, covers and
RS485, and no dimmers, no HVAC and no binary sensors. The other 11 were updated
correctly but *nothing in that project compiles them*, so its clean build says
nothing about them. They are compile-checked in the reference project, which
does instantiate them; say that rather than implying the sync verified them.

The first attempt at the whole thing produced **40 errors**, which is what a
sync looks like before the GVL constants and the call-site migrations are in
place. That is the normal path, not a sign something went wrong.

**And it was still not finished.** Everything above passed — clean build, zero
new messages, logic-unchanged check green — and `MAIN_INIT` was still ~180 lines
of `InitMqtt` / `InitMqttDiscovery*` calls written in the previous generation's
style, because the reference keeps that style working. The second pass (§6c):

| | |
|:--|:--|
| Instances moved onto their declaration | 13 (4 pushbuttons, 2 covers, 6 lights, 1 outlet) |
| Init calls deleted from `MAIN_INIT` | 26 |
| `MAIN_INIT` size | ~7000 → 699 → 850 characters after the tidy, one executable statement left |
| Entity platforms preserved | 6 × `E_MQTT_ENTITY.Light`, 1 × `Switch` |
| Result | `NEW vs baseline: 0`, only `PLC_PRG_MAIN` changed |

**A sync takes two passes: the blocks, then the way the blocks are configured.**
Budget for both. The second one is the one nothing will remind you about.
