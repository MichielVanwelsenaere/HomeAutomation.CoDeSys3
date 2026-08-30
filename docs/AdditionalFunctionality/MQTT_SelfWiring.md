# Naming a block instead of wiring it

Function blocks used to need two calls in an init action before they would do
anything: `InitMqtt(...)` to hand them the publish queue, the topic prefixes and
the callback collector, and `InitMqttDiscovery*(...)` to announce them to Home
Assistant. Everyone using this project uses MQTT, so that plumbing was the same
every time and only got in the way.

Now a block wires itself. The only thing you have to say is the name you want to
see in Home Assistant, and you say it where you declare the instance:

```iecst
PROGRAM PRG_MAIN
VAR
    FB_DO_BIN_001  : FB_OUTPUT_BINARY_MQTT := (FriendlyName := 'Kitchen light',
                                               EntityType := E_MQTT_ENTITY.Light);
    FB_DO_COVER_001: FB_OUTPUT_COVER_MQTT  := (FriendlyName := 'Living room blind');
END_VAR
```

That is the whole configuration. No `InitMqtt`, no `InitMqttDiscovery`.

## What the block does on its own

On its **first cyclic call** a named block reaches into the `GVL_MQTT`
global variable list for everything it used to be handed — the publish queue, the
publish and subscribe topic prefixes for its category, its callback collector,
and the Home Assistant device — and then announces itself for discovery. The MQTT
topic is still derived from the instance name (`FB_DO_BIN_001`), exactly as
before, so **topics and entity ids do not change**.

Two consequences worth knowing:

- **A named block must be called cyclically.** Its wiring happens in its body, so
  an instance that is never invoked — or is only invoked inside a conditional
  branch that stays false — never wires itself and never appears in Home
  Assistant. The old init action wired it regardless. Nothing warns about this.
- **Anything that shows up in a discovery payload must be configured before that
  first call.** `ConfigureFunctionBlock` and friends belong in the init step, where
  they already are. Moving one into a cyclic action would publish a discovery
  config built from zeros, with no error anywhere.

  The way to sidestep that ordering trap entirely is to take the value at the
  declaration instead, via `FB_init` — it has run before the first cycle by
  construction, so no ordering rule is left for anyone to break.
  `FB_OUTPUT_COVER_MQTT` does this with its `T_LOCKOUT` and `T_UD` and has no
  `ConfigureFunctionBlock` at all. It suits values that describe the hardware and
  never change while the PLC runs. Note CODESYS requires every `FB_init` argument
  at every declaration site, so adding one is a breaking change for existing
  projects — unlike a `VAR_INPUT` default.

## `EntityType`

Most blocks announce themselves as exactly one kind of Home Assistant entity and
you can ignore `EntityType`. Some can be more than one thing —
`FB_OUTPUT_BINARY_MQTT` and `FB_OUTPUT_BISTABLE_MQTT` can appear as a switch, a
light, a lock, a siren or a valve — and there `EntityType` picks which:

| Value | Announced as |
|:--|:--|
| `E_MQTT_ENTITY.Default` | whatever that block has always defaulted to |
| `E_MQTT_ENTITY.Light` | `light` |
| `E_MQTT_ENTITY.Lock` | `lock` |
| `E_MQTT_ENTITY.Siren` | `siren` |
| `E_MQTT_ENTITY.Valve` | `valve` |
| `E_MQTT_ENTITY.Switch` | `switch` |
| `E_MQTT_ENTITY.Fan` | `fan` |

A fan is announced as on/off only. Home Assistant's fan platform requires just
`command_topic`; `percentage_command_topic` and `oscillation_command_topic` are
supported by `CreateFanEntity` but left empty here, because a binary output has no
speed or oscillation state to report. A dimmer-backed fan would pass them. Preset
modes are not supported — `preset_modes` is a JSON list, which this one-`JSONVAR`-
per-field struct cannot express.

> **If you are migrating an existing project, check this one.** A block you used
> to announce with `InitMqttDiscoveryAsLight` must now say
> `EntityType := E_MQTT_ENTITY.Light`. Leave it out and the project still compiles
> perfectly, but Home Assistant gains a new `switch.` entity while the old
> retained `light/.../config` topic is orphaned — the light disappears from your
> dashboards and automations.

## `RelayType`

Say which way round the contact the output drives actually sits:

| Value | The load is live when | Typical use |
|:--|:--|:--|
| `E_RELAY_TYPE.NO` | `OUT` is `TRUE` | the default; almost every lighting circuit |
| `E_RELAY_TYPE.NC` | `OUT` is `FALSE` | sockets, and anything that must survive a dead controller |

