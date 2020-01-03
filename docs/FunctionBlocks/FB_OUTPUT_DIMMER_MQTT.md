## FB_OUTPUT_DIMMER_MQTT

### __General__
Can be controlled using pulses from [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md), maintains output state through powercycles.

### __Block diagram__

<img src="../_img/FB_OUTPUT_DIMMER_MQTT.svg" width="350">

INPUT(S)
- SINGLE: input to connect to one or multiple `SINGLE` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md).
- DOUBLE: input to connect to one or multiple `DOUBLE` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md).
- LONG: input to connect to one or multiple `LONG` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md).
- P_LONG: input to connect to one or multiple `P_LONG` from one or multiple [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md).
- PRIO_HIGH: when high the output `Q` is set to high with a maximum brightness, has priority over the other inputs.
- PRIO_LOW: when high the output `Q` is set to low, has priority over the other inputs.
- VAL: byte value for SET operation.
- SET: input for switching output DIM to input VAL value.
- RST: input to switch of the output.

INPUT/OUTPUT(S)
- OUT: dimmer value, byte datatype. 

OUTPUT(S)
- Q: output.
- DBL: double-click output.

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name. 
    - `MQTTSubscribePrefix`: datatype *POINTER TO STRING*, pointer to the MQTT subscribe prefix that should be used for publishing any messages/events to this FB. Suffix is automatically set to FB name. 
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.
    - `OutputDimmer`: datatype *BOOL*, specify whether the DIM values (0-255) should be outputted as MQTT events.
    - `Qos_Dimm`: datatype *SD_MQTT.QoS*, MQTT QoS of the DIM MQTT events.
    - `Delta_Dimm`: datatype *INT*, resolution of the MQTT OUT events. For example: specifying value *5* will configure the FB to only emit an MQTT event when the OUT output differs *5* or more than its previous value. Note that the last value of output OUT (when input `P_LONG` becomes low again) is always published. Even if the resolution delta hasn't been reached yet. This way the last OUT value published through MQTT is always synchronized with the OUT output of the FB.

- ConfigureDimmer: configures the dimmer with your prefered configurations, an overview of the parameters and their default values:
    - `T_Debounce`: debounce time for input PB, defaults to 10ms.
    - `T_Reconfig`:  reconfiguration time, defaults to 10S.
    - `T_On_Max`: start limitation, defaults to 0ms.
    - `T_Dimm_Start`: reaction time to dim, defaults to 400ms.
    - `T_Dimm`: time for a dimming ramps, defaults to 3s.
    - `Min_On`: minimum value of output OUT at startup, defaults to 50.
    - `Max_On`: maximum value of output OUT at startup, defaults to 255.
    - `Soft_Dimm`: if TRUE dimming begins after ON and at 0. 
    - `Dbl_Toggle`: if TRUE the output DBL is inverted at each double-click, defaults to FALSE.
    - `Rst_Out`: if input Rst is TRUE, ouput OUT is set to 0, defaults to FALSE.
    
- PublishReceived: callback method called by the callbackcollector when a message is received on the subscribed topic by the callbackcollector.
### __Function Block Behaviour__
The following table shows the operating status of the dimmer:

| SINGLE/DOUBLE/LONG/P_LONG | SET | RST | Q | DIR | DBL | OUT |
|:-------------|:------------------|:------------------|:------------------|:------------------|:------------------|:------------------|
| SINGLE        | 0                 | 0                 | NOT Q             | OUT < 127         | -                 | LIMIT(MIN_ON,OUT,MAX_ON)
| DOUBLE        | 0                 | 0                 | -                 | -                 | TOG PULSE         | 
| LONG/P_LONG   | 0                 | 0                 | ON                | NOT DIR           | -                 | Ramp up or down depending on DIR, start at 0 when soft_dimm = TRUE and Q = 0, reverse direction if 0 or 255 is reached
| 0             | 1                 | 0                 | ON                | OUT < 127         | -                 | VAL
| 0             | 0                 | 1                 | OFF               | UP                | OFF               | 0 when RST_OUT = TRUE

