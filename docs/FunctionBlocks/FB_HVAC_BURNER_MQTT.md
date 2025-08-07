## FB_HVAC_BURNER_MQTT
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)

### **General**

Designed to control a heat source with a simple on/off signal. Respects any minimum runtime requirements.

### **Block diagram**

<img src="../_img/FB_HVAC_BURNER_MQTT.svg" width="350">

INPUT(S)

- IN: datatype _BOOL_, when high heat production is required for the pump(s).

OUTPUT(S)

- OUT: datatype _BOOL_, follows input `IN` while respecting minimum and maximum allowed runtime configuration. 

METHOD(S)

- FB_init: constructor, overview of the parameters:
  - `MIN_ONTIME`: datatype _TIME_, minimum on time for the burner in order to prevent damage.
  - `MIN_OFFTIME`: datatype _TIME_, minimum off time for the burner in order to prevent damage.

- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
  - `MQTTPublishPrefix`: datatype _POINTER TO STRING_, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.
  - `MQTTSubscribePrefix`: datatype _POINTER TO STRING_, pointer to the MQTT subscribe prefix that should be used for publishing any messages/events to this FB. Suffix is automatically set to FB name.
  - `pMqttPublishQueue`: datatype _POINTER TO FB_MqttPublishQueue_, pointer to the MQTT queue to publish messages.
  - `pMqttCallbackCollector`: datatype _SD_MQTT.CallbackCollector_, pointer to the MQTT callback collector, required to register FB for subscriptions on a certain topic.
  - `MqttQos`: datatype _SD_MQTT.QoS_, configures the MQTT Qos for the function block published messages.
  - `MqttRetain`: datatype _BOOL_, configures the MQTT retain flag for the function block published messages.

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | MQTT payload | QoS                                  | Retain flag                          | Published on startup                 |
| :-------------------- | :---------------------------------- | :----------- | :----------------------------------- | :----------------------------------- | :----------------------------------- |
| **input changes: OUT** | A change is detected on output `OUT`. | `TRUE/FALSE` | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name.
