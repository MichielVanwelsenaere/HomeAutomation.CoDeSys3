## FB_RS485_EASTRON_SDM220_MQTT

### __General__
Used to process Modbus RTU data through RS485 to human understandable values and publish data updates through MQTT if desired.
Due to the large amount of modbus registers exposed and the Eastron SDM220 limitation to read at maximum 40 registers at once the function block requires three modbus read commands to read out all the available data. Each of these three modbus read command reads out multiple registers at once which guarantees a consistent data readout as datapoints are extracted at a single point in time.

Eastron SDM220 datasheets:
- [SDM220ModbusEN](../RS485/datasheets/SDM220ModbusEN.pdf)
- [SDM220Register](../RS485/datasheets/SDM220Register.pdf)

### __Block diagram__

<img src="../_img/FB_RS485_EASTRON_SDM220_MQTT.svg" width="350">

OUTPUT(S):
- VOLTAGE: datatype real, part of modbus read commando 1.
- CURRENT: datatype real, part of modbus read commando 1.
- ACTIVEPOWER: datatype real, part of modbus read commando 1.
- APPARENT_POWER: datatype real, part of modbus read commando 1.
- REACTIVE_POWER: datatype real, part of modbus read commando 1.
- POWER_FACTOR: datatype real, part of modbus read commando 1.
- PHASE_ANGLE: datatype real, part of modbus read commando 1.
- FREQUENCY: datatype real, part of modbus read commando 2.
- IMPORT_ACTIVE_ENERGY: datatype real, part of modbus read commando 2.
- EXPORT_ACTIVE_ENERGY: datatype real, part of modbus read commando 2.
- IMPORT_REACTIVE_ENERGY: datatype real, part of modbus read commando 2.
- EXPORT_REACTIVE_ENERGY: datatype real, part of modbus read commando 2.
- TOTAL_ACTIVE_ENERGY: datatype real, part of modbus read commando 3.
- TOTAL_REACTIVE_ENERGY: datatype real, part of modbus read commando 3.

Outputs sharing the same modbus read commando are read from the device at a single point in time. 

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.  
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.
    
- TODO


### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatination of the publish prefix and the function block name and a unique value: 
| output       | MQTT topc suffic | 
|:-------------|:------------------|
| VOLTAGE | `/VOLT`
| CURRENT | `/CURR`
| ACTIVEPOWER |  `/ACTP`
| APPARENT_POWER | `/APPP`
| REACTIVE_POWER | `/REAP`
| POWER_FACTOR | `/POWF`
| PHASE_ANGLE | `/PHAA`
| FREQUENCY | `/FREQ`
| IMPORT_ACTIVE_ENERGY | `/IMAE`
| EXPORT_ACTIVE_ENERGY | `/EXAE`
| IMPORT_REACTIVE_ENERGY | `/IMRE`
| EXPORT_REACTIVE_ENERGY | `/EXRE`
| TOTAL_ACTIVE_ENERGY | `/TOTAE`
| TOTAL_REACTIVE_ENERGY | `/TOTRE`

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