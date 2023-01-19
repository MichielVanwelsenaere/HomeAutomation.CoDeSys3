## FB_MQTT_DEVICE

![](../_img/mqtt_log_in_ha.png)

INPUT(S)

OUTPUT(S)

METHOD(S)

- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
  - `MQTTPublishPrefix`: datatype _POINTER TO STRING_, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.
  - `pMqttPublishQueue`: datatype _POINTER TO FB_MqttPublishQueue_, pointer to the MQTT queue to publish messages.
  - `MqttQos`: datatype _SD_MQTT.QoS_, configures the MQTT Qos for the function block published messages.
  - `MqttRetain`: datatype _BOOL_, configures the MQTT retain flag for the function block published messages.
- send: allows logging to MQTT.
  - `payload`: datatype _STRING_, the payload to be sent to MQTT. String(128)

### **Code example**

- variables initiation: (inside MqttVariables)

```
	MQTT_logger							:FB_MQTT_LOG;
```

- Init MQTT method call (called once during startup):

```
MqttVariables.MQTT_logger.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttPubLogPrefix),
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue),
	MqttQos:=MQTT.QoS.ExactlyOnce,
	MqttRetain:=FALSE
);
```

To send a message to MQTT:

```
MqttVariables.MQTT_logger.send('Init finished');
```

## Home Assistant

To show the MQTT messages in Home Assistant, you need to go through three steps:

1. Add the following to your `configuration.yaml`:
   ```yaml
   - name: "plc_log"
     object_id: "plc_log"
     unique_id: "plc_log"
     state_topic: "Devices/PLC/House/debug"
     qos: 0
     device: *device # write or link your device here
     availability: *availability # write or link your availability here
   ```
2. Add the following to your dashboard:
   ```yaml
   type: logbook
   entities:
     - sensor.plc_log
   ```
