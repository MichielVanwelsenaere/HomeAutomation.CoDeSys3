## FB_INPUT_PUSHBUTTON_DIMMER_MQTT

### __General__
Big brother of FB_INPUT_PUSHBUTTON_MQTT with additional functionality to output a dimmer value (range 0-255).

### __Block diagram__
TODO:
![FB_INPUT_PUSHBUTTON_DIMMER_MQTT](../_img/FB_INPUT_PUSHBUTTON_DIMMER_MQTT.svg)

INPUT(S)
- PB: digital input linked to the signal wire of a pushbutton.
- VAL:
- SET:
- RST:

OUTPUT(S)
- SINGLE: output high for one clock cycle when a single push is detected on input `PB`.
- DOUBLE: output high for one clock cycle when a double push is detected on input `PB`.
- LONG: output high for one clock cycle when a long push is detected on input `PB`.
- Q:
- DBL:
- OUT: dimmer value, datatype byte. 

METHOD(S)
- InitMQTT: enables MQTT events on the FB: sets the MQTT publish topic and sets the pointer to the `MQTTPublishQueue`. If dimmer values are not required as MQTT output, set `OutputDimmer` to `FALSE`.
- ConfigureDimmer: configures the dimmer with your prefered configurations, an overview of the parameters and their default values:
    - `T_Debounce`: debounce time for input PB, defaults to 10ms.
    - `T_Reconfig`:  reconfguration time, defaults to 10S
    - `T_On_Max`: start limitation, defaults to 0ms.
    - `T_Dimm_Start`: reaction time to dim, defaults to 400ms.
    - `T_Dimm`: time for a dimming ramps, defaults to 3s.
    - `Min_On`: minimum value of output OUT at startup, defaults to 50.
    - `Max_On`: maximum value of output OUT at startup, defaults to 255.
    - `Soft_Dimm`: if TRUE dimming begins after ON and at 0. 
    - `Dbl_Toggle`: if TRUE the output DBL isinverted at each double-click, defaults to FALSE.
    - `Rst_Out`: if input Rst is TRUE, ouput OUT is set to 0, defaults to FALSE.
    - `T_Long`: configures the time parameter specifing the decoding time for long key press. Defaults to 400mS. When this timespan is reached while pushing the pushbutton a long push is detected on input `PB`.

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