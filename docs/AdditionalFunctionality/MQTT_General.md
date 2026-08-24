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
    MqttSubHVACPrefix : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttBaseTopic, 'In/HVAC/');
    MqttSubSwitchTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubSwitchPrefix, '+');
    MqttSubCoverTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubCoverPrefix, '#');
    MqttSubDimmerTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubDimmerPrefix, '#');
    MqttSubRS485Topic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubRS485Prefix, '#');
    MqttSubHVACTopic : STRING(GVL_MQTT.MQTT_TOPIC_LEN) := CONCAT(MqttSubHVACPrefix, '#');
    bBrokerReachable : BOOL := TRUE;
END_VAR
```
<!-- gvl:end -->

### Topic lengths

`MQTT_TOPIC_LEN` (160) is the width of every declaration that stores a complete
topic - the GVL's own topics and prefixes, `sMQTTPublishTopic`, `AddMessage`'s
`Topic`, and every topic parameter on the discovery device. `MQTT_SUFFIX_LEN` (64)
is for the per-instance fragment appended to a prefix. Nothing in the topic path is
left at the IEC default of `STRING(80)`, because **IEC string assignment and
`CONCAT` both truncate silently** - there is no error and no warning, and the only
symptom is a Home Assistant entity that never updates.

Two deliberate exceptions, both fragments rather than topics:
`ST_RS485_COMMISSION_REQUEST.ReportTopic` (32) is a suffix under the bus prefix, and
`FB_RS485_DUCO_DUCOBOX_MQTT`'s `sSubTopic` holds what is left of a topic after the
subscribe prefix is stripped off.

**The real ceiling is lower than 160, and it is not ours.** A discovery payload is
composed by `PRO_JSON`, whose `JSONVAR` value field is
`STRING(GPL_JSON.MAX_VALUE_SIZE)` - and `MAX_VALUE_SIZE` is **150**. A topic longer
than 150 characters is cut when it is written into the discovery struct, whatever
our own declarations say. 150 is not reachable in practice here (the longest topic
in this project is about 66 characters), but it is the number to check against
before inventing very long device or instance names.

That value cannot be read from the library - a `.library` does not unpack, and
`dir()` on a ScriptEngine object returns nothing. It was established by compile
probe: assign a constant index into `ARRAY[1..1] OF BYTE` at
`GPL_JSON.MAX_VALUE_SIZE - N + 1` for a range of `N`, and read which lines the
compiler rejects. That oracle is **one-sided** - an index below the lower bound is
not reported, only one above the upper bound is - so it brackets rather than pins,
and it is worthless without a known-good and a known-bad control line. The obvious
probe, assigning an over-long string *constant*, is actively misleading here: it
reports `STRING(GPL_JSON.MAX_VALUE_SIZE)` as too small for a 21-character literal,
which the broker disproves.

## The publish queue

Every block publishes by handing a message to `GVL_MQTT.fbMqttPublishQueue`, a
ring buffer of 1025 slots. `PRG_MQTT.MQTT_PUBLISH` drains it and hands messages
to a pool of 40 `FB_MQTT_PUBLISH_WORKER` instances, which do the actual sending.

### **Reading its state**

| Member | Kind | Meaning |
|:--|:--|:--|
| `HasMessage()` | METHOD : BOOL | Something is queued. This is what the drain loop gates on. |
| `IsFull()` | METHOD : BOOL | No room for another message. Reports full one slot early. |
| `DroppedCount` | VAR_OUTPUT : UDINT | Messages discarded because the ring was full. Should stay at 0. |

`HasMessage()` and `IsFull()` are **methods, not flags** — call them, do not read a
stored value. There used to be `EMPTY` and `FULL` outputs and removing them was the
point: with the read and write index equal, the ring is either completely empty or
completely full, so a stored flag was the only thing distinguishing the two cases,
and both the producers and the consumer wrote it. Losing that race either left a
non-empty queue looking empty — the workers stop draining and a retained state
change sits unsent until something else publishes — or cleared `FULL` while the ring
really was full, letting a writer overwrite messages not yet sent.

Computing them from the indices instead means nothing shared is mutable: the write
index is only ever advanced by `AddMessage`, the read index only by `GetMessage`, and
each side merely reads the other's. Reporting full one slot early is what pays for
it, and is why the usable capacity is 1024 rather than 1025.

### **What is still not safe**

One race remains. Two tasks calling `AddMessage` at the same time can both read the
same write index, leave one message in that slot built from each other's fields, and
leave the next slot never written at all — so one publish is corrupted and the next
carries whatever was in that slot a lap earlier. Nothing detects it, because the
slot count still balances.

Four tasks write to this queue (MainTask, HvacTask, RS485, MqttCommunication, plus
Ping), so it is reachable. Fixing it needs one ring per producing task rather than a
lock: a lock would have to be held across a 1.5 kB payload copy, and MainTask
blocking on one held by RS485 is priority inversion on the task that also drives the
covers. `SysTask`, `CmpIecTask` and `SysCpuHandling` are all unresolved on this
device, so there is no runtime task identity and no atomics to build on either.

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

There is no `FB_MQTT_LOG` block. There used to be one - unreferenced, never
compiled - and it was deleted; logging is this method, not a block anyone
instantiates.
