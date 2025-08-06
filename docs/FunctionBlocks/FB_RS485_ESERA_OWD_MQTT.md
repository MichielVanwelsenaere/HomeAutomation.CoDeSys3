## FB_RS485_ESERA_OWD_MQTT
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)

### **General**
Designed to communicate with [Esera](https://esera.de/) 1-Wire modbus gateway this functionality allows pulling data from an extensive 1-Wire network in the PLC and publish updates through MQTT if desired.

Esera supports and produces a wide range of 1-Wire devices; indoor/outdoor temperature sensors, humidity sensors, brightness sensors, air quality sensors, etc.

Required hardware:

[1-Wire Gateway 10 Modbus RTU](https://esera.de/en/Produkte/11324/1-Wire-Gateway-10-Modbus-RTU): [manual](../RS485/datasheets/Esera_ModbusGateway10_Manual.pdf), [wiring](../RS485/datasheets/Esera_ModbusGateway10_Wiring.pdf), [software](https://download.esera.de/download/technical/config%20tool%203)

### **Modbus configuration**
The Esera gateways & controllers use a fixed communication baudrate of 19200 with a 8N1 bit configuration making it a dominant slave device in terms of configuration. Make sure any other Modbus devices on the network are able to leverage the same settigs.

The slave id of the gateway is configurable by setting the controller number in the Esera configuration tool.

### **OWD**
The gateway exposes 30 so called "OWD's" (One Wire Devices). The Esera configtool allows assigning a specific and static OWD number to a sensor. This allows the user to create a sensormap, for example: 'OWD1: temperature sensor living room'.

Programmatically each OWD is represented by a [FB_RS485_ESERA_OWD_MQTT](FB_RS485_ESERA_OWD_MQTT.md) function block where the sensor data is processed to.

The following 1-Wire devices are currently supported:

| Device | Devicecode | exports | link |
|:-------------|:------------------|:------------------|:------------------|
| Maxim integrated DS1820 & DS18B20  | 1820 | temperature | [link](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf)
| Esera multisensor Pro 1 | 11151 | air quality, humidity, temperature | [link](https://esera.de/en/Produkte/11151/1-Wire-Multisensor-Air-Quality-Humidity-and-Temperature-Pro-I)
| Esera multisensor Pro 2  | 11152 | air quality, humidity, temperature | [link](https://esera.de/en/Produkte/11152/1-Wire-Multisensor-Air-Quality-Humidity-and-Temperature-Sensor-Pro-II)
| Esera temperature sensor living space Pro | 11148 | humidity, temperature | [link](https://esera.de/en/Produkte/11148/1-Wire-temperature-sensor-living-space-Pro)
| Esera MSP 105 multisensor Pro Air Humidity and Temperature Sensor   | 11150 | humidity, temperature | [link](https://esera.de/en/Produkte/11150/MSP-105-1-Wire-Multisensor-Pro-Air-Humidity-and-Temperature-Sensor)
| Esera multisensor Pro temperature, humidity living room flush-mounted for Berker, Jung, Merten | 11160 | humidity, temperature | [link](https://esera.de/en/Produkte/11160.3/1-Wire-Multisensor-Pro-temperature-humidity-living-room-flush-mounted-for-Berker-Jung-Merten)
| Esera MS105 multisensor temperature, humidity living room flush-mounted for Berker, Jung, Merten | 11132 | humidity, temperature, brightness | [link](https://esera.de/en/Produkte/11132.3/MS105-1-Wire-Multisensor-temperature-humidity-living-room-flush-mounted-for-Berker-Jung-Merten-Kopie)
| Esera multisensor for temperature, humidity, brightness, indoor, surface  | 11134 | humidity, temperature, brightness | [link](https://esera.de/en/Produkte/11134/1-Wire-multi-sensor-for-temperature-humidity-brightness-indoor-surface)


Note that the Esera documents the full list of supported devices over here: [link](https://esera.de/en/Produkte/11324/1-Wire-Gateway-10-Modbus-RTU). Yet, only the devices are above are supported in the software due to lack of actual testing devices.
Nevertheless, adding a new device is a simple task, feel free to reach out.

### **Block diagram**

<img src="../_img/FB_RS485_ESERA_OWD_MQTT.svg" width="350">

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **sensor data is received**   | temperature, humidity, etc readings received. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix and the function block name, the OWD number and a unique sensor value. For example:

`Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/TEMP`

Naturally `/TEMP` will only be omitted by the OWD if the physical sensor exposes it.

| output       | MQTT topc suffic | Unit         | 
|:-------------|:------------------|:------------------|
| TEMPERATURE | `/TEMP` | °C 
| HUMIDITY | `/HUM` | % 
| OWD_VOLTAGE |  `/OWDV` | V 
| AIR_QUALITY | `/AIRQ` | ppm 
| DEW_POINT | `/DEWP` | °C 
| BRIGHTNESS | `/BNESS` | Lux

### **Code example**

- Define the function block in RS485 variables (Modbus address 2, OWD 1, polling interval 30 seconds)
```
FB_RS485_1WIRE_MULTISENSOR_01 			: FB_RS485_ESERA_OWD_MQTT(2, 1, T#30S);
```

- In RS485_Init, register the device to the RS485 buscontroller:
```
RS485BusController.RegisterDevice(device := RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01);
```

- In RS485_Init, initialize MQTT configuration for the function block:
```
RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01.InitMqtt(	
	MQTTPublishPrefix:= ADR(MqttVariables.MqttPubRS485Prefix),	
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue)
);
RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01.InitMqttDiscovery(
	Device := ADR(MqttVariables.OWD_MULTISENSOR_01),
	ParentDevice:= ADR(MqttVariables.PLC_Device),
	DeviceName := '1-Wire sensorhub Garage',
	SupportsTemperature := TRUE,
	SupportsHumidity := TRUE,
	SupportsDewPoint := TRUE,
	SupportsOwdVoltage := TRUE);
```

- In RS485_Run, call the function block so it can do its work:
```
RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01();
```

### **Home Assistant YAML**
If [MQTT discovery](../AdditionalFunctionality/MQTT_Discovery.md) is not working for you, you can use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config. Adopt where necessary depending on the exposed values of your OWD.

```YAML

mqtt:
  sensor:
  - name: "temperature kitchen"
    object_id: "kitchen_temp"
    state_topic: "Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/TEMP"
    unit_of_measurement: "°C"
    qos: 2
    availability:
      - topic: "Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/availability"
      - topic: "Devices/PLC/House/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
```