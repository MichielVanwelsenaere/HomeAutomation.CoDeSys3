## FB_INPUT_BINARYSENSOR_MQTT

### __General__
Binary sensors gather information about the state of devices which have a "digital" return value (either 1 or 0). These can be switches, contacts, pins, etc. These sensors only have two states: *0/off/low/closed/false* and *1/on/high/open/true*

### __Block diagram__

<img src="../_img/FB_INPUT_BINARYSENSOR_MQTT.svg" width="350">

INPUT(S)
- BS: digital input linked to the signal wire of the binary sensor.

OUTPUT(S)
- Q: follows the input `BS` but debounced.
- EVENT: output high for one clock cycle when any event occurs on debounced input `BS`.
- EVENT_R: output high for one clock cycle when a rising edge is detected on debounced input `BS`.
- EVENT_F: output high for one clock cycle when a falling edge is detected on debounced input `BS`.

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name. 
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.

- ConfigureFunctionBlock: configures the behaviour of output `Q` using the parameters below:
    - `T_TurnOffDelay`: duration of the turn off delay added on output `Q` to prevent rapid ON/OFF behaviour on the output caused by a fast switching sensor on the digital input. Default to 0 seconds, can be extremely usefull when connecting a motion sensor the the PLC. 

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **input changes: BS**   | A change is detected on input `BS`. (*) | `ON/OFF` | 2 | `TRUE` | no

MQTT publish topic is a concatenation of the publish prefix variable and the function block name. 

### __Code example__

- variables initiation:
```
MQTTBinarySensorPrefix  :STRING(100) := 'WAGO-PFC200/Out/DigitalInputs/BinarySensors/';
FB_DI_BS_001            :FB_INPUT_BINARYSENSOR_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_INPUT_BINARYSENSOR_MQTT.InitMQTT(MQTTPublishPrefix:= ADR(MQTTBinarySensorPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue)                          (* pointer to MQTTPublishQueue to send a new MQTT event *)
);
```
The MQTT publish topic in this code example will be `WAGO-PFC200/Out/DigitalInputs/BinarySensors/FB_DI_BS_001` (MQTTBinarySensorPrefix variable + function block name).

- Configuration of the function block with a 5 second turn off delay on the output (called once during startup):
```
FB_INPUT_BINARYSENSOR_MQTT.ConfigureFunctionBlock(T_TurnOffDelay:= T#5S);         (* time to delay the negative edge on output Q *)
```

- reading digital input for events (cyclic):
```
FB_DI_BS_001(BS:= DI_001);
```

- integration with `FB_OUTPUT_SWITCH_MQTT`:
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIOHIGH:=      FALSE,                  (* brings the output high regardless of other input values *)
    PRIOLOW:=       FALSE,                  (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_BS_001.EVENT      (* for toggling the output *)	
);
```

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT binary sensor](https://www.home-assistant.io/components/binary_sensor.mqtt/) config:

```YAML
- platform: MQTT
  name: "FB_DI_BS_001"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/BinarySensors/FB_DI_BS_001"
  qos: 2  
  payload_on: "ON"
  payload_off: "OFF"
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
```