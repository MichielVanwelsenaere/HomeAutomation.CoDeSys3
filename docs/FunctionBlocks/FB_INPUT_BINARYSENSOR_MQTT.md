## FB_INPUT_BINARYSENSOR_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Binary sensors gather information about the state of devices which have a "digital" return value (either 1 or 0). These can be switches, contacts, pins, etc. These sensors only have two states: *0/off/low/closed/false* and *1/on/high/open/true*.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌────────────────────────────┐
       │ FB_INPUT_BINARYSENSOR_MQTT │
       ├────────────────────────────┤
BOOL ──┤ BS                       Q ├── BOOL
       │                      EVENT ├── BOOL
       │                    EVENT_R ├── BOOL
       │                    EVENT_F ├── BOOL
       └────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `BS` | BOOL | Digital input linked to the signal wire of the binary sensor. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Q` | BOOL | Follows the input `BS` but debounced. |
| `EVENT` | BOOL | Output high for one clock cycle when any event occurs on debounced input `BS`. |
| `EVENT_R` | BOOL | Output high for one clock cycle when a rising edge is detected on debounced input `BS`. |
| `EVENT_F` | BOOL | Output high for one clock cycle when a falling edge is detected on debounced input `BS`. |

### **Methods**

**`ConfigureFunctionBlock`** — Configures the behavior of output `Q` using the parameters below:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `T_TurnOffDelay` | TIME |  | Duration of the turn off delay added on output `Q` to prevent rapid ON/OFF behavior on the output caused by a fast switching sensor on the digital input. Defaults to 0 seconds, can be extremely useful when connecting a motion sensor to the PLC. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `DeviceClass` | STRING(100) | `'smoke'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **input changes: BS**   | A change is detected on input `BS`. (*) | `ON/OFF` | 2 | `TRUE` | yes

MQTT publish topic is a concatenation of the publish prefix variable and the function block name. 

### **Code example**

- variables initiation:
```
MQTTBinarySensorPrefix  :STRING(100) := 'Devices/PLC/Lab/Out/DigitalInputs/BinarySensors/';
FB_DI_BS_001            :FB_INPUT_BINARYSENSOR_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_INPUT_BINARYSENSOR_MQTT.InitMQTT(MQTTPublishPrefix:= ADR(MQTTBinarySensorPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue)                          (* pointer to MQTTPublishQueue to send a new MQTT event *)
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/DigitalInputs/BinarySensors/FB_DI_BS_001` (MQTTBinarySensorPrefix variable + function block name).

- Configuration of the function block with a 5 second turn off delay on the output (called once during startup):
```
FB_INPUT_BINARYSENSOR_MQTT.ConfigureFunctionBlock(T_TurnOffDelay:= T#5S);         (* time to delay the negative edge on output Q *)
```

- reading digital input for events (cyclic):
```
FB_DI_BS_001(BS:= DI_001);
```

- integration with `FB_OUTPUT_BINARY_MQTT`:
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIO_HIGH:=     FALSE,                  (* brings the output high regardless of other input values *)
    PRIO_LOW:=      FALSE,                  (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_BS_001.EVENT      (* for toggling the output *)	
);
```

- MQTT discovery:
```
FB_DI_BS_001.InitMqttDiscovery(
	Name := 'Binary sensor 001',			(* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);
```