This MQTT function block is a wrapper of the `DIMM_I` function block in the OSCAT building library enhanced with additional functionality in order to be able to emit MQTT events. To fully understand it's logic it's advised to give the documentation present in [the OSCAT building library docs](http://www.oscat.de/images/OSCATBuilding/oscat_building100_en.pdf) a good read (page 52).

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Output changes: Q**   | A change is detected on output `Q`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: DBL**   | A change is detected on output `DBL`. (*) | `TRUE/FALSE` | 2 | `TRUE` | no
| **Output changes: OUT**   | A change is detected on output `OUT`. (*) | `0-255` | configured in method call `InitMQTT` | `TRUE` | no

(*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output. 

### __MQTT Subscription Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **Change output Q to high** | Request to change output to high. | `TRUE` | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low.
| **Change output Q to low** | Request to change output to low. | `FALSE` | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low.
| **Set OUT byte value** | Request to set the byte value on input/output `OUT`. | `0-255` | Command executed when `PRIO_HIGH` input is low.

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name. 

### __Code example__

- variables initiation:
```
MqttPubDimmerPrefix			:STRING(100) := 'WAGO-PFC200/Out/Dimmers/';
MqttSubDimmerPrefix			:STRING(100) := 'WAGO-PFC200/In/Dimmers/';
FB_AO_DIMMER_001			:FB_OUTPUT_DIMMER_MQTT;	
```

- Init MQTT method call (called once during startup):
```
FB_AO_DIMMER_001.InitMQTT(MQTTPublishPrefix:= ADR(MqttPubDimmerPrefix),     (* pointer to string prefix for the MQTT publish topic *)
	MQTTSubscribePrefix:= ADR(MqttSubDimmerPrefix),                         (* pointer to string prefix for the MQTT subscribe topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),             (* pointer to MQTTPublishQueue to send a new MQTT event *)
	pMqttCallbackCollector := ADR(MqttVariables.collector_FB_DIMMER_MQTT),  (* pointer to CallbackCollector to receive Mqtt subscription events *)
    TRUE,                                                                   (* specify whether dimmer value should be outputted on MQTT topic *)
    SD_MQTT.QoS.ExactlyOnce,                                                (* specify the QoS for the dimmer mqtt events (values 0-255) *)    
    5                                                                       (* specify the resolution for the dimmer mqtt events *)    
);
```
The MQTT publish topic in this code example will be `WAGO-PFC200/Out/Dimmers/FB_AO_DIMMER_001` (MQTTPubSwitchPrefix variable + function block name). The subscription topic will be `WAGO-PFC200/In/Dimmers/FB_AO_DIMMER_001` (MQTTSubSwitchPrefix variable + function block name).

- checking for events to switch the digital output (cyclic):
```
FB_AO_DIMMER_001(SINGLE:=   FB_DI_PB_041.SINGLE,    (* for toggling the output Q *)
    DOUBLE:=                FB_DI_PB_041.DOUBLE,    (* for controlling the output DBL *)
    LONG:=                  FB_DI_PB_041.LONG,      (* for controlling the dimmer output OUT *)
    P_LONG:=                FB_DI_PB_041.P_LONG,    (* for controlling the dimmer output OUT *)
    Q=>                     DO_001,                 (* couple the function block to the physical digital output *)
    OUT:=                   AO_001                  (* couple the function block to the physical anolog output *)
);
```
the above illustrates an integration with [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md) as well.

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT lights](https://www.home-assistant.io/components/light.mqtt/) config:

```YAML
- platform: MQTT
  name: "FB_AO_DIM_001"
  state_topic: "WAGO-PFC200/Out/DigitalOutputs/FB_AO_DIM_001/Q"
  command_topic: "WAGO-PFC200/In/DigitalOutputs/FB_AO_DIM_001"
  brightness_command_topic: "WAGO-PFC200/In/DigitalOutputs/FB_AO_DIM_001"
  brightness_scale: 255
  brightness_state_topic: "WAGO-PFC200/Out/DigitalOutputs/FB_AO_DIM_001/OUT"
  on_command_type: "last"
  payload_on: "TRUE"
  payload_off: "FALSE"
  qos: 2
  optimistic: false
  availability_topic: "Devices/WAGO-PFC200/availability"
  payload_available: "online"
  payload_not_available: "offline"
```