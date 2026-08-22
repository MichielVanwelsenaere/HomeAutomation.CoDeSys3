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
| `HEAT_REQUEST` | BOOL | Output for requesting heat from the burner. An alias of `PUMP`, so it carries the run-on too; the burner's own minimum runtime is controlled in the burner function block. |
| `MIN_ONTIME_ACTIVE` | BOOL | High while `PUMP` is on and its minimum on-time is not yet satisfied — including the run-on after `IN` has dropped. **Wire it to the collector's `PUMP_MIN_ONTIME_ACTIVE`** so the valves are held open for the run-on; see the note below. |

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
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `DeviceClass` | STRING(100) | `'heat'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **The run-on, and what has to know about it**

`PUMP` does not follow `IN`. The block wraps `OSCAT_BUILDING.ACTUATOR_PUMP`, whose
switch-off branch is gated on the minimum on-time:

```
ELSIF pump AND NOT in AND NOT manual AND tx - last_change >= min_ontime THEN
```

So after demand goes away the pump keeps running until `MIN_ONTIME` has elapsed
since it started. That is the point of the block — a pump that short-cycles wears
out — but it means **anything that shuts a flow path has to wait for the pump, not
for the demand.**

`MIN_ONTIME_ACTIVE` is that signal, and it is why the output exists. Feed it to
`FB_HVAC_COLLECTOR_MQTT.PUMP_MIN_ONTIME_ACTIVE` and the manifold holds the
circuits that were flowing open until the pump actually stops. Leave it unwired
and the valves shut the moment the thermostat is satisfied, while the pump runs on
against them.

Two more consequences of the same run-on, both worth a thought before changing a
timing:

- **The burner follows `PUMP`, not `IN`.** `HEAT_REQUEST` is an alias of `PUMP`, so
  the burner is still being asked for heat during the run-on. And because the
  burner has its own independent minimum on-time, its window can start *later* than
  the pump's and therefore end later — a boiler firing after the pump has stopped.
  Chaining two minimum on-times does not compose into one.
- **`RUN_EVERY` is passed as `T#0S` deliberately.** OSCAT's anti-seize feature
  starts the pump on its own after an idle period. On a manifold that means the
  pump starts with every valve shut, because no thermostat asked for anything and
  the collector has no way to know. Do not enable it without giving the collector a
  reason to open a circuit.

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: PUMP** | A change is detected on output `PUMP`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
