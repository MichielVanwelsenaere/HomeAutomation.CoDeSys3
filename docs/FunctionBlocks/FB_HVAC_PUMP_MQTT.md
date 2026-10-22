## FB_HVAC_PUMP_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control a pump with a simple on/off signal and request heat from the burner function block when it is required. Respects any minimum runtime requirements, and can run the pump once a day out of season so it does not seize.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────────────┐
       │           FB_HVAC_PUMP_MQTT           │
       ├───────────────────────────────────────┤
BOOL ──┤ IN                               PUMP ├── BOOL
BOOL ──┤ EXERCISE_DAILY           HEAT_REQUEST ├── BOOL
TIME ──┤ EXERCISE_INTERVAL   MIN_ONTIME_ACTIVE ├── BOOL
BOOL ──┤ EXERCISE_PERMIT      EXERCISE_REQUEST ├── BOOL
       │                       EXERCISE_ACTIVE ├── BOOL
       └───────────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `IN` | BOOL |  | Should be made high if pump flow is required. |
| `EXERCISE_DAILY` | BOOL | `FALSE` | Runs the pump for `MIN_ONTIME` once it has stood still for `EXERCISE_INTERVAL`, so it cannot seize over the summer. See *Daily exercise* below. |
| `EXERCISE_INTERVAL` | TIME | `TIME#1440m0s0ms` | How long the pump must stand still before an exercise run is due. Daily by default. |
| `EXERCISE_PERMIT` | BOOL | `TRUE` | High when the pump has somewhere to push water. Leave it at `TRUE` for an always-open circuit; behind a manifold, wire it to the collector's `EXERCISE_READY`. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PUMP` | BOOL | Output for switching the pump on and off. Respects a minimum on and off runtime value to prevent damaging the pump. |
| `HEAT_REQUEST` | BOOL | Output for requesting heat from the burner. Follows `PUMP` except during an exercise run, so it carries the run-on too; the burner's own minimum runtime is controlled in the burner function block. |
| `MIN_ONTIME_ACTIVE` | BOOL | High while `PUMP` is on and its minimum on-time is not yet satisfied — including the run-on after `IN` has dropped. **Wire it to the collector's `PUMP_MIN_ONTIME_ACTIVE`** so the valves are held open for the run-on; see the note below. |
| `EXERCISE_REQUEST` | BOOL | High from the moment an exercise run is due until the pump has stopped again. Wire it to the collector's `PUMP_EXERCISE_REQUEST`. |
| `EXERCISE_ACTIVE` | BOOL | High while the pump runs for exercise rather than for heat. `HEAT_REQUEST` stays low for the whole run. |

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

One more consequence of the same run-on, worth a thought before changing a
timing:

- **The burner follows `PUMP`, not `IN`.** `HEAT_REQUEST` is `PUMP` outside an
  exercise run, so the burner is still being asked for heat during the run-on. And because the
  burner has its own independent minimum on-time, its window can start *later* than
  the pump's and therefore end later — a boiler firing after the pump has stopped.
  Chaining two minimum on-times does not compose into one.

### **Daily exercise**

A circulator that stands still all summer can seize: the rotor sticks in the scale
and the motor cannot break it free when the heating season starts. Set
`EXERCISE_DAILY` and the block runs the pump for `MIN_ONTIME` whenever it has stood
still for `EXERCISE_INTERVAL` — a day, by default. In the heating season the pump
never stands still that long, so the run only happens when it is needed.

An exercise run is not heat demand:

- **The burner stays off.** `HEAT_REQUEST` is low for the whole run, including the
  cycle in which the pump is stopping. A single cycle of `HEAT_REQUEST` would be
  enough to start the burner for its full minimum on-time.
- **Real demand takes over.** `IN` going high ends the exercise at once and the
  pump carries on as a heating run, with `HEAT_REQUEST` following `PUMP` as usual.
- **The interval runs from when the pump last stopped**, for any reason, and
  restarts with the application. A PLC restarted more often than
  `EXERCISE_INTERVAL` never exercises its pumps.
- **The run is `MIN_ONTIME` long.** With `MIN_ONTIME` at `T#0S` the pump runs for
  a single cycle, which exercises nothing.

What the pump needs before it may start depends on what it is pumping into.

**A circuit that is always open** — a floor heating loop on its own pump, with no
zone valves — needs nothing. `EXERCISE_PERMIT` defaults to `TRUE`, so setting
`EXERCISE_DAILY` is the whole job. Two things are worth checking on the hydraulics,
though neither is the PLC's to solve: if the loop shares a boiler with domestic hot
water, the run circulates whatever is in the flow pipe, so the floor's mixing valve
or high-limit thermostat is what keeps a slug of hot water out of the screed; and
if the loop has a thermal actuator or zone valve that the PLC does not control, it
must open on its own or the run is dead-headed.

**A manifold with valves** needs a path opened first. With no thermostat asking for
heat, every valve on it is shut, and a pump started against them runs dead-headed —
the same failure the `MIN_ONTIME_ACTIVE` interlock above exists to prevent. So the
pump does not start on its own; it asks:

1. `EXERCISE_REQUEST` goes high as soon as the run is due. Wire it to
   `FB_HVAC_COLLECTOR_MQTT.PUMP_EXERCISE_REQUEST`, which opens every valve.
2. Wire the collector's `EXERCISE_READY` to `EXERCISE_PERMIT`. It goes high once
   the valves have had `ValveCycleTime` to open, and the pump runs from then.
3. Once the pump has stopped, `EXERCISE_REQUEST` drops and the valves close.

```ST
fbPump2Collector.PUMP_EXERCISE_REQUEST := fbPump2.EXERCISE_REQUEST;
fbPump2Collector();

fbPump2(
	IN := fbPump2Collector.PUMP,
	EXERCISE_DAILY := TRUE,
	EXERCISE_PERMIT := fbPump2Collector.EXERCISE_READY);
```

Opening every valve, not just one, is deliberate: a thermal actuator that has been
shut all summer sticks just as readily as the pump, so the run exercises the valves
too.

**Do not use OSCAT's `RUN_EVERY` for this.** It is passed as `T#0S`: the actuator's
own anti-seize starts the pump without asking anything, so behind a manifold it
starts against shut valves, and because `HEAT_REQUEST` follows `PUMP` it would also
fire the burner.

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: PUMP** | A change is detected on output `PUMP`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
