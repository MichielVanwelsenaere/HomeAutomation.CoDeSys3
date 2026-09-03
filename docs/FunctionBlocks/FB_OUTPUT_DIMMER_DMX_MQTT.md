## FB_OUTPUT_DIMMER_DMX_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Can be controlled using pulses from [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md), maintains output state through power cycles. Takes a 0-255 byte value as input -as FB input or MQTT value-. Byte input value is linearly scaled to a word datatype value with a range from 0-32767. Output linear scaled range can be configured to be different from 0-32767 if desired.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────┐
       │ FB_OUTPUT_DIMMER_DMX_MQTT │
       ├───────────────────────────┤
BOOL ──┤ SINGLE                  Q ├── BOOL
BOOL ──┤ LONG                Q_OUT ├── WORD
BOOL ──┤ P_LONG                OUT ├── WORD
BOOL ──┤ PRIO_HIGH                 │
BOOL ──┤ PRIO_LOW                  │
BOOL ──┤ SET                       │
BYTE ──┤ VAL                       │
BOOL ──┤ RST                       │
       └───────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `SINGLE` | BOOL |  | Input to connect to one or multiple `SINGLE` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `LONG` | BOOL |  | Input to connect to one or multiple `LONG` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `P_LONG` | BOOL |  | Input to connect to one or multiple `P_LONG` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `PRIO_HIGH` | BOOL | `FALSE` | When high the output `Q` is set to high with a maximum brightness, has priority over the other inputs. |
| `PRIO_LOW` | BOOL | `FALSE` | When high the output `Q` is set to low, has priority over the other inputs. |
| `SET` | BOOL |  | Input for switching output DIM to the input VAL value. |
| `VAL` | BYTE |  | Byte value for SET operation. |
| `RST` | BOOL |  | Input to switch off the output. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Q` | BOOL | Output, bool datatype. |
| `Q_OUT` | WORD | Follows 'OUT' when Q is high. Equal to 0 when Q is low. |
| `OUT` | WORD | Dimmer value, word datatype. |

### **Methods**

**`ConfigureFunctionBlock`** — Configures the dimmer with your preferred settings, an overview of the parameters and their default values.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `T_Debounce` | TIME | `TIME#10ms` | Debounce time for input PB, defaults to 10ms. |
| `T_Reconfig` | TIME | `TIME#10s0ms` | Reconfiguration time, defaults to 10S. |
| `T_On_Max` | TIME | `TIME#0ms` | Start limitation, defaults to 0ms. |
| `T_Dimm_Start` | TIME | `TIME#400ms` | Reaction time to dim, defaults to 400ms. |
| `T_Dimm` | TIME | `TIME#3s0ms` | Time for a dimming ramp, defaults to 3s. |
| `Min_On` | BYTE | `50` | Minimum value of output OUT at startup, defaults to 50. |
| `Max_On` | BYTE | `255` | Maximum value of output OUT at startup, defaults to 255. |
| `Soft_Dimm` | BOOL | `TRUE` | If TRUE dimming begins after ON and at 0, defaults to TRUE. |
| `Rst_Out` | BOOL | `FALSE` | If input Rst is TRUE, output OUT is set to 0, defaults to FALSE. |
| `OUT_LinearScaleMin` | INT | `0` | Lower bound value used for linearly scaling output OUT from datatype byte to word. Defaults to 0. |
| `OUT_LinearScaleMax` | INT | `32767` | Upper bound value used for linearly scaling output OUT from datatype byte to word. Defaults to 32767. |

