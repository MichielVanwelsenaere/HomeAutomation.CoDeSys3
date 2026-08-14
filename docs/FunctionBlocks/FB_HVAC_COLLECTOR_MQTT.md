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
ARRAY [1..VALVE_COUNT] OF BOOL ──┤ THERMOSTAT       VALVE ├── ARRAY [1..VALVE_COUNT] OF BOOL
                                 │                   PUMP ├── BOOL
                                 └────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `THERMOSTAT` | ARRAY [1..VALVE_COUNT] OF BOOL | Heat demand, one element per manifold circuit. When high the valve should be opened and flow provided by the pump. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `VALVE` | ARRAY [1..VALVE_COUNT] OF BOOL | Output for the valve controlled by the thermostat at the same index. |
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
| `NameValve` | ARRAY [1..VALVE_COUNT] OF STRING(100) |  | Name shown in the Home Assistant front-end for each valve, indexed as `THERMOSTAT` and `VALVE` are. An empty name means that circuit is unwired and announces no entity. |
| `DeviceClass` | STRING(100) | `'water'` | Home Assistant device class for the entity. Leave empty for the default. |
<!-- fb-interface:end -->

### **Using it**

The index is part of the interface, not an implementation detail: `THERMOSTAT[1]`
drives `VALVE[1]`, which publishes to `<topic>/Valves/VALVE_1` and appears in Home
Assistant as an entity whose id ends `_VALVE_1`. Renumbering the circuits renames
Home Assistant entities and orphans their retained discovery configs.

Array elements cannot be named as formal parameters, so a caller assigns the
inputs, calls the block, then reads the outputs. `NameValve` likewise travels as a
whole array, so the caller needs somewhere to hold it — with a bound matching
`VALVE_COUNT` in the block:

```ST
// declaration
CollectorValveNames : ARRAY[1..8] OF STRING(100);

// once, at startup, after InitMqtt
CollectorValveNames[1] := 'Radiator 1';
CollectorValveNames[2] := 'Radiator 2';
FB_PUMP_2_COLLECTOR.InitMqttDiscovery(ADR(MqttVariables.PLC_Device), CollectorValveNames);

// every cycle
FB_PUMP_2_COLLECTOR.THERMOSTAT[1] := FB_THERMOSTAT_2.OUT;
FB_PUMP_2_COLLECTOR.THERMOSTAT[2] := FB_THERMOSTAT_3.OUT;

FB_PUMP_2_COLLECTOR();

DO_006 := FB_PUMP_2_COLLECTOR.VALVE[1];
DO_007 := FB_PUMP_2_COLLECTOR.VALVE[2];
```

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities. 

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: VALVE_X** | A change is detected on output `VALVE_X`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
