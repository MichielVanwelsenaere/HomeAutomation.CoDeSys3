## FB_HVAC_BURNER_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control a heat source with a simple on/off signal. Respects any minimum runtime requirements.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌─────────────────────┐
       │ FB_HVAC_BURNER_MQTT │
       ├─────────────────────┤
BOOL ──┤ IN              OUT ├── BOOL
       └─────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `IN` | BOOL |  | When high heat production is required for the pump(s). |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `OUT` | BOOL | Follows input `IN` while respecting minimum and maximum allowed runtime configuration. |

### **Methods**

**`FB_init`** — Constructor, overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MIN_ONTIME` | TIME |  | Minimum on time for the burner in order to prevent damage. |
| `MIN_OFFTIME` | TIME |  | Minimum off time for the burner in order to prevent damage. |

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
| `DeviceClass` | STRING(100) | `'heat'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
<!-- fb-interface:end -->

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: OUT** | A change is detected on output `OUT`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
