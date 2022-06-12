## FB_RS485_ESERA_1WIRE_GATEWAY_MQTT

### __General__
Designed to communicate with [Esera](https://esera.de/) 1-Wire modbus gateway this functionality allows pulling data from an extensive 1-Wire network in the PLC and publish updates through MQTT if desired.

Esera supports and produces a wide range of 1-Wire devices; indoor/outdoor temperature sensors, humidity sensors, brightness sensors, air quality sensors, etc.

Required hardware:

[1-Wire Gateway 10 Modbus RTU](https://esera.de/shop/en/Service-Support/1-Wire-Basics/1-Wire-building-blocks/414/1-Wire-Gateway-10-Modbus-RTU): [manual](../RS485/datasheets/Esera_ModbusGateway10_Manual.pdf), [wiring](../RS485/datasheets/Esera_ModbusGateway10_Wiring.pdf), [software](https://download.esera.de/download/technical/config%20tool%203)

### __Modbus configuration__
The Esera gateways & controllers use a fixed communication baudrate of 19200 with a 8N1 bit configuration making it a dominant slave device in terms of configuration. Make sure any other Modbus devices on the network are able to leverage the same settigs.

The slave id of the gateway is configurable by setting the controller number in the Esera configuration tool.

### __OWD__
The gateway exposes 30 so called "OWD's" (One Wire Devices). The Esera configtool allows assigning a specific and static OWD number to a sensor. This allows the user to create a sensormap, for example: 'OWD1: temperature sensor living room'.

Programmatically each OWD is represented by a [FB_RS485_ESERA_OWD_MQTT](FB_RS485_ESERA_OWD_MQTT.md) function block where the sensor data is processed to.

### __Code example__

- variables initiation:
```
MqttRS485Prefix							: STRING(100) := 'Devices/PLC/Home/Out/RS485/';	
FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME	: FB_RS485_ESERA_1WIRE_GATEWAY_MQTT;
```

- Init RS485 method call (called once during startup):
```
FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HUIS.InitRS485(
	DeviceAddress := 2
);
```

- Init MQTT method call (called once during startup):
```
FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttRS485Prefix),	
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue)
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Home/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME` (MQTTPubSwitchPrefix variable + function block name).

- Registering device to a buscontroller (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME);
```
