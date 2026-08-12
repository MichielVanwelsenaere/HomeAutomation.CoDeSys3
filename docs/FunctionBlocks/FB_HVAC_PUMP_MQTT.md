## FB_HVAC_PUMP_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control a pump with a simple on/off signal and request heat from the burner function block when it is required. Respects any minimum runtime requirements.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌────────────────────────┐
       │   FB_HVAC_PUMP_MQTT    │
       ├────────────────────────┤
BOOL ──┤ IN                PUMP ├── BOOL
       │           HEAT_REQUEST ├── BOOL
       │      MIN_ONTIME_ACTIVE ├── BOOL
       └────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `IN` | BOOL | Should be made high if pump flow is required. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PUMP` | BOOL | Output for switching the pump on and off. Respects a minimum on and off runtime value to prevent damaging the pump. |
| `HEAT_REQUEST` | BOOL | Output for requesting heat from the burner. Follows the input `IN` more closely than output `PUMP` since the minimum runtime for the burner is controlled in the burner function block. |
| `MIN_ONTIME_ACTIVE` | BOOL | Output indicating when the pump is in its minimum runtime cycle. |

### **Methods**

**`FB_init`** — Constructor, overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MIN_ONTIME` | TIME |  | Time that the pump should be on at a minimum before turning it off again. |
| `MIN_OFFTIME` | TIME |  | Time that the pump should be off at a minimum before turning it on again. |

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
| `DeviceClass` | STRING(100) | `'heat'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: PUMP** | A change is detected on output `PUMP`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
