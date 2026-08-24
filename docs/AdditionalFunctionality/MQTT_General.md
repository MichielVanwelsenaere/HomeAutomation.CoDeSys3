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
    collector_FB_MQTT_LOG : MQTT.CallbackCollector;
    collector_FB_RS485_MQTT : MQTT.CallbackCollector;
    collector_FB_HVAC_MQTT : MQTT.CallbackCollector;
    MQTT_QOS_EXACTLY_ONCE : MQTT.QoS := MQTT.QoS.ExactlyOnce;
    MqttMain : STRING(16) := 'Devices/';
    MqttType : STRING(16) := 'PLC/';
    MqttDevice : STRING(16) := 'Lab/';
    MqttBaseTopic : STRING(100) := CONCAT(CONCAT(MqttMain, MqttType), MqttDevice);
    MqttDiagnosticTopic : STRING(100) := CONCAT(MqttBaseTopic, 'diagnostic');
    MqttAvailabilityTopic : STRING(100) := CONCAT(MqttBaseTopic, 'availability');
    MqttAvailabilityOnlinePayload : STRING(20) := 'online';
    MqttAvailabilityOfflinePayload : STRING(20) := 'offline';
    MQTTAvailabilityHartbeatTime : TIME := TIME#5s0ms;
    MqttHADiscoveryPrefix : STRING(16) := 'homeassistant/';
    PLC_Device : FB_PLC_MQTT_DISCOVERY_DEVICE;
    OWD_MULTISENSOR_01 : FB_1WIRE_MQTT_DISCOVERY_DEVICE;
    MqttPushbuttonPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/DigitalInputs/Pushbuttons/');
    MqttPubSwitchPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/DigitalOutputs/');
    MqttSubSwitchPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/DigitalOutputs/');
    MqttPubCoverPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/Covers/');
    MqttSubCoverPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/Covers/');
    MqttPubDimmerPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/Dimmers/');
    MqttSubDimmerPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/Dimmers/');
    MqttPubRS485Prefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/RS485/');
    MqttSubRS485Prefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/RS485/');
    MqttPubHVACPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/HVAC/');
    MqttSubHVACPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/HVAC/');
    MqttSubSwitchTopic : STRING(100) := CONCAT(MqttSubSwitchPrefix, '+');
    MqttSubCoverTopic : STRING(100) := CONCAT(MqttSubCoverPrefix, '#');
    MqttSubDimmerTopic : STRING(100) := CONCAT(MqttSubDimmerPrefix, '#');
    MqttSubRS485Topic : STRING(100) := CONCAT(MqttSubRS485Prefix, '#');
    MqttSubHVACTopic : STRING(100) := CONCAT(MqttSubHVACPrefix, '#');
    bBrokerReachable : BOOL := TRUE;
END_VAR
```
<!-- gvl:end -->

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

