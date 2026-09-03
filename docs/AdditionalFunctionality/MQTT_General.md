## **All MQTT settings**

The topics are predefined once in the `GVL_MQTT`.

MQTT works with subscriptions and publications. An example for a dimmer publication is 
  `Devices/PLC/Lab/Out/Dimmers/FB_AO_DIMMER_001/OUT`

If you change any of these topics, keep an eye on the **length of the topic and/or STRING() size**.
	
The topic root is built from `MqttMain` + `MqttType` + `MqttDevice`, so the reference project publishes under `Devices/PLC/Lab/`. Every topic in these docs assumes those values - change `MqttDevice` and all of them shift with it.

<!-- gvl:start -->
```ST
VAR_GLOBAL
    MQTT_TOPIC_LEN : INT := 160;
    MQTT_SUFFIX_LEN : INT := 64;
    clientID : STRING := 'PLC-Lab';
    broker : STRING := '10.101.1.11:1883';
    fbMqttPublishQueue : FB_MQTT_PUBLISH_QUEUE;
    collector_FB_OUTPUT_SWITCH_MQTT : MQTT.CallbackCollector;
    collector_FB_OUTPUT_COVER_MQTT : MQTT.CallbackCollector;
    collector_FB_DIMMER_MQTT : MQTT.CallbackCollector;
    collector_FB_RS485_MQTT : MQTT.CallbackCollector;
    collector_FB_HVAC_MQTT : MQTT.CallbackCollector;
    MQTT_QOS_EXACTLY_ONCE : MQTT.QoS := MQTT.QoS.ExactlyOnce;
    MqttMain : STRING(16) := 'Devices/';
    MqttType : STRING(16) := 'PLC/';
    MqttDevice : STRING(16) := 'Lab/';
    MqttBaseTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(CONCAT(MqttMain, MqttType), MqttDevice);
    MqttDiagnosticTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'diagnostic');
    MqttAvailabilityTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'availability');
    MqttAvailabilityOnlinePayload : STRING(20) := 'online';
    MqttAvailabilityOfflinePayload : STRING(20) := 'offline';
    MQTTAvailabilityHartbeatTime : TIME := TIME#5s0ms;
    MqttHADiscoveryPrefix : STRING(16) := 'homeassistant/';
    PLC_Device : FB_PLC_MQTT_DISCOVERY_DEVICE;
    OWD_MULTISENSOR_01 : FB_1WIRE_MQTT_DISCOVERY_DEVICE;
    MqttPushbuttonPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/DigitalInputs/Pushbuttons/');
    MqttPubSwitchPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/DigitalOutputs/');
    MqttSubSwitchPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/DigitalOutputs/');
    MqttPubCoverPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/Covers/');
    MqttSubCoverPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/Covers/');
    MqttPubDimmerPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/Dimmers/');
    MqttSubDimmerPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/Dimmers/');
    MqttPubRS485Prefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/RS485/');
    MqttSubRS485Prefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/RS485/');
    MqttPubHVACPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/HVAC/');
    MqttPubAnalogInputPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'Out/AnalogInputs/');
    MqttSubHVACPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/HVAC/');
    MqttSubSwitchTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubSwitchPrefix, '+');
    MqttSubCoverTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubCoverPrefix, '#');
    MqttSubDimmerTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubDimmerPrefix, '#');
    MqttSubRS485Topic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubRS485Prefix, '#');
    MqttSubHVACTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubHVACPrefix, '#');
    bBrokerReachable : BOOL := TRUE;
    MQTT_LANE_MAIN : INT := 0;
    MQTT_LANE_RS485 : INT := 1;
    MQTT_LANE_HVAC : INT := 2;
END_VAR
```
<!-- gvl:end -->

## The publish queue

