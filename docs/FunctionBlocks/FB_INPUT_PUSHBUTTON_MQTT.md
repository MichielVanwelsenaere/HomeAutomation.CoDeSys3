## FB_INPUT_PUSHBUTTON_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Reads out a digital input and sets a single, double or long output high for one cycle when one of those events has been detected on the configured input.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌──────────────────────────┐
       │ FB_INPUT_PUSHBUTTON_MQTT │
       ├──────────────────────────┤
BOOL ──┤ PB                SINGLE ├── BOOL
       │                   DOUBLE ├── BOOL
       │                     LONG ├── BOOL
       │                   P_LONG ├── BOOL
       └──────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PB` | BOOL | Digital input linked to the signal wire of a pushbutton. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `SINGLE` | BOOL | Output high for one clock cycle when a single push is detected on input `PB`. |
| `DOUBLE` | BOOL | Output high for one clock cycle when a double push is detected on input `PB`. |
| `LONG` | BOOL | Output high for one clock cycle when a long push is detected on input `PB`. |
| `P_LONG` | BOOL | Output becomes high when a long push is detected on input `PB`, remains high as long as `PB` remains high. |

### **Methods**

**`ConfigureFunctionBlock`** — Configures the time parameter specifying the decoding time for a long key press. Defaults to 400ms.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `T_Long` | TIME |  | How long the pushbutton must be held before a long press is detected. Defaults to 400ms. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `{"event_type": "SINGLE"}` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `{"event_type": "DOUBLE"}` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `{"event_type": "LONG"}` | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix variable and the function block name.

(*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output. 

### **Code example**

- variables initiation:
```
MQTTPushbuttonPrefix    :STRING(100) := 'Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/';
FB_DI_PB_001            :FB_INPUT_PUSHBUTTON_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DI_PB_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPushbuttonPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue)          (* pointer to MQTTPublishQueue to send a new MQTT event *)
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001` (MQTTPushbuttonPrefix variable + function block name).

- reading digital input for events (cyclic):
```
FB_DI_PB_001(PB:= DI_001);
```

- integration with `FB_OUTPUT_SWITCH_MQTT`:
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIOHIGH:=      FALSE,                  (* brings the output high regardless of other input values *)
    PRIOLOW:=       FALSE,                  (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_PB_001.SINGLE     (* for toggling the output *)	
);
```

- MQTT discovery:
```
FB_DI_PB_001.InitMqttDiscovery(
	Name := 'pushbutton 001',			    (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);
```
