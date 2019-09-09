## FB_INPUT_PUSHBUTTON_DIMMER_MQTT

### __General__
Big brother of input function block [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md) with additional functionality to output a realtime dimmer value (range 0-255).

### __Block diagram__

![FB_INPUT_PUSHBUTTON_DIMMER_MQTT](../_img/FB_INPUT_PUSHBUTTON_DIMMER_MQTT.svg)

INPUT(S)
- PB: digital input linked to the signal wire of a pushbutton.
- VAL: byte value for SET operation.
- SET: input for switching output OUT to input VAL value.
- RST: input to switch of the output.

OUTPUT(S)
- SINGLE: output high for one clock cycle when a single push is detected on input `PB`.
- DOUBLE: output high for one clock cycle when a double push is detected on input `PB`.
- LONG: output high for one clock cycle when a long push is detected on input `PB`.
- Q: output.
- DBL: double-click output.
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

### __Function Block Behaviour__
This MQTT function block is a wrapper of the `DIMM_I` function block in the OSCAT building library enhanced with additional functionality in order to be able to emit MQTT events for single, double, long and dimmer events. To fully understand it's logic it's adviced to give the documentation present in [the OSCAT building library docs](http://www.oscat.de/images/OSCATBuilding/oscat_building100_en.pdf) a good read (page 52).

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QOS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Pushbutton single press** | A single pushbutton press is detected on input `PB`. | `SINGLE` | 2 | `FALSE` | no
| **Pushbutton double press** | A double pushbutton press is detected on input `PB`. | `DOUBLE` | 2 | `FALSE` | no
| **Pushbutton long press**   | A long pushbutton press is detected on input `PB`. | `LONG` | 2 | `FALSE` | no
| **Output changes: Q**   | A change is detected on output `Q`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DBL**   | A change is detected on output `DBL`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: OUT**   | A change is detected on output `OUT`. (*) | `0-255` | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix variable and the function block name.

(*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output. 

### __Code example__

- variables initiation:
```
MQTTPushbuttonPrefix    :STRING(100) := 'WAGO-PFC200/Out/DigitalInputs/Pushbuttons/';
FB_DI_PB_001            :FB_INPUT_PUSHBUTTON_DIMMER_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DI_PB_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPushbuttonPrefix),    (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),         (* pointer to MQTTPublishQueue to send a new MQTT event *)
    TRUE                                                                (* specify whether dimmer value should be outputted on MQTT topic *)
);
```
The MQTT publish topic in this code example will be `WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001` (MQTTPushbuttonPrefix variable + function block name). Note that for the outputs `Q`, `DBL` and `OUT` the MQTT publish topic has an additional concatination being the name of the output. For example: `WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/OUT`.

- reading digital input for events (cyclic):
```
FB_DI_PB_001(PB:= DI_001);
```

- integration with `?`: There's currently no integration with an output function block possible as there's currently no output function block that supports dimming values. Got some hardware laying around that supports dimming on an output? Open [a git issue on the repo](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/issues/new) and let's collaborate on it! 

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config:

```YAML
# To receive single/double/long events
- platform: MQTT
  name: "FB_DI_PB_001"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001"
  qos: 2
  expire_after: 3
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
# To receive state of output Q
- platform: MQTT
  name: "FB_DI_PB_001_Q"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/Q"
  qos: 2
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
# To receive state of output DBL
- platform: MQTT
  name: "FB_DI_PB_001_DBL"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/DBL"
  qos: 2
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
# To receive state of output OUT
- platform: MQTT
  name: "FB_DI_PB_001_OUT"
  state_topic: "WAGO-PFC200/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001/OUT"
  qos: 2
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
```