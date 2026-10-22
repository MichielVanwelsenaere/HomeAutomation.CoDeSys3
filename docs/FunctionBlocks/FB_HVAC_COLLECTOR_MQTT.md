## FB_HVAC_COLLECTOR_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control multiple valves that share the same pump. Valves can be controlled via the thermostat function blocks.

<!-- fb-interface:start -->
### **Block diagram**

```text
                                  ┌─────────────────────────────────────────┐
                                  │          FB_HVAC_COLLECTOR_MQTT         │
                                  ├─────────────────────────────────────────┤
ARRAY [1..ciValveCount] OF BOOL ──┤ THERMOSTAT                        VALVE ├── ARRAY [1..ciValveCount] OF BOOL
                           BOOL ──┤ PUMP_MIN_ONTIME_ACTIVE             PUMP ├── BOOL
                           BOOL ──┤ PUMP_EXERCISE_REQUEST    EXERCISE_READY ├── BOOL
                                  └─────────────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `THERMOSTAT` | ARRAY [1..ciValveCount] OF BOOL |  | Heat demand, one element per manifold circuit. When high the valve should be opened and flow provided by the pump. |
| `PUMP_MIN_ONTIME_ACTIVE` | BOOL |  | Wire to the pump's `MIN_ONTIME_ACTIVE`. While it is high the circuits that were last flowing are held open, so the pump is never left turning against a shut manifold. Optional: left unwired it reads FALSE and the block behaves as it did before. |
| `PUMP_EXERCISE_REQUEST` | BOOL |  | Wire it to the pump's `EXERCISE_REQUEST`. While it is set and no circuit asks for heat, every valve is opened so the pump's exercise run has a path. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `VALVE` | ARRAY [1..ciValveCount] OF BOOL | Output for the valve controlled by the thermostat at the same index. |
| `PUMP` | BOOL | Output that should be directed to an HVAC pump function block in order to turn a pump on or off. |
| `EXERCISE_READY` | BOOL | High once the valves have been open for `ValveCycleTime` for an exercise run. Wire it to the pump's `EXERCISE_PERMIT`. |

### **Methods**

**`FB_init`** — Constructor, overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `ValveCycleTime` | TIME |  | Time required to fully open or close a valve. Pump output will only be switched when at least one valve is fully open. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `NameValve` | ARRAY [1..ciValveCount] OF STRING(100) |  | Name shown in the Home Assistant front-end for each valve, indexed as `THERMOSTAT` and `VALVE` are. An empty name means that circuit is unwired and announces no entity. |
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
`ciValveCount` in the block:

```ST
// declaration
asCollectorValveNames : ARRAY[1..8] OF STRING(100);

// once, at startup, after InitMqtt
asCollectorValveNames[1] := 'Radiator 1';
asCollectorValveNames[2] := 'Radiator 2';
fbPump2Collector.InitMqttDiscovery(ADR(GVL_MQTT.PLC_Device), asCollectorValveNames);

// every cycle
fbPump2Collector.THERMOSTAT[1] := fbThermostat2.OUT;
fbPump2Collector.THERMOSTAT[2] := fbThermostat3.OUT;
fbPump2Collector.PUMP_MIN_ONTIME_ACTIVE := fbPump2.MIN_ONTIME_ACTIVE;
fbPump2Collector.PUMP_EXERCISE_REQUEST := fbPump2.EXERCISE_REQUEST;

fbPump2Collector();

DO_006 := fbPump2Collector.VALVE[1];
DO_007 := fbPump2Collector.VALVE[2];

fbPump2(
	IN := fbPump2Collector.PUMP,
	EXERCISE_DAILY := TRUE,
	EXERCISE_PERMIT := fbPump2Collector.EXERCISE_READY);
```

### **The pump interlock — wire `PUMP_MIN_ONTIME_ACTIVE`**

`FB_HVAC_PUMP_MQTT` holds its output for `MIN_ONTIME` after its `IN` drops, to stop
the pump short-cycling. This block, left to itself, closes every valve in the cycle
demand ends. Put those two together and the pump spends the rest of its minimum
on-time turning against a manifold that is closing — running dry, with nowhere for
the water to go.

Whether it actually got there depended on two timings configured on two different
blocks, with nothing in the code relating them:

> dead-head if the valves close in less than the pump's `MIN_ONTIME`

The reference project sits on the safe side of that by a minute — `ValveCycleTime`
`T#3M` against `MIN_ONTIME` `T#2M` — but nothing defended the margin, and
`ValveCycleTime` is the time a valve takes to **open**. Closing time is not modelled
anywhere, so the margin rested on a physical property the code never sees.

Wiring `PUMP_MIN_ONTIME_ACTIVE` removes the coupling: while the pump is running out
its minimum on-time, the circuits that were last flowing stay open, and they close
once it stops. It is requirement 2.3 of the chain as designed:

    2.2 The heating valve can only turn on the pump once it's fully open
    2.3 The heating valve can only start closing once the pump has completed its
        minimum cycle time

Three things worth knowing about the hold:

- **It cannot latch the pump on.** The hold re-opens valves, but `PUMP` is built
  from `THERMOSTAT`, not from `VALVE`, so the block never re-requests the pump: the
  minimum on-time expires, the input clears, the valves close. Rebuilding `PUMP`
  from `VALVE[]` would close that loop and hold the pump on for ever. That used to
  be an identity and is not one any more.
- **It holds the circuits that were flowing**, not an arbitrary one, so the water
  keeps going where it was already going.
- **It publishes.** A held valve reports `TRUE` on MQTT for as long as it is held,
  which is what Home Assistant should see — the valve really is open.

If you leave it unwired, keep the pump's `MIN_ONTIME` shorter than the time the
valves take to close, and be aware that nothing checks it for you. On real hardware
the robust answer is both: wire the interlock **and** fit a differential bypass on
the manifold.

### **The pump's daily exercise — wire `PUMP_EXERCISE_REQUEST` and `EXERCISE_READY`**

`FB_HVAC_PUMP_MQTT` can run its pump once a day through the summer so it does not
seize. Behind this block that run needs a path: with no thermostat asking for heat,
every valve is shut, and a pump started against them runs dead-headed. So the pump
does not start on its own. It asks, and this block answers:

1. The pump raises `EXERCISE_REQUEST`.
2. If no circuit is asking for heat, every valve opens — all `ciValveCount` of
   them, not only the ones that were last flowing. A thermal actuator that has
   stood shut all summer sticks just as readily as the pump does, so the run
   exercises the valves too.
3. After `ValveCycleTime`, the same travel time a heating run waits for,
   `EXERCISE_READY` goes high and the pump runs for its `MIN_ONTIME`.
4. The pump drops its request once it has stopped, and the valves close.

No heat is requested at any point: the pump keeps `HEAT_REQUEST` low for an
exercise run, so the burner stays off and only the water already in the circuits
moves. Real demand during the run takes over the ordinary way — the valves follow
`THERMOSTAT` again, and the pump starts for heat once they have had their travel
time.

The open valves publish `TRUE` on MQTT while the run lasts, including circuits that
announce no Home Assistant entity.

Leave both unwired and the pump's own `EXERCISE_PERMIT` defaults to `TRUE`, so a
pump with `EXERCISE_DAILY` set would start against shut valves. Do not enable the
exercise on a pump behind this block without wiring the pair.

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities. 

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **output changes: VALVE_X** | A change is detected on output `VALVE_X`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
