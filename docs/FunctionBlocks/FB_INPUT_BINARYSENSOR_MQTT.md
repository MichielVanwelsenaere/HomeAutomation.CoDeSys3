## FB_INPUT_BINARYSENSOR_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Binary sensors gather information about the state of devices which have a "digital" return value (either 1 or 0). These can be switches, contacts, pins, etc. These sensors only have two states: *0/off/low/closed/false* and *1/on/high/open/true*.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌─────────────────────────────┐
       │  FB_INPUT_BINARYSENSOR_MQTT │
       ├─────────────────────────────┤
BOOL ──┤ BS                        Q ├── BOOL
BOOL ──┤ ProcessImageValid     EVENT ├── BOOL
       │                     EVENT_R ├── BOOL
       │                     EVENT_F ├── BOOL
       └─────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `BS` | BOOL |  | Digital input linked to the signal wire of the binary sensor. |
| `ProcessImageValid` | BOOL | `TRUE` | Gates the debounce: FALSE holds the sensor at rest. Wire it to `Pfc200Bus.xConfigFinished`. **Needed on any normally-closed loop** — until the bus is up every mapped word reads zero, and through the inversion such a loop needs, zero is the tripped state. |

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
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `DeviceClass` | STRING(100) | `'smoke'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Publishing starts once the block is wired, which `FriendlyName` does on its own.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **input changes: BS**   | A change is detected on input `BS`. (*) | `ON/OFF` | 2 | `TRUE` | yes

MQTT publish topic is a concatenation of the publish prefix variable and the function block name. 

### **Code example**

Declaration — `FriendlyName` is all the wiring this block needs:

```iecst
VAR
	FB_DI_BS_001 : FB_INPUT_BINARYSENSOR_MQTT := (FriendlyName := 'Smoke detector landing');
END_VAR
```

Cyclic call, once per scan:

```iecst
FB_DI_BS_001(BS := NOT(DI_001), ProcessImageValid := Pfc200Bus.xConfigFinished);
```

`NOT` because a smoke detector's loop is normally closed, and `ProcessImageValid`
because that inversion makes an unstarted K-bus look like an alarm.

Driving an output from its edge:

```iecst
FB_DO_SW_001(TOGGLE := FB_DI_BS_001.EVENT, OUT => DO_001);
```

The publish topic is `GVL_MQTT.MqttPushbuttonPrefix` plus the instance name, so this
instance publishes to `.../Out/DigitalInputs/Pushbuttons/FB_DI_BS_001` and announces
itself to Home Assistant as `Smoke detector landing`.
