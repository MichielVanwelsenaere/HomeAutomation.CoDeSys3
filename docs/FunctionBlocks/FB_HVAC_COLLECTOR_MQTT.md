## FB_HVAC_COLLECTOR_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control multiple valves that share the same pump. Valves can be controlled via the thermostat function blocks.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌────────────────────────┐
       │ FB_HVAC_COLLECTOR_MQTT │
       ├────────────────────────┤
BOOL ──┤ THERMOSTAT_1   VALVE_1 ├── BOOL
BOOL ──┤ THERMOSTAT_2   VALVE_2 ├── BOOL
BOOL ──┤ THERMOSTAT_3   VALVE_3 ├── BOOL
BOOL ──┤ THERMOSTAT_4   VALVE_4 ├── BOOL
BOOL ──┤ THERMOSTAT_5   VALVE_5 ├── BOOL
BOOL ──┤ THERMOSTAT_6   VALVE_6 ├── BOOL
BOOL ──┤ THERMOSTAT_7   VALVE_7 ├── BOOL
BOOL ──┤ THERMOSTAT_8   VALVE_8 ├── BOOL
       │                   PUMP ├── BOOL
       └────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `THERMOSTAT_1` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_2` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_3` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_4` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_5` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_6` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_7` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |
| `THERMOSTAT_8` | BOOL | Input for the signal coming from a thermostat function block. When high the valve should be opened and flow provided by the pump. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `VALVE_1` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_2` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_3` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_4` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_5` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_6` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_7` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `VALVE_8` | BOOL | Output for the valve that should be controlled by the matching thermostat. |
| `PUMP` | BOOL | Output that should be directed to an HVAC pump function block in order to turn a pump on or off. |

### **Methods**

**`FB_init`** — Constructor, overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `ValveCycleTime` | TIME |  | Time required to fully open or close a valve. Pump output will only be switched when at least one valve is fully open. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `NameValve1` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve2` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve3` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve4` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve5` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve6` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve7` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `NameValve8` | STRING(100) | `''` | Name shown in the Home Assistant front-end for this valve. Leave empty to skip it. |
| `DeviceClass` | STRING(100) | `'water'` | Home Assistant device class for the entity. Leave empty for the default. |
<!-- fb-interface:end -->

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities. 

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: VALVE_X** | A change is detected on output `VALVE_X`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