```iecst
FB_DO_SW_RE : FB_OUTPUT_BINARY_MQTT := (FriendlyName := 'Living room sockets',
                                        EntityType   := E_MQTT_ENTITY.Switch,
                                        RelayType    := E_RELAY_TYPE.NC);
```

This changes nothing in the PLC — the output behaves identically either way — and
everything in the discovery config, where it swaps the `payload_on` /
`payload_off` pair so Home Assistant reports the state of the **load** rather than
the state of the coil. Leave it at `NO` on an NC circuit and the entity reads
exactly backwards: "off" while the sockets are live. Nothing catches that, because
nothing in the PLC is wrong.

The default is `NO` and `NO` is `0`, so an instance that says nothing behaves as
it always has.

Only the blocks whose discovery methods take it honour it —
`FB_OUTPUT_BINARY_MQTT` and `FB_OUTPUT_BISTABLE_MQTT`. It lives on `FB_MQTT_BASE`
alongside `FriendlyName` and `EntityType`, so it is accepted and ignored
elsewhere, the same way `EntityType` is on a block that can only be one thing.

## Leaving a block unnamed

`FriendlyName` is optional and defaults to empty. An unnamed block does nothing
on its own: it neither wires itself nor announces itself, and it behaves exactly
as it did before this change. That is what keeps existing projects working, and it
is also how you deliberately keep an instance silent.

## When you still need the Init methods

`InitMqtt` and `InitMqttDiscovery*` are unchanged and still public. Call them
yourself when the declaration cannot express what you need:

- a second broker, or a publish queue other than `GVL_MQTT.fbMqttPublishQueue`
- a topic prefix that is not the standard one for that block's category
- a `DeviceClass`, `overruleId` or `meta` on the discovery config
- a per-instance Home Assistant device rather than the shared `PLC_Device`

Leave `FriendlyName` empty when you do, so the block does not also wire itself.
And keep the order: `InitMqtt` first, then `InitMqttDiscovery*` — the discovery
methods do nothing until `InitMqtt` has run.

## Which blocks self-wire

**Self-wiring**, driven by `FriendlyName`: the pushbutton, binary sensor and RTD
temperature inputs, the binary, bistable, cover and dimmer outputs, the HVAC
thermostat, pump and burner, the DMX dimmer, and all three Eastron meter blocks
— the SDM630, the SDM220 and the SDM_POWER.

`FB_RS485_EASTRON_SDM630_MQTT` is the first RS485 block to self-wire, and it shows
what the others would need. Its discovery announces a Home Assistant device of its
own — 26 entities under one meter — which the 1-Wire block below cannot do from a
single name because its device is shared between sensors and lives in the GVL. The
meter sidesteps that by **owning** its discovery device instead of referencing one,
so `FriendlyName` really is the only thing a call site has to supply.

**Still explicit, and deliberately so.** Two blocks have a discovery config that a
single name cannot describe, so they keep both of their calls:

| Block | Why |
|:--|:--|
| `FB_HVAC_COLLECTOR_MQTT` | its discovery carries **a name per valve**, one entity per circuit |
| `FB_RS485_ESERA_OWD_MQTT` | its discovery takes its own HA device, a parent device and six capability flags |

For these, the wiring has to stay next to the discovery call. `InitMqttDiscovery*`
does nothing until `InitMqttDone` is TRUE, and an init action runs a cycle *before*
a block's first body call — so self-wiring them while leaving discovery in the init
action would make that discovery call fire too early and silently announce
nothing.

**Not self-wired.** These two *do* extend `FB_MQTT_BASE`, so `FriendlyName` is
already on them. What they lack is an `InitMqttDiscovery` method — a prologue could
wire their MQTT publishing but would have nothing to announce:

- `FB_INPUT_PUSHBUTTON_DIMMER_MQTT`
- `FB_RS485_DUCO_DUCOBOX_MQTT`

Giving them discovery is the worthwhile follow-up, and the three Eastron meter blocks
are the worked examples of what that looks like for an RS485 block. Until then their
call sites are untouched and keep working exactly as before.

All three Eastron meters now take their Modbus address, poll rate and — for the
SDM_POWER block — the meter model through `FB_init`, so their whole configuration
is the declaration and `RS485_INIT` does nothing for them but register them on the
bus. That is the shape to copy: a value that describes the wiring rather than a
mode belongs in `FB_init`, where it is settled before the first cycle and cannot
be forgotten at a call site.

`FB_RS485_EASTRON_SDM_POWER_MQTT` shows why that matters for discovery. The model
it announces itself as is derived from `DeviceType`, so a name alone does not
describe it — and because `FB_init` settles `DeviceType` before the first cyclic
call, the prologue has nothing to wait for. Configuration through `FB_init` and
self-wiring through `FriendlyName` are complementary: together they remove the
whole init sequence rather than half of it.