**`initDMX`** — Configures the dimmer with DMX configuration. For more info about Art-Net and DMX, [read this](./../AdditionalFunctionality/DMX_artnet.md).

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DmxChannel` | INT |  | Which channel, 1-512. `initDMX` refuses anything outside that and leaves the block dormant: the buffer is indexed as `DmxChannel - 1`, so 0 would write in front of it. |
| `DmxWidth` | INT | `1` | Width of the fixture, in channels (often 1 or 2). Metadata for MQTT discovery only; the block writes the single byte at `DmxChannel` whatever this says, so an RGB fixture still gets one channel. |
| `DmxUniverse` | INT | `1` | Universe number. Metadata for MQTT discovery only; it does not affect the DMX output. |
| `pDmxValues` | POINTER TO oscat_network.NETWORK_BUFFER_SHORT |  | Pointer to a global buffer. There is currently only one buffer, and thus one universe. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |
| `OutputDimmer` | BOOL |  | Set TRUE to publish the dimmer value as MQTT events. |
| `Qos_Dimm` | MQTT.QoS |  | MQTT QoS used for the dimmer value events. |
| `Delta_Dimm` | INT |  | Resolution of the dimmer events: only publish once the value has moved by at least this much. The final value is always published, so MQTT and the output never drift apart. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |

**`PublishReceived`** — Callback method called by the callback collector when a message is received on the subscribed topic by the callback collector.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **Function Block Behavior**

The following table shows the operating status of the dimmer:

| SINGLE/LONG/P_LONG | SET | RST | Q     | DIR (\*)  | OUT                                                                                                                    | Q_OUT    |
| :----------------- | :-- | :-- | :---- | :-------- | :--------------------------------------------------------------------------------------------------------------------- | :------- |
| SINGLE             | 0   | 0   | NOT Q | OUT < 127 | LIMIT(MIN_ON,OUT,MAX_ON)                                                                                               | Q \* OUT |
| LONG/P_LONG        | 0   | 0   | ON    | NOT DIR   | Ramp up or down depending on DIR, start at 0 when soft_dimm = TRUE and Q = 0, reverse direction if 0 or 255 is reached | OUT      |
| 0                  | 1   | 0   | ON    | OUT < 127 | VAL                                                                                                                    | OUT      |
| 0                  | 0   | 1   | OFF   | UP        | 0 when RST_OUT = TRUE                                                                                                  | 0        |

(\*): DIR refers to the direction of the dimmer output `OUT`, indicating whether the dimmer output value changes upwards or downwards.

This MQTT function block is a wrapper of the `DIMM_I` function block in the OSCAT building library enhanced with additional functionality in order to be able to emit MQTT events. To fully understand its logic it's advised to give the documentation present in [the OSCAT building library docs](../_img/oscat_building100_en.pdf) a good read (page 52).

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                   | Description                                | MQTT payload | QoS                                  | Retain flag | Published on startup |
| :---------------------- | :----------------------------------------- | :----------- | :----------------------------------- | :---------- | :------------------- |
| **Output changes: Q**   | A change is detected on output `Q`. (\*)   | `TRUE/FALSE` | 2                                    | `TRUE`      | no                   |
| **Output changes: OUT** | A change is detected on output `OUT`. (\*) | `0-255`      | configured in method call `InitMQTT` | `TRUE`      | no                   |

(\*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output.

### **MQTT subscribe behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command                     | Description                                          | expected payload | Additional notes                                                 |
| :-------------------------- | :--------------------------------------------------- | :--------------- | :--------------------------------------------------------------- |
| **Change output Q to high** | Request to change output to high.                    | `TRUE`           | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low. |
| **Change output Q to low**  | Request to change output to low.                     | `FALSE`          | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low. |
| **Set OUT byte value**      | Request to set the byte value on input/output `OUT`. | `0-255`          | Command executed when `PRIO_HIGH` input is low.                  |

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name.
Note that the function block also accepts float values for setting the dimmer output value, the float value will get rounded to the nearest integer value.

### **Code example**

- variables initiation:
```
MqttPubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/Out/Dimmers/';
MqttSubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/In/Dimmers/';
FB_AO_DIMMER_001			:FB_OUTPUT_DIMMER_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_AO_DIMMER_001.InitMQTT(MQTTPublishPrefix:= ADR(GVL_MQTT.MqttPubDimmerPrefix),     (* pointer to string prefix for the MQTT publish topic *)
    MQTTSubscribePrefix:= ADR(GVL_MQTT.MqttSubDimmerPrefix),                         (* pointer to string prefix for the MQTT subscribe topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),             (* pointer to MQTTPublishQueue to send a new MQTT event *)
    pMqttCallbackCollector := ADR(GVL_MQTT.collector_FB_DIMMER_MQTT),  (* pointer to CallbackCollector to receive Mqtt subscription events *)
    TRUE,                                                                   (* specify whether dimmer value should be outputted on MQTT topic *)
    MQTT.QoS.ExactlyOnce,                                                (* specify the QoS for the dimmer mqtt events (values 0-255) *)
    5                                                                       (* specify the resolution for the dimmer mqtt events *)
);
```

The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/Dimmers/FB_AO_DIMMER_001` (MQTTPubSwitchPrefix variable + function block name). The subscription topic will be `Devices/PLC/Lab/In/Dimmers/FB_AO_DIMMER_001` (MQTTSubSwitchPrefix variable + function block name).