Every block publishes by handing a message to `GVL_MQTT.fbMqttPublishQueue`.
`PRG_MQTT.MQTT_PUBLISH` drains it and hands messages to a pool of
`FB_MQTT_PUBLISH_WORKER` instances — `PRG_MQTT.cudiPublishers` of them, which is
also what the pool array is sized from — and those do the actual sending.

### **One lane per producing task**

The queue is not one ring. It is a ring **per producing task**, drained round-robin
by the single consumer, because a ring shared between tasks cannot be made safe here
without a lock nobody can afford (see below). A lane is single-producer /
single-consumer: its write index is advanced only by the task that owns it, its read
index only by the drain, and each side merely reads the other's — one aligned `INT`
load on this 32-bit target, which cannot tear.

| Lane | Constant | Owner |
|:--|:--|:--|
| 0 | `GVL_MQTT.MQTT_LANE_MAIN` | MainTask — the default for anything that does not name a lane |
| 1 | `GVL_MQTT.MQTT_LANE_RS485` | the RS485 task, by far the loudest producer |
| 2 | `GVL_MQTT.MQTT_LANE_HVAC` | HvacTask |

`AddMessage` writes lane 0. `AddMessageOn(Lane := ...)` names one, and a block that
runs in its own task must use it. A discovery device takes its lane through
`SetLane`, once, after init.

**Name the lane, do not count.** The constants exist so that a new producer picks a
lane by naming the task it runs in; a bare number is how two tasks end up sharing
one. Adding a lane is not free either: a slot holds a `STRING(1500)` payload and a
`STRING(160)` topic, so it is about 1.8 kB, and the three lanes hold 341 slots each
to keep the total at the 1024 the single ring had. Widening `ciLanes` without
narrowing `ciLaneN` adds roughly 600 kB of static RAM per lane.

### **Reading its state**

| Member | Kind | Meaning |
|:--|:--|:--|
| `HasMessage()` | METHOD : BOOL | Something is queued. This is what the drain loop gates on. |
| `IsFull()` | METHOD : BOOL | No room for another message. Reports full one slot early. |
| `DroppedCount` | VAR_OUTPUT : UDINT | Messages discarded because a lane was full. Should stay at 0. It rides in the RS485 diagnostic as `drop=`. |

`HasMessage()` and `IsFull()` are **methods, not flags** — call them, do not read a
stored value. Both are computed from the read and write indices, so nothing shared is
mutable: the write index is only ever advanced by `AddMessage`, the read index only by
`GetMessage`, and each side merely reads the other's.

A stored flag could not be safe here. With the two indices equal a lane is either
completely empty or completely full, so the flag would be the only thing telling those
apart, and both the producers and the consumer would have to write it — leaving a
non-empty lane looking empty, where the workers stop draining and a retained state
change sits unsent, or clearing `IsFull()` while the lane really is full, where a
writer overwrites a message not yet sent. Reporting full one slot early is what pays
for computing them instead, and is why a lane of 341 slots carries 340 messages. `HasMessage()` answers for
any lane; `GetMessage` picks up where the last drain left off, so a loud lane cannot
starve a quiet one.

### **Why lanes rather than a lock**

Two tasks in `AddMessage` on the same ring both read the same write index, leave one
message in that slot built from each other's fields, and leave the next slot never
written — one publish corrupted, the next carrying whatever was in that slot a lap
earlier. Nothing detects it, because the slot count still balances. What reaches the
broker is a device publishing a payload it never sent, on a topic belonging to
another block, and its own counters still add up.

A lock is not the alternative. It would have to be held across a 1.5 kB payload copy,
and MainTask blocking on one held by the RS485 task is priority inversion on the task
that also drives the covers. `SysTask`, `CmpIecTask` and `SysCpuHandling` are all
unresolved on this device, so there is no runtime task identity to key a lock on and
no atomics to build one from either. Splitting the ring removes the shared mutable
index instead of guarding it.

### **What is still not safe**

