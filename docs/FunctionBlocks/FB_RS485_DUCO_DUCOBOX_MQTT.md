## FB_RS485_DUCO_DUCOBOX_MQTT

### __General__
Used to process Modbus RTU data through RS485 to human understandable values and publish data updates through MQTT if desired. Allows finegrained local control on your DucoBox.

----------------------------

:rotating_light: In order to leverage this modbus integration a communication print (partnumber 0000-4251) is required on the DucoBox.

----------------------------

DUCO DUCOBOX Focus data:
- [Productlink](https://www.duco.eu/uk/products/mechanical-ventilation/ventilation-units/ducobox-focus)
- [Modbus registers](../RS485/datasheets/DUCO_DUCOBOX_Modbus_Registers.pdf)

### __Block diagram__

<img src="../_img/FB_RS485_DUCO_DUCOBOX_MQTT.svg" width="500">

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.  
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.    
- InitRS485: configures the Modbus RTU device address and the execution/polling interval for the multiple modbus read commands.
- RequestBusTime: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
- GetRtuQuery: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
- ProcessDataArray: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatination of the publish prefix and the function block name, the OWD numer and a unique sensor value. For example:

`Devices/PLC/House/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/0/TYPE`

| output       | MQTT topc suffic | Unit        	  | Note 			  |
|:-------------|:-----------------|:------------------|:------------------|
| Type of module | `/TYPE` | N/A | Possible values: 10,11,12,13,14,15,16,17,18,19.
| Status | `/STATUS` | N/A | Possible values: 0,1,2,3,4,5,6,7,99.
| Current Power | `/ACTP` | Watts | Only present for 'Type' 10 (master unit).
| Indoor Temperature | `/TEMP` | °C |
| CO<sub>2</sub> Value | `/CO2` | ppm | CO<sub>2</sub> valve only.
| RH Value | `/RH` | % | Humidity Control valve only.
| Location Number | `/LOCNR` | N/A | Indicates a number of a group of components belonging together.

### __MQTT Subscription Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **write holding** | Writes an integer value to a specific register. | `INT` | Only integer values are processed further.

MQTT subscription topic is a concatenation of the subscribe prefix variable, function block name, node number and register number. For example, topic `Devices/PLC/House/In/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/1/0` with payload `30` will set the 'Target value (%)' parameter for node 1 (which in this case represents the entire system). Go through the DUCO modbus register documentation linked above for a deeper understanding.

Upon a succesfull write operation the received payload will be published on the 'Out' topic. Continuing with the example above this will result in a payload `30` to be published on topic `Devices/PLC/House/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/1/0`.

### __Code example__

- variables initiation:
```
MQTTPubRS485Prefix                :STRING(100) := 'Devices/PLC/House/Out/RS485/';
FB_RS485_DUCO_DUCOBOX_MQTT_001    :FB_RS485_DUCO_DUCOBOX_MQTT;
```

- Init RS485 method call (called once during startup):
```
FB_RS485_DUCO_DUCOBOX_MQTT_001.InitRS485(
	DataPollingInterval := T#20S,       (* Polling interval *)		
	DeviceAddress := 1                  (* Device address of the modbus device *)			
);
```

- Init MQTT method call (called once during startup):
```
FB_RS485_DUCO_DUCOBOX_MQTT_001.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttRS485Prefix),                       (* pointer to string prefix for the mqtt publish topic *)
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue)      (* pointer to MqttPublishQueue to send a new Mqtt event *)
);

```
The MQTT publish topic in this code example will be `Devices/PLC/House/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001` (MQTTPubSwitchPrefix variable + function block name).

- Registering device to a buscontroller (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_DUCO_DUCOBOX_MQTT_001);
```

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config:

```YAML
mqtt:
  sensor:
  
```