- ConfigureFunctionBlock (called once during startup):
```
FB_AO_DIMMER_001.ConfigureFunctionBlock(
	T_Debounce:=T#10MS,
	T_Reconfig:=T#10S,
	T_On_Max:=T#0S,
	T_Dimm_Start:=T#400MS,
	T_Dimm:=T#3S,
	Min_On:=50,
	Max_On:=255,
	Soft_Dimm:=TRUE,
	Rst_Out:=FALSE,
	OUT_LinearScaleMin:=11000,
	OUT_LinearScaleMax:=32767
);
```

The dimmer behavior in the example above is adjusted to start dimming from '11000' instead of the default '0' value. This can be important as different dimming devices will have different lower bound 'on' voltages. In addition, depending on your PLC device, the maximum out value will differ. Note that this method only requires a call when it's desired to change the default behavior characteristics.

- checking for events to switch the digital output (cyclic), example 1:
```
FB_AO_DIMMER_001(SINGLE:=   FB_DI_PB_041.SINGLE,    (* for toggling the output Q *)
    LONG:=                  FB_DI_PB_041.LONG,      (* for controlling the dimmer output OUT *)
    P_LONG:=                FB_DI_PB_041.P_LONG,    (* for controlling the dimmer output OUT *)
    Q=>                     DO_001,                 (* couple the function block to the physical digital output *)
    OUT=>                   AO_001,                 (* couple the function block to the physical analog output *)
    VAL:=                   255,                    (* value to set on output OUT when input SET is high *)
    SET:=                   FB_DI_PB_041.DOUBLE     (* when high, VAL is set on output OUT *)
);
```

The above illustrates an integration with [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). The dimmer module in this example has a 'on/off' digital input that is wired to the 'Q' output of the dimmer & a 0/1-10V analog input that is wired to the 'OUT' output of the dimmer.

- checking for events to switch the digital output (cyclic), example 2:
```
FB_AO_DIMMER_001(SINGLE:=   FB_DI_PB_041.SINGLE,    (* for toggling the output Q *)
    LONG:=                  FB_DI_PB_041.LONG,      (* for controlling the dimmer output OUT *)
    P_LONG:=                FB_DI_PB_041.P_LONG,    (* for controlling the dimmer output OUT *)
    Q_OUT=>                 AO_001,                 (* couple the function block to the physical analog output *)
    VAL:=                   255,                    (* value to set on output OUT when input SET is high *)
    SET:=                   FB_DI_PB_041.DOUBLE     (* when high, VAL is set on output OUT *)
);
```

The above illustrates an integration with [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). The dimmer module in this example has a 0/1-10V analog input that is wired to the 'Q_OUT' output of the dimmer.

- Init DMX method call (called once during startup):
```
FB_AO_DMX_DIMMER_001.InitDmx(
    DmxChannel := 1,
    DmxWidth:=1,
    pDmxValues := ADR(GVL_DMX.DMX.BUFFER)
    dmxUniverse := 1,
);
```

The above illustrates how to initiate DMX capabilities. If `InitDmx` is called before `InitMqttDiscovery`, the config JSON in MQTT also contains the DMX channel, width and universe.

- MQTT discovery:
```
FB_AO_DIMMER_001.InitMqttDiscovery(
	name := '001. Office strip cold',				(* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_Device),							(* The device shown in Home Assistant *)
);
```
