# Naming convention — decided, not open

Everything in `HomeAutomation.project` follows one convention, adopted in
issue #179 for the major release. **It is settled.** Do not re-derive it from what
the surrounding code happens to do, do not ask the user which style to use, and do
not "improve" it. The full version with rationale is
[`docs/CodingStyle.md`](../docs/CodingStyle.md); this file is the working summary,
kept here because it is the file an agent editing the project has loaded.

## Objects — `PREFIX_` + SCREAMING_SNAKE

| Kind | Prefix | | Kind | Prefix |
|:--|:--|:--|:--|:--|
| Function block | `FB_` | | Structure | `ST_` |
| Function | `F_` | | Array alias | `A_` |
| Program | `PRG_` | | Global variable list | `GVL_` |
| Interface | `I_` | | Method, property | none, `PascalCase` |
| Enumeration | `E_` | | Action | none, `SCREAMING_SNAKE` |

Enumerations are singular. Enumeration values take no prefix and stay
`PascalCase`.

## Variables — type prefix + PascalCase

`b` BOOL · `by` BYTE · `w` WORD · `dw` DWORD · `si`/`usi` SINT/USINT ·
`i`/`ui` INT/UINT · `di`/`udi` DINT/UDINT · `li`/`uli` LINT/ULINT · `r` REAL ·
`lr` LREAL · `s` STRING · `ws` WSTRING · `t` TIME · `lt` LTIME · `dt` DT ·
`tod` TOD · `dat` DATE

`e` enum · `st` struct · `fb` FB instance · `itf` interface instance ·
`p` pointer · `a` array · `h` handle · `c` constant · `g` global · `_` member

Stacked outermost first: `psMqttPublishPrefix`, `awReadBuffer`, `astRs485Steps`.
A pointer to an FB, struct or interface may take a plain `p` rather than `pfb` /
`pst` / `pitf`.

**`b` is BOOL and `by` is BYTE.** The CODESYS guide reserves `x`. If you are about
to write `xEnable` because that is what you have seen elsewhere, that is the
mistake this line exists to stop.

## The one exemption: MQTT discovery structs

The `MQTT_DISCOVERY_*` structs are **wire format**. `STRUCT_TO_JSON` in
`FB_BASE_MQTT_DISCOVERY_DEVICE.PublishEntityConfig` publishes their member names
as JSON keys, and those keys are Home Assistant's discovery abbreviations —
`cmd_t`, `pl_on`, `stat_t`, `uniq_id`, `avty`, `dev`.

So they are exempt **both ways**: no `ST_` prefix on the type, no prefixes on the
members. Prefixing `pl_on` to `sPlOn` publishes `"sPlOn"`, Home Assistant ignores
it, and every entity stops working — with a clean build, a green `verify` and
nothing in any report to show for it. This is the one naming mistake in this
project that no tool can catch.

Boundaries: the exemption covers those structs' own members only. Local variables
inside `InitMqttDiscovery*` and `Create*Entity` are ordinary and get prefixes.
`ST_MQTT_MESSAGE` is the internal queue record, is never serialised, and follows
the normal rules.

## Renaming, when you do have to

Use `./tools/ai/codesys.ps1 rename -Map <file>` — it renames the object *and*
rewrites every reference, which the IDE's refactoring does not expose to the
ScriptEngine. `-DryRun` reports what would be touched without writing anything.

Three things the root `CLAUDE.md` explains in full and that bite here in
particular:

- A renamed **member** re-derives its stored `structValue`, so instance
  initialisers survive a rename — but confirm with `export` and `<structValue>`,
  never with `info`, which returns the declaration text and is the half that lies.
- Renaming an **`FB_init` parameter** may orphan the stored `InputAssignments`
  behind an instance's argument list. Check by export afterwards; the fix is the
  IDE.
- An **SFC chart cannot be scripted at all**, so renaming an action is IDE
  hand-work. Actions already follow the convention precisely so that this never
  needs doing.
