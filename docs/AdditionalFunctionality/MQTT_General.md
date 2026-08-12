## **All MQTT settings**

The topics are predefined once in the `MqttVariables`.

MQTT works with subscriptions and publications. An example for a dimmer publication is 
  `Devices/PLC/Lab/Out/Dimmers/FB_AO_DIMMER_001/OUT`

If you change any of these topics, keep an eye on the **length of the topic and/or STRING() size**.
	
The topic root is built from `MqttMain` + `MqttType` + `MqttDevice`, so the reference project publishes under `Devices/PLC/Lab/`. Every topic in these docs assumes those values - change `MqttDevice` and all of them shift with it.

<!-- gvl:start -->
```ST
VAR_GLOBAL
    clientID : STRING := 'PLC-Lab';
    broker : STRING := '10.101.1.11:1883';
    fbMqttPublishQueue : FB_MqttPublishQueue;
    collector_FB_OUTPUT_SWITCH_MQTT : MQTT.CallbackCollector;
    collector_FB_OUTPUT_COVER_MQTT : MQTT.CallbackCollector;
    collector_FB_VIRTUAL_MQTT : MQTT.CallbackCollector;
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
    MqttPubVirtualPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/Virtuals/');
    MqttSubVirtualPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/Virtuals/');
    MqttPubRS485Prefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/RS485/');
    MqttSubRS485Prefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/RS485/');
    MqttPubHVACPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'Out/HVAC/');
    MqttSubHVACPrefix : STRING(100) := CONCAT(MqttBaseTopic, 'In/HVAC/');
    MqttSubSwitchTopic : STRING(100) := CONCAT(MqttSubSwitchPrefix, '+');
    MqttSubCoverTopic : STRING(100) := CONCAT(MqttSubCoverPrefix, '+');
    MqttSubVirtualTopic : STRING(100) := CONCAT(MqttSubVirtualPrefix, '+');
    MqttSubDimmerTopic : STRING(100) := CONCAT(MqttSubDimmerPrefix, '#');
    MqttSubRS485Topic : STRING(100) := CONCAT(MqttSubRS485Prefix, '#');
    MqttSubHVACTopic : STRING(100) := CONCAT(MqttSubHVACPrefix, '#');
END_VAR
```
<!-- gvl:end -->

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
