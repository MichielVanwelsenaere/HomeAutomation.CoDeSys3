# Naming a block instead of wiring it

Function blocks used to need two calls in an init action before they would do
anything: `InitMqtt(...)` to hand them the publish queue, the topic prefixes and
the callback collector, and `InitMqttDiscovery*(...)` to announce them to Home
Assistant. Everyone using this project uses MQTT, so that plumbing was the same
every time and only got in the way.

Now a block wires itself. The only thing you have to say is the name you want to
see in Home Assistant, and you say it where you declare the instance:

```iecst
PROGRAM PLC_PRG_MAIN
VAR
    FB_DO_BIN_001  : FB_OUTPUT_BINARY_MQTT := (FriendlyName := 'Kitchen light',
                                               EntityType := E_MQTT_ENTITY.Light);
    FB_DO_COVER_001: FB_OUTPUT_COVER_MQTT  := (FriendlyName := 'Living room blind');
END_VAR
```

That is the whole configuration. No `InitMqtt`, no `InitMqttDiscovery`.

## What the block does on its own

On its **first cyclic call** a named block reaches into the `MqttVariables`
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

> **If you are migrating an existing project, check this one.** A block you used
> to announce with `InitMqttDiscoveryAsLight` must now say
> `EntityType := E_MQTT_ENTITY.Light`. Leave it out and the project still compiles
> perfectly, but Home Assistant gains a new `switch.` entity while the old
> retained `light/.../config` topic is orphaned — the light disappears from your
> dashboards and automations.

## Leaving a block unnamed

`FriendlyName` is optional and defaults to empty. An unnamed block does nothing
on its own: it neither wires itself nor announces itself, and it behaves exactly
as it did before this change. That is what keeps existing projects working, and it
is also how you deliberately keep an instance silent.

## When you still need the Init methods

`InitMqtt` and `InitMqttDiscovery*` are unchanged and still public. Call them
yourself when the declaration cannot express what you need:

- a second broker, or a publish queue other than `MqttVariables.fbMqttPublishQueue`
- a topic prefix that is not the standard one for that block's category
- a `DeviceClass`, `overruleId`, `meta` or `Invert` on the discovery config
- a per-instance Home Assistant device rather than the shared `PLC_Device`

Leave `FriendlyName` empty when you do, so the block does not also wire itself.
And keep the order: `InitMqtt` first, then `InitMqttDiscovery*` — the discovery
methods do nothing until `InitMqtt` has run.

## Blocks not yet migrated

These still need their explicit `InitMqtt` call:

- `FB_INPUT_PUSHBUTTON_DIMMER_MQTT` — does not extend `FB_MQTT_BASE`; it
  hand-rolls its own MQTT plumbing and has no discovery method.
- The HVAC, RS485, DMX and log blocks — the same prologue applies to them, it has
  simply not been added yet. Their call sites are untouched and keep working.
