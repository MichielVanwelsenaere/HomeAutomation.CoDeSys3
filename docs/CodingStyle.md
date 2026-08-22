# Coding style

One convention, applied to everything. If you are adding a block, a datatype or a
variable, this page decides its name — there is nothing to weigh up and nothing to
ask.

Two rules, because objects and variables genuinely differ:

- **Objects** — `PREFIX_` + `SCREAMING_SNAKE`.
- **Variables** — type prefix + `PascalCase`.

The variable half is [the CODESYS naming convention](https://content.helpme-codesys.com/en/LibDevSummary/varnames.html)
verbatim. The object half is ours: the published guide covers variables only, and
the object prefixes people associate with CODESYS (`FB_`, `E_`, `ST_`, `I_`) come
from Static Analysis settings, which are configurable rather than normative. So
this page follows CODESYS where CODESYS has an opinion, and says so where it does
not.

## Table of contents

- [Objects](#objects)
- [Variables](#variables)
  - [Type prefixes](#type-prefixes)
  - [Composing prefixes](#composing-prefixes)
  - [Scope markers](#scope-markers)
  - [Library and vendor types](#library-and-vendor-types)
- [Exemptions](#exemptions)
- [Why b and not x](#why-b-and-not-x)
- [Checking your work](#checking-your-work)

## Objects

| Kind | Prefix | Example |
|:--|:--|:--|
| Function block | `FB_` | `FB_OUTPUT_BINARY_MQTT` |
| Function | `F_` | `F_SWAP_WORDS_TO_REAL` |
| Program | `PRG_` | `PRG_MAIN` |
| Interface | `I_` | `I_RS485_DEVICE` |
| Enumeration | `E_` | `E_RELAY_TYPE` |
| Structure | `ST_` | `ST_RS485_STEP` |
| Array alias | `A_` | `A_RS485_STEP_LIST` |
| Global variable list | `GVL_` | `GVL_MQTT` |
| Method, property | *no prefix*, `PascalCase` | `InitMqtt`, `ResolveEntityId` |
| Action | *no prefix*, `SCREAMING_SNAKE` | `MAIN_INIT`, `HVAC_RUN` |

Rules that follow from the table and are worth stating anyway:

- **Enumerations are singular.** `E_HVAC_MODE`, not `E_HVAC_MODES` — a variable of
  that type holds one mode.
- **Enumeration values are not variables** and take no prefix. They stay
  `PascalCase`: `E_MQTT_ENTITY.LightDimmer`, `E_RELAY_TYPE.NC`.
- **Methods keep `PascalCase`** rather than the object rule, because they read as
  calls at the call site, and because every method in the project already does.
- **Actions keep `SCREAMING_SNAKE`.** They are only ever named from an SFC chart,
  and a chart cannot be edited by script — see `CLAUDE.md` at the repository
  root. Renaming one is hand-work in the IDE, so the convention is the one they
  already follow.
- **No plurals on collections.** An array's prefix already says it is one:
  `astRs485Steps` is fine because the *variable* is plural, `A_RS485_STEP_LIST`
  names the type.

## Variables

Prefix, then `PascalCase`. `bStartup`, `sFriendlyName`, `pMqttPublishQueue`,
`awReadBuffer`.

### Type prefixes

| Type | Prefix | | Type | Prefix |
|:--|:--|:--|:--|:--|
| `BOOL` | `b` | | `REAL` | `r` |
| `BYTE` | `by` | | `LREAL` | `lr` |
| `WORD` | `w` | | `STRING` | `s` |
| `DWORD` | `dw` | | `WSTRING` | `ws` |
| `LWORD` | `lw` | | `TIME` | `t` |
| `SINT` / `USINT` | `si` / `usi` | | `LTIME` | `lt` |
| `INT` / `UINT` | `i` / `ui` | | `DATE_AND_TIME` | `dt` |
| `DINT` / `UDINT` | `di` / `udi` | | `TIME_OF_DAY` | `tod` |
| `LINT` / `ULINT` | `li` / `uli` | | `DATE` | `dat` |

And for everything that is not a base type:

| Kind | Prefix | Example |
|:--|:--|:--|
| Enumeration | `e` | `eRelayType : E_RELAY_TYPE;` |
| Structure | `st` | `stComPortSettings : SysCom.SysComSettings;` |
| Function block instance | `fb` | `fbDoBin001 : FB_OUTPUT_BINARY_MQTT;` |
| Interface instance | `itf` | `itfTransport : I_RS485_TRANSPORT;` |
| Pointer | `p` | `pMqttPublishQueue` |
| Reference | `r` | `rBusController` |
| Array | `a` | `awReadBuffer` |
| Handle | `h` | `hComPort : RTS_IEC_HANDLE;` |

`h` is ours, not the guide's: the guide has no handle prefix and the runtime
handle types (`RTS_IEC_HANDLE`, `CAA.HANDLE`) are neither struct nor scalar in any
useful sense. It was already in use in `FB_RS485_TRANSPORT_RTU`, so it is written
down rather than invented.

### Composing prefixes

Prefixes stack outermost first, so the name reads the way the declaration does:

| Declaration | Name |
|:--|:--|
| `POINTER TO STRING` | `psMqttPublishPrefix` |
| `POINTER TO FB_MQTT_PUBLISH_QUEUE` | `pfbMqttPublishQueue`, or `pMqttPublishQueue` |
| `ARRAY[0..7] OF WORD` | `awData` |
| `ARRAY[1..8] OF ST_RS485_STEP` | `astRs485Steps` |
| `POINTER TO A_RS485_READ_BUFFER` | `paRs485ReadBuffer` |

The second row is a deliberate softening. Stacking every prefix on a pointer to a
function block produces `pfb…`, which nobody reads as clearer; `p` alone is
accepted for a pointer to an FB, a struct or an interface, since the pointee's
kind is already obvious from the name that follows. Do not soften anything else.

### Scope markers

| Scope | Marker | Example |
|:--|:--|:--|
| Constant | `c` | `cMaxDevices : INT := 8;` |
| Global | `g` | `gPublishQueue` |
| Member (private, of a base class) | `_` | `_InstancePath` |

The marker goes before the type prefix: `cbEnableDebug`, `gpPublishQueue`.

In practice `g` is rare here, because globals live in a GVL and are always read
qualified (`GVL_MQTT.fbMqttPublishQueue`) — the GVL name is the scope marker, and
doubling it up adds nothing. Prefix a global with `g` only when it is *not*
reached through its list.

### Library and vendor types

Third-party types keep their own names — we do not rename anything inside
`src/Libraries/` or a vendor package. Only the variable is ours, and this is the
prefix it takes:

| Type | Prefix | Type | Prefix |
|:--|:--|:--|:--|
| `TON`, `TOF`, `R_TRIG`, `F_TRIG` | `fb` | `MQTT.QoS` | `e` |
| `OSCAT_BASIC.*`, `OSCAT_BUILDING.*` FBs | `fb` | `MQTT.CALLBACK_DATA` | `st` |
| `Util.LIN_TRAFO`, `Util.BLINK` | `fb` | `SysCom.SysComSettings` | `st` |
| `MQTT.CallbackCollector`, `MQTT.MQTTClient` | `fb` | `SysCom.SYS_COM_PARITY` | `e` |
| `STRUCT_TO_JSON` | `fb` | `oscat_network.NETWORK_BUFFER_SHORT` | `st` |
| `WagoAppDALI.Fb*` | `fb` | `WagoAppDALI.typBallast` | `st` |
| `RTS_IEC_HANDLE` | `h` | `RTS_IEC_RESULT` | `e` |

## Exemptions

There is exactly one, and it is a correctness constraint rather than taste.

**The MQTT discovery structs are wire format, not code.** Their member names are
published as JSON keys, so renaming a member changes what Home Assistant
receives:

```
TYPE MQTT_DISCOVERY_LIGHT EXTENDS MQTT_DISCOVERY_BASE :
STRUCT
	cmd_t: JSONVAR;    // command_topic
	pl_on: JSONVAR;    // payload_on
	stat_t: JSONVAR;   // state_topic
END_STRUCT
```

`FB_BASE_MQTT_DISCOVERY_DEVICE.PublishEntityConfig` serialises these with
`STRUCT_TO_JSON`, which emits member names verbatim. Prefix `pl_on` to `sPlOn`
and the published config carries `"sPlOn"`, which Home Assistant ignores: every
entity silently stops working, with a clean build and a green `verify`. Nothing in
the toolchain can catch it.

So the `MQTT_DISCOVERY_*` structs are exempt **both ways** — no `ST_` on the type,
no prefixes on the members. They are named after Home Assistant's
[MQTT discovery abbreviations](https://www.home-assistant.io/integrations/mqtt/#abbreviations)
and they follow that document, not this one.

Two boundaries on the exemption:

- It covers the structs' own members only. Local variables inside the
  `InitMqttDiscovery*` and `Create*Entity` methods that populate them are ordinary
  variables and take ordinary prefixes.
- `ST_MQTT_MESSAGE` is **not** covered. It is the internal publish-queue record
  and is never serialised, so it follows the normal rules.

## Why b and not x

The CODESYS table gives `b` to `BOOL` and `by` to `BYTE`, and explicitly reserves
`x`. That is the opposite of Beckhoff/TwinCAT habit, where `x` is `BOOL` and `b`
is `BYTE`, and it is the rule most likely to be "corrected" back by a
well-meaning contributor — this project itself had `xComPortOpen` sitting next to
`bStripJsonRootOk` before the convention landed.

We follow the guide. `bStartup : BOOL;` and `byAddress : BYTE;`. If you have
arrived from TwinCAT, this is the one row to unlearn.

## Checking your work

The compiler enforces none of this, and neither does CI. What does exist:

- `./tools/ai/codesys.ps1 rename -Map <file> -DryRun` reports what a rename would
  touch without writing the project, which is also the fastest way to see whether
  a name is used anywhere.
- `./tools/ai/codesys.ps1 verify` proves the result still builds. A rename that
  compiles is almost always a rename that worked; the exception is a collision
  with an existing name in the same scope, which binds silently to the wrong
  thing. The `rename` task refuses those rather than trying.
- CODESYS's own *Static Analysis* can check naming conventions if you have the
  add-on, configured to the tables above. It is not part of the build here.

Renaming anything already published is a breaking change for the installation
projects that copy blocks out of this repository by name — see
[sync-implementation-project](../.claude/skills/sync-implementation-project/SKILL.md)
and keep it for a major release.
