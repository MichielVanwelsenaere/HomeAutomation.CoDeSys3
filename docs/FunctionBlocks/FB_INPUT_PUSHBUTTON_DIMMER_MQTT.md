## FB_INPUT_PUSHBUTTON_DIMMER_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Big brother of input function block [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md) with additional functionality to output a realtime dimmer value (range 0-255).

It announces **two** Home Assistant entities: an **event** entity for the button, carrying
`SINGLE`, `DOUBLE` and `LONG`, and a **sensor** for the dim level. Set `FriendlyName` at the
declaration and the block wires itself — no `InitMqtt` call needed.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌─────────────────────────────────┐
       │ FB_INPUT_PUSHBUTTON_DIMMER_MQTT │
       ├─────────────────────────────────┤
BOOL ──┤ PB                          DIM ├── BYTE
BOOL ──┤ SET                         DBL ├── BOOL
BYTE ──┤ VAL                           Q ├── BOOL
BOOL ──┤ RST                      SINGLE ├── BOOL
       │                          DOUBLE ├── BOOL
       │                            LONG ├── BOOL
       │                          P_LONG ├── BOOL
       └─────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PB` | BOOL | Digital input linked to the signal wire of a pushbutton. |
| `SET` | BOOL | Input for switching output DIM to the input VAL value. |
| `VAL` | BYTE | Byte value for SET operation. |
| `RST` | BOOL | Input to switch off the output. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `DIM` | BYTE | Dimmer value, byte datatype. |
| `DBL` | BOOL | Double-click output. |
| `Q` | BOOL | Output. |
| `SINGLE` | BOOL | Output high for one clock cycle when a single push is detected on input `PB`. |
| `DOUBLE` | BOOL | Output high for one clock cycle when a double push is detected on input `PB`. |
| `LONG` | BOOL | Output high for one clock cycle when a long push is detected on input `PB`. |
| `P_LONG` | BOOL | Output becomes high when a long push is detected on input `PB`, remains high as long as `PB` remains high. |

### **Methods**

**`ConfigureFunctionBlock`** — Configures the dimmer with your preferred settings, an overview of the parameters and their default values:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `T_Debounce` | TIME |  | Debounce time for input PB, defaults to 10ms. |
| `T_Reconfig` | TIME |  | Reconfiguration time, defaults to 10S. |
| `T_On_Max` | TIME |  | Start limitation, defaults to 0ms. |
| `T_Dimm_Start` | TIME |  | Reaction time to dim, defaults to 400ms. |
| `T_Dimm` | TIME |  | Time for a dimming ramp, defaults to 3s. |
| `Min_On` | BYTE |  | Minimum value of output DIM at startup, defaults to 50. |
| `Max_On` | BYTE |  | Maximum value of output DIM at startup, defaults to 255. |
| `Soft_Dimm` | BOOL |  | If TRUE dimming begins after ON and at 0. |
| `Dbl_Toggle` | BOOL |  | If TRUE the output DBL is inverted at each double-click, defaults to FALSE. |
| `Rst_Out` | BOOL |  | If input Rst is TRUE, output DIM is set to 0, defaults to FALSE. |
| `T_Long` | TIME |  | Configures the time parameter specifying the decoding time for a long key press. Defaults to 400ms. When this timespan is reached while pushing the pushbutton a long push is detected on input `PB`. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup. Not needed when `FriendlyName` is set at the declaration: the block then wires itself.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `OutputDimmer` | BOOL |  | Set TRUE to publish the dimmer value as MQTT events. |
| `Qos_Dimm` | MQTT.QoS |  | MQTT QoS used for the dimmer value events. |
| `Delta_Dimm` | INT |  | Resolution of the dimmer events: only publish once the value has moved by at least this much. The final value is always published, so MQTT and the output never drift apart. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. The self-wiring prologue passes `FriendlyName`; the dim level entity is named after it too. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **Function Block Behavior**
This MQTT function block is a wrapper of the `DIMM_I` function block in the OSCAT building library enhanced with additional functionality in order to be able to emit MQTT events for single, double, long and dimmer events. To fully understand its logic it's advised to give the documentation present in [the OSCAT building library docs](../_img/oscat_building100_en.pdf) a good read (page 52).

### **MQTT publish behavior**
Requires `FriendlyName` on the declaration, or an explicit `InitMQTT` call, to enable MQTT
capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `{"event_type": "SINGLE"}` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `{"event_type": "DOUBLE"}` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `{"event_type": "LONG"}` | 2 | `FALSE` | no
| **Output changes: P_LONG**   | A change is detected on output `P_LONG`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: Q**   | A change is detected on output `Q`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DBL**   | A change is detected on output `DBL`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DIM**   | The level has moved by at least `Delta_Dimm`, or the button was released. (*) | `0-255` | `Qos_Dimm`, from `InitMQTT` | `TRUE` | **yes**

MQTT publish topic is a concatenation of the publish prefix variable and the function block name.

(*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output. 

:bulb: **The three press payloads are JSON.** Home Assistant's event platform reads
`event_type` out of the payload, so a bare word would arrive and be discarded. Anything reading
these topics directly, hand-written YAML included, has to read the JSON too.

**`DIM` is published retained, and once at startup.** It is state, not an event: after a Home
Assistant restart the sensor takes its value back from the broker instead of reading *unknown*
until somebody dims something, and a level that has never moved is published anyway so a freshly
discovered entity is not born empty. `Delta_Dimm` decides the rest, with the value on release
always sent so MQTT and the output cannot drift apart.

### **Home Assistant entities**

| Entity | Platform | State topic | Behaviour |
|:--|:--|:--|:--|
| *FriendlyName* | `event`, `dev_cla: button` | `…/<block>` | Fires on each press. Event types `SINGLE`, `DOUBLE`, `LONG`. Stateless, so no expiry. |
| *FriendlyName* level | `sensor` | `…/<block>/DIM` | The dim level, 0-255. No unit, no device class, no state class — it is a control position, not a measurement, and a mean of it means nothing. `expire_after` is 0. |

Both entities belong to the PLC's discovery device and inherit its availability, so they grey out
together when the PLC stops saying *online*. Neither carries an availability topic of its own:
nothing in this block can be individually untrustworthy the way an RTD channel can.

`Q`, `DBL` and `P_LONG` keep publishing, but are **not** announced. `P_LONG` is the hold duration
of a `LONG` the event entity already carries, and `DBL` is internal toggle state — entities for
either would be clutter that has to be explained. Subscribe to the topics directly if you want
them.

:bulb: **The level is a sensor, not a light — deliberately.** A light entity has to be
commandable, and this block has no subscribe side at all: no callback collector, no command
topics. [`FB_OUTPUT_DIMMER_MQTT`](./FB_OUTPUT_DIMMER_MQTT.md) is the block that has those, and it
is what to reach for when Home Assistant has to *set* the level rather than watch it — driven from
this block's `SINGLE` and `P_LONG`, or from
[`FB_INPUT_PUSHBUTTON_MQTT`](./FB_INPUT_PUSHBUTTON_MQTT.md).

### **Code example**

- variables initiation:
```
fbDiPb002 : FB_INPUT_PUSHBUTTON_DIMMER_MQTT := (FriendlyName := 'Button number 002');
```

The block wires itself from `GVL_MQTT` on its first cyclic call and announces both entities. Its
publish topic is `GVL_MQTT.MqttPushbuttonPrefix` + the instance name, so with the lab's prefix
that is `Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/fbDiPb002`, and the level lands on
`…/fbDiPb002/DIM`. See [MQTT self-wiring](../AdditionalFunctionality/MQTT_SelfWiring.md).

- reading digital input for events (cyclic):
```
fbDiPb002(PB := DI_002);
```

- altering the dimming behaviour (called once during startup):
```
fbDiPb002.ConfigureFunctionBlock(
	T_Debounce := T#10MS,
	T_Reconfig := T#10S,
	T_On_Max := T#0S,
	T_Dimm_Start := T#400MS,
	T_Dimm := T#3S,
	Min_On := 50,
	Max_On := 255,
	Soft_Dimm := TRUE,
	Dbl_Toggle := FALSE,
	Rst_Out := FALSE,
	T_Long := T#400MS);
```

- wiring it by hand instead, where `FriendlyName` is left empty:
```
fbDiPb002.InitMqtt(
	MQTTPublishPrefix := ADR(GVL_MQTT.MqttPushbuttonPrefix),
	pMqttPublishQueue := ADR(GVL_MQTT.fbMqttPublishQueue),
	OutputDimmer := TRUE,                   (* publish the dim level at all *)
	Qos_Dimm := MQTT.QoS.ExactlyOnce,       (* QoS for the dim level *)
	Delta_Dimm := 5);                       (* how far the level must move to be worth publishing *)

fbDiPb002.InitMqttDiscovery(
	Device := ADR(GVL_MQTT.PLC_Device),
	Name := 'Button number 002');
```
