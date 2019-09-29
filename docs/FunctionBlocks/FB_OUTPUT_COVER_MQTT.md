## FB_OUTPUT_COVER_MQTT

### __General__
The cover function block allows you to control a covers such as a rollershutter or a garage door.

----------------------------

:rotating_light: Do not use this function block if the mechanical safety on your electric rollershutters hasn't been configured properly!

----------------------------

### __Block diagram__

<img src="../_img/FB_OUTPUT_COVER_MQTT.svg" width="350">

INPUT(S)

OUTPUT(S)

METHOD(S)
- InitMQTT: 
    
- PublishRecived: callback method called by the callbackcollector when a message is received on the subscribed topic by the callbackcollector.

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QOS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|

MQTT publish topic is a concatination of the publish prefix and the function block name. 

### __MQTT Subscription Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name. 

### __Code example__

- variables initiation:


- Init MQTT method call (called once during startup):



- checking for events to switch the digital output (cyclic):


- integration with 

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT cover](https://www.home-assistant.io/components/cover.mqtt/) config:
