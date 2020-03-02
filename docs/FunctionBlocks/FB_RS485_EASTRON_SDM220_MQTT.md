## FB_RS485_EASTRON_SDM220_MQTT

### __General__
Used to process Modbus RTU data through RS485 to human understandable values and to publish updates to the data through MQTT.

### __Block diagram__

<img src="../_img/FB_RS485_EASTRON_SDM220_MQTT.svg" width="350">

OUTPUT(S)
- VOLTAGE: 
- CURRENT:
- ACTIVEPOWER:
- APPARENT_POWER:
- REACTIVE_POWER:
- POWER_FACTOR:
- PHASE_ANGLE:
- FREQUENCY:
- IMPORT_ACTIVE_ENERGY:
- EXPORT_ACTIVE_ENERGY:
- IMPORT_REACTIVE_ENERGY:
- EXPORT_REACTIVE_ENERGY:
- TOTAL_ACTIVE_ENERGY:
- TOTAL_REACTIVE_ENERGY:

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.  
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.
    
- ProcessData1: processes new Modbus RTU data, an overview of the parameters:
- ProcessData2: processes new Modbus RTU data, an overview of the parameters:
- ProcessData3: processes new Modbus RTU data, an overview of the parameters:


### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Output changes: OUT**   | A change is detected on output `OUT`. | `TRUE/FALSE` | 2 | `TRUE` | yes

MQTT publish topic is a concatination of the publish prefix and the function block name. 


### __Code example__

- variables initiation:
```
MQTTPubRS485Prefix              :STRING(100) := 'WAGO-PFC200/Out/RS485/';
FB_RS485_EASTRON_SDM220_001     :FB_RS485_EASTRON_SDM220_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_RS485_EASTRON_SDM220_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPubRS485Prefix),   (* pointer to string prefix for the MQTT publish topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),                     (* pointer to MQTTPublishQueue to send a new MQTT event *)
);
```
The MQTT publish topic in this code example will be `WAGO-PFC200/Out/RS485/FB_RS485_EASTRON_SDM220_001` (MQTTPubSwitchPrefix variable + function block name).



### __Home Assistant YAML__
TODO