**A discovery device shared between tasks publishes on one lane.** A lane is set per
device, and `GVL_MQTT.PLC_Device` is announced to from MainTask's blocks *and* from
the HVAC blocks, so it cannot take a lane of its own without moving one task's
discovery onto the other's. Its publishes therefore stay on lane 0 and two tasks can
still collide there.

The window is startup, when discovery configs and the first availability messages go
out; steady-state publishing is unaffected, because each block's own state publishes
name their task's lane. Giving it a lane per caller means either a discovery device
per task or a lane argument threaded through every `Create*Entity`, and neither has
been done.

## MQTT Birth and Last Will message

### **General**

The software supports so-called Birth and Last Will and Testament (LWT) messages. The former is used to send a message after the service has started, and the latter is used to notify other clients about an ungracefully disconnected client. In addition to a Birth message on startup, the Birth message is also published cyclically as a heartbeat.

### **Examples**

<ins>Birth message:</ins></br>
Topic: `Devices/PLC/Lab/availability`</br>
Payload: `online`


<ins>LWT message:</ins></br>
Topic: `Devices/PLC/Lab/availability`</br>
Payload: `offline`

Note that the topics and payloads can be changed in the code. The Birth message is by default published during startup and after that every 5 seconds (heartbeat). This can be changed in the code as well.

The Birth message is also published on connect and on **re**connect, off the rising
edge of the client's `MQTT_CONNECTED` flag in `PRG_MQTT` - the same edge that drives
the [U1 LED](User_leds_CODESYS3S_runtime.md).

## Device diagnostics

Every Home Assistant *device* announced from this project - the PLC itself, and
each RS485 sensor or meter that announces itself as a device of its own - gets two
diagnostic entities for free. `FB_BASE_MQTT_DISCOVERY_DEVICE.initBaseDevice`
creates them, so every discovery device has them and nothing has to ask:

| Entity | Platform | Follows |
|:--|:--|:--|
| `Availability` | `binary_sensor`, class `CONNECTIVITY` | the device's **own** availability topic |
| `Log` | `sensor` | the device's **own** `<diagnostic root>/Log` |

**Both name the device's own topics, not the controller's.** For the PLC that is
`Devices/PLC/Lab/availability` and `Devices/PLC/Lab/diagnostic/Log`. For an RS485
device it is that device's publish topic plus `/availability` and `/diagnostic/Log`
- so an SDM630's `Availability` entity reports whether *the meter* is answering on
the bus, which is what `OnTransactionDone` publishes, and its `Log` entity carries
only that meter's messages.

That distinction is the whole point. Pointing every device's diagnostics at the
controller's topics compiles, publishes and looks right, and produces one
`Availability` entity per device all mirroring the PLC's LWT plus one `Log` entity
per device all showing the same shared stream.

A device block wires it up by passing its own topics when it announces itself:

```
Device^.initEastronDevice(
	...
	availabilityTopic1	:= GVL_MQTT.MqttAvailabilityTopic,
	availabilityTopic2	:= CONCAT(THIS^.sMQTTPublishTopic, '/availability'),
	MqttDiagnosticTopic	:= CONCAT(THIS^.sMQTTPublishTopic, '/diagnostic'));
```

`availabilityTopic1` stays the controller's topic: an entity is unavailable if
*either* the PLC or the device is down, which is what Home Assistant's two-topic
availability list expresses. `availabilityTopic2` is what the `Availability`
diagnostic entity itself reports, and it falls back to topic 1 when a device does
not have one of its own.

### Writing to a device's log

`SendLogMessage` is a method on the discovery device, so it publishes to whichever
device you call it on:

```
GVL_MQTT.PLC_Device.SendLogMessage(str := 'Init finished', instance := 'PRG_MAIN');
```

The payload is `instance | str`, retained, so the entity holds the last message
across a restart. `PublishEntityConfig` calls it on `THIS^` for every entity a
device announces, which is why a device's log shows its own discovery trace even
when nothing else logs to it.
