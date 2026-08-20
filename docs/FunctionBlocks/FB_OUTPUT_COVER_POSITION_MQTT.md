## FB_OUTPUT_COVER_POSITION_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

A roller shutter or blind that Home Assistant can send **to a position**, not just open, closed
and stop. The entity gets a slider, and the cover reports back how far open it is as it travels.

This is the sibling of [`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md), and the two are
interchangeable for everything that block already did. Use the older one when a cover genuinely
has nothing but two relays and no idea where it is; use this one when the travel time is known,
which is nearly always.

**Where the position comes from.** There is no encoder on a shutter motor, so the position is
*integrated from run time* against `T_TravelUp` and `T_TravelDown` by
`OSCAT_BUILDING.BLIND_CONTROL_S` — a library this project already references. That block keeps a
simulated 0..255 position, extends the motor briefly at each end stop so every full journey
recalibrates, and enforces a lockout between direction changes. This block is the translation
layer around it: percent to and from 0..255, Home Assistant's payloads and topics, and the state
machine that decides what a stop means.

:bulb: **Measure both travel times.** A shutter usually falls faster than it climbs. Times that
are 10% out show up as a position that drifts from reality mid-travel and snaps back at the end
stops.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────┐
       │ FB_OUTPUT_COVER_POSITION_MQTT │
       ├───────────────────────────────┤
BOOL ──┤ UP                         MU ├── BOOL
BOOL ──┤ DN                         MD ├── BOOL
BOOL ──┤ PRIO_LOCK            Position ├── BYTE
TIME ──┤ T_TravelUp             Moving ├── BOOL
TIME ──┤ T_TravelDown    PositionKnown ├── BOOL
BYTE ──┤ PublishStep                   │
       └───────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `UP` | BOOL | Manual up, e.g. straight from a pushbutton's long-press output. **Held TRUE drives, releasing stops and holds** — a person watching the cover beats whatever position was asked for, and the abandoned setpoint is not resumed. |
| `DN` | BOOL | Manual down, same contract as `UP`. Both held together is not a command: that is what the engine underneath calls automatic mode, and this block enters it by itself when a position is requested. |
| `PRIO_LOCK` | BOOL | Nothing may drive the motor while this is TRUE — a wind alarm, a service switch, an open window contact. Commands are still accepted and still remembered; they simply do not move anything until it clears. |
| `T_TravelUp` | TIME | Time to travel from fully closed to fully open. Defaults to 20 s. This is how the position is known at all, so measure it. |
| `T_TravelDown` | TIME | Time to travel from fully open to fully closed. Defaults to 20 s, and is usually the shorter of the two. |
| `PublishStep` | BYTE | Percent of travel between position publishes **while moving**. Defaults to 5, which gives a slider that visibly tracks the shutter without putting twenty messages per journey on the broker. The exact position is always published once movement ends, whatever this is set to. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `MU` | BOOL | Motor up contactor. Never TRUE at the same time as `MD` — the engine holds a one-second lockout across a direction change. |
| `MD` | BOOL | Motor down contactor. |
| `Position` | BYTE | How far open, **0 closed to 100 open**, the way Home Assistant counts a cover. Converted from the engine's 0..255 with rounding, so a cover sent to 50 reads back as 50. |
| `Moving` | BOOL | A motor is running. |
| `PositionKnown` | BOOL | An end stop has been reached at least once since power-up, so the position has been measured rather than assumed. FALSE means it is still the engine's opening guess. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `DeviceClass` | STRING(50) | `'shutter'` | Home Assistant device class for the entity. Leave empty for the default. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **Code example**

```
FB_DO_COVER_002 : FB_OUTPUT_COVER_POSITION_MQTT := (FriendlyName := 'Living room shutter');
```

```
FB_DO_COVER_002(
	T_TravelUp := T#20S,
	T_TravelDown := T#18S,
	MU => DO_005,
	MD => DO_006
);
```

That is the whole of it: the block wires itself from `MqttVariables` on its first cyclic call and
announces a cover **with a position slider** to Home Assistant. Add a pushbutton by handing its
long-press outputs to `UP` and `DN`.

:rotating_light: **The travel times are inputs, not `FB_init` arguments** — deliberately unlike
[`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md), which takes `(T_LOCKOUT, T_UD)` at the
declaration. A travel time is the one number on a cover that somebody always ends up tuning after
watching the thing move, and CODESYS stores an instance's `FB_init` arguments where no script can
revise them — see [CLAUDE.md](../../CLAUDE.md). An input can be corrected from `MAIN_INIT`, from
an online session, or by editing one line here.

### **MQTT behaviour**

| direction | topic | payloads |
|:--|:--|:--|
| publish | `.../Out/Covers/<instance>` | `OPEN` / `OPENING` / `CLOSING` / `CLOSED` / `STOPPED`, on change and once at startup |
| publish | `.../Out/Covers/<instance>/POSITION` | `0`..`100`, every `PublishStep` while moving and exactly once movement ends |
| subscribe | `.../In/Covers/<instance>` | `OPEN`, `CLOSE`, `STOP` |
| subscribe | `.../In/Covers/<instance>/POSITION` | `0`..`100` |

:bulb: **The cover subscription is a `#` wildcard because of this block.** The position command
topic sits one level below the cover's own topic, and `MqttSubCoverTopic` used to end in `+`,
which would not have delivered it. The older cover block's topics still match, so nothing changed
for it.

### **What a stop means**

Three ways to interrupt a journey, and they are deliberately not the same:

| | effect |
|:--|:--|
| `STOP` over MQTT | motors off, and **the setpoint is dragged to the present position** so automatic mode has nothing left to resume. A stop that silently resumes later is not a stop. |
| releasing `UP` / `DN` | the same hold, reached the same way |
| `PRIO_LOCK` | motors off, but the setpoint is **kept**: whatever was asked for happens when the lock clears |

### **Home Assistant**

The block publishes its own discovery config, so no YAML is needed:

| Field | Value |
|:--|:--|
| `position_topic` / `set_position_topic` | the two `/POSITION` topics above |
| `position_open` / `position_closed` | 100 / 0 |
| `device_class` | from `DeviceClass`, `shutter` by default |

**Supplying `set_position_topic` is what puts a slider on the entity** rather than three buttons,
which is the whole difference from the older cover block on the Home Assistant side.
`CreateCoverEntity` therefore takes all four position fields as optional parameters and publishes
`null` for each when they are empty — so
[`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md)'s config gains four nulls and behaves exactly as
it did.

### **Provenance**

The idea, and the mapping from Home Assistant's cover to OSCAT's blind chain, came from a library
built on top of this project by a friend of the author: their `FB_COVER_MQTT_SD` drives
`BLIND_INPUT_EXT_PT` and `BLIND_CONTROL_S_PT` from a fork of `CommonTypesAndFunctions`, and
publishes position to a second topic in much the same shape.

This block is a re-implementation rather than a port, for two reasons: it needs no forked library,
and it drives `BLIND_CONTROL_S` directly rather than through the input stage, since pushbutton
handling in this project belongs to
[`FB_INPUT_PUSHBUTTON_MQTT`](FB_INPUT_PUSHBUTTON_MQTT.md) and doing it twice would put two state
machines in charge of one shutter.
