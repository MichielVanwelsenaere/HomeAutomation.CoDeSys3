## FB_INPUT_PUSHBUTTON_MQTT

### __General__
Reads out a digital input and sets a single, double or long output high for one cyclus when a single, double or long press has been detected on the input.

### __Block diagram__

![FB_INPUT_PUSHBUTTON_MQTT](../_img/FB_INPUT_PUSHBUTTON_MQTT.svg)

INPUT(S)
- PB: digital input linked to the signal wire of a pushbutton.

OUTPUT(S)
- SINGLE: output high for one clock cycle when a single push is detected on input `PB`.
- DOUBLE: output high for one clock cycle when a double push is detected on input `PB`.
- LONG: output high for one clock cycle when a long push is detected on input `PB`.

METHOD(S)
- InitMQTT: enables MQTT events on the FB: sets the topic to publish to and sets the pointer to the `MQTTPublishQueue`.

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QOS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `SINGLE` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `DOUBLE` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `LONG` | 2 | `FALSE` | no

### __Code example__

- variables initiation:
```
MQTTPushbuttonPrefix    :STRING(100) := 'WAGO-PFC200/Out/DigitalInputs/Pushbuttons/';
FB_DI_PB_001            :FB_INPUT_PUSHBUTTON_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DI_PB_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPushbuttonPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    MQTTTopicSuffix := 'FB_DI_PB_001',                                  (* value to suffix the the MQTT topic, should be unique for each FB *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue)          (* pointer to MQTTPublishQueue to send a new MQTT event *)
);
```

- reading digital input for events (cyclic):
```
FB_DI_PB_001(PB:= DI_001);
```

- integration with `FB_OUTPUT_SWITCH_MQTT`:
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIOHIGH:=      FALSE,                  (* brings the output high regardless of other input values *)
    PRIOLOW:=       FALSE,                  (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_PB_001.SINGLE     (* for toggling the output *)	
);
```

### __Home Assistant yaml__
To integrate with Home Assistant use the yaml code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config:

```yaml
- platform: MQTT
  name: "FB_DI_PB_001"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001"
  qos: 2
  expire_after: 3
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
```