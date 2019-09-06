## FB_INPUT_PUSHBUTTON_DIMMER_MQTT

### __General__
Big brother of FB_INPUT_PUSHBUTTON_MQTT with additional functionality to output a dimmer value (range 0-255).

### __Block diagram__
TODO:
![FB_INPUT_PUSHBUTTON_DIMMER_MQTT](../_img/FB_INPUT_PUSHBUTTON_DIMMER_MQTT.svg)

INPUT(S)
- PB: digital input linked to the signal wire of a pushbutton.

OUTPUT(S)
- SINGLE: output high for one clock cycle when a single push is detected on input `PB`.
- DOUBLE: output high for one clock cycle when a double push is detected on input `PB`.
- LONG: output high for one clock cycle when a long push is detected on input `PB`.
- Q:
- DBL:
- OUT: dimmer value, datatype byte. 

METHOD(S)
- InitMQTT: enables MQTT events on the FB: sets the MQTT publish topic and sets the pointer to the `MQTTPublishQueue`.
- ConfigureDimmer: configures the dimmer with your prefered configurations

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QOS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `SINGLE` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `DOUBLE` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `LONG` | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix variable and the function block name. 

### __Code example__

TODO

### __Home Assistant YAML__
TODO