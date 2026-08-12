## FB_INPUT_PUSHBUTTON_DIMMER_MQTT
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
Big brother of input function block [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md) with additional functionality to output a realtime dimmer value (range 0-255).

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

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `OutputDimmer` | BOOL |  | Set TRUE to publish the dimmer value as MQTT events. |
| `Qos_Dimm` | MQTT.QoS |  | MQTT QoS used for the dimmer value events. |
| `Delta_Dimm` | INT |  | Resolution of the dimmer events: only publish once the value has moved by at least this much. The final value is always published, so MQTT and the output never drift apart. |
<!-- fb-interface:end -->

### **Function Block Behavior**
This MQTT function block is a wrapper of the `DIMM_I` function block in the OSCAT building library enhanced with additional functionality in order to be able to emit MQTT events for single, double, long and dimmer events. To fully understand its logic it's advised to give the documentation present in [the OSCAT building library docs](../_img/oscat_building100_en.pdf) a good read (page 52).

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `SINGLE` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `DOUBLE` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `LONG` | 2 | `FALSE` | no
| **Output changes: P_LONG**   | A change is detected on output `P_LONG`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: Q**   | A change is detected on output `Q`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DBL**   | A change is detected on output `DBL`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DIM**   | A change is detected on output `DIM`. (*) | `0-255` | configured in method call `InitMQTT` | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix variable and the function block name.

(*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output. 

### **Code example**

- variables initiation:
```
MQTTPushbuttonPrefix    :STRING(100) := 'Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/';
FB_DI_PB_001            :FB_INPUT_PUSHBUTTON_DIMMER_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DI_PB_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPushbuttonPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),         (* pointer to MQTTPublishQueue to send a new MQTT event *)
    TRUE,                                                               (* specify whether dimmer value should be outputted on MQTT topic *)
    SD_MQTT.QoS.ExactlyOnce,                                            (* specify the QoS for the dimmer mqtt events (values 0-255) *)    
    5                                                                   (* specify the resolution for the dimmer mqtt events *)    
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001` (MQTTPushbuttonPrefix variable + function block name). Note that for the outputs `Q`, `DBL` and `DIM` the MQTT publish topic has an additional concatenation being the name of the output. For example: `Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/DIM`.

- reading digital input for events (cyclic):
```
FB_DI_PB_001(PB:= DI_001);
```

- integration with `?`: The output dimmer values can be connected to any light supporting integration through Home Assistant, OpenHAB, etc. For dimming using a PLC analog output check out the [FB_OUTPUT_DIMMER_MQTT docs](./FB_OUTPUT_DIMMER_MQTT.md)

### **Home Assistant YAML**
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config:

```YAML
mqtt:
  sensor:
  # To receive single/double/long events  
  - name: "FB_DI_PB_001"
    state_topic: "Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001"
    qos: 2
    expire_after: 3
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
  # To receive state of output Q
  - name: "FB_DI_PB_001_Q"
    state_topic: "Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/Q"
    qos: 2
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
  # To receive state of output DBL
  - name: "FB_DI_PB_001_DBL"
    state_topic: "Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/DBL"
    qos: 2
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
  # To receive state of output DIM
  - name: "FB_DI_PB_001_DIM"
    state_topic: "Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/DIM"
    qos: 2
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
  # To receive state of output P_LONG
  - name: "FB_DI_PB_001_P_LONG"
    state_topic: "Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/P_LONG"
    qos: 2
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
```
