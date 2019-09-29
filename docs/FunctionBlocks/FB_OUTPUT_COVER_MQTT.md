## FB_OUTPUT_COVER_MQTT

### __General__
The cover function block allows you to control a covers such as a rollershutter or a garage door. Using a time variable that specifies the time to close/open a cover completely its possible to control the specific position of the cover. That specific position variable is maintained through powercycles.

----------------------------

:rotating_light: Do not use this function block if the mechanical safety on your electric rollershutters hasn't been configured properly!

----------------------------

### __Block diagram__

<img src="../_img/FB_OUTPUT_COVER_MQTT.svg" width="350">

INPUT(S)
- UP: bool input to move the cover up.
- DN: bool input to move the cover down.
- PI: byte input, position to move cover to in automode. Automode can be enabled by maken UP and DN high simultaneous. 
- PRIO_UP: when high the cover will receive a constant signal to move up. Usage: make covers move up in case of a fire alarm for example. (*)
- PRIO_DN: when low the cover will receive a constant signal to move down. (*)

(*) When high, all incomming MQTT events will be ignored.

OUTPUT(S)
- POS: cover position value, byte datatype.
- MU: bool value, motor up signal.
- MD: bool value, moter down signal.

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name. 
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.
    - `Qos_POS`: datatype *SD_MQTT.QoS*, MQTT QoS of the POS MQTT events.
    - `Delta_POS`: datatype *INT*, resolution of the MQTT POS events. For example: specifying value *5* will configure the FB to only emit an MQTT event when the POS output differs *5* or more than its previous value. Note that the last value of output POS (when it has reached position the desired position) is always published. Even if the resolution delta hasn't been reached yet. This way the last POS value published through MQTT is always synchronized with the POS output of the FB.

- ConfigureFunctionBlock: configures the behaviour of the cover using the parameters below:
    - `T_LOCKOUT`: delay between change of direction. 
    - `T_UD`: run time to move the cover completely up/down.

- PublishReceived: callback method called by the callbackcollector when a message is received on the subscribed topic by the callbackcollector.

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QOS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Output changes: POS**   | A change is detected on output `POS`. (*) | `0-100` | configured in method call `InitMQTT` | `TRUE` | yes

MQTT publish topic is a concatination of the publish prefix and the function block name. 

### __MQTT Subscription Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **Open cover** | Request to open the cover. | `OPEN` | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low.
| **Close cover** | Request to close the cover. | `CLOSE` | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low.
| **Stop cover** | Request to stop the cover from moving. | `STOP` | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low.
| **Move cover to position** | Request to move the cover to a specific position. | `0-100` (*) | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low.

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name. 

(*): `0` meaning completely closed, `100` completely open.

### __Code example__

- variables initiation:


- Init MQTT method call (called once during startup):



- checking for events to switch the digital output (cyclic):


- integration with 

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT cover](https://www.home-assistant.io/components/cover.mqtt/) config:

```YAML
- platform: mqtt 
  name: "MQTT Cover" 
  command_topic: "WAGO-PFC200/In/Covers/FB_DO_COVER_001" 
  position_topic: "WAGO-PFC200/Out/Covers/FB_DO_COVER_001" 
  set_position_topic: "WAGO-PFC200/In/Covers/FB_DO_COVER_001" 
  payload_open: "OPEN" 
  payload_close: "CLOSE" 
  payload_stop: "STOP" 
  position_open: 100 
  position_closed: 0 
  qos: 2 
  optimistic: false 
  availability_topic: "Devices/WAGO-PFC200/availability" 
  payload_available: "online" 
  payload_not_available: "offline"
```