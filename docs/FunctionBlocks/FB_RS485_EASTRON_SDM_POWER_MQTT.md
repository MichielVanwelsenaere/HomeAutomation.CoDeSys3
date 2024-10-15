## FB_RS485_EASTRON_SDM_POWER_MQTT

### **General**
Used to process Modbus RTU data through RS485 to human understandable values and publish data updates through MQTT if desired.
This function block aims to read power consumption from a range of Eastron SDM power meters. Currently the Eastron SDM120, SDM220 and SDM630 are supported.

Eastron SDM120 datasheets:
- [Manual](../RS485/datasheets/SDM120_Manual.pdf)
- [Modbus registers](../RS485/datasheets/SDM120_Modbus_Registers.pdf)

Eastron SDM220 datasheets:
- [Manual](../RS485/datasheets/SDM220_Manual.pdf)
- [Modbus registers](../RS485/datasheets/SDM220_Modbus_Registers.pdf)

Eastron SDM630 datasheet:
- [Manual and Modbus registers](../RS485/datasheets/SDM630-Modbus-V2.pdf)

### **Block diagram**

<img src="../_img/FB_RS485_EASTRON_SDM_POWER_MQTT.svg" width="500">

OUTPUT(S):
- ACTIVEPOWER: datatype real.
- DataAvailable: datatype bool, high when data is available read by modbus read commando. This means the output is only low on startup until modbus read commando has been executed successfully.
- Error: datatype bool, high when an error occured while executing modbus read commando.

METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name.  
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.     
    - `pMqttCallbackCollector`: datatype _POINTER TO MQTT.CallbackCollector, pointer to the MQTT callback collector to receive subscribe messages.
- InitRS485: configures the Modbus RTU device address and the execution/polling interval for the modbus read command.
- RequestBusTime: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
- GetRtuQuery: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
- ProcessDataArray: method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatination of the publish prefix and the function block name and a unique value: 
| output       | MQTT topc suffic | Unit         | 
|:-------------|:------------------|:------------------|
| ACTIVEPOWER |  `/ACTP` | Watts

### **Code example**

- variables initiation:
```
MQTTPubRS485Prefix                :STRING(100) := 'Devices/PLC/House/Out/RS485/';
FB_RS485_EASTRON_SDM_POWER_001    :FB_RS485_EASTRON_SDM_POWER_MQTT;
```

- Init RS485 method call (called once during startup):
```
FB_RS485_EASTRON_SDM_POWER_001.InitRS485(
	DataPollingInterval := T#15S,                     (* Polling interval for data array *)			
	DeviceAddress := 1,                               (* Device address of the modbus device *)
	DeviceType := RS485_EASTRON_SDM_Devices.SDM630    (* Type of Eastron SDM device *)
);
```

- Init MQTT method call (called once during startup):
```
FB_RS485_EASTRON_SDM_POWER_001.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttRS485Prefix),                       (* pointer to string prefix for the mqtt publish topic *)
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue)      (* pointer to MqttPublishQueue to send a new Mqtt event *)
);

```
The MQTT publish topic in this code example will be `Devices/PLC/House/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001` (MQTTPubSwitchPrefix variable + function block name).

- Registering device to a buscontroller (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_EASTRON_SDM_POWER_001);
```

### **Home Assistant YAML**
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config:

```YAML
mqtt:
  sensor:
  - name: "car charger power"
    object_id: "car_charger_power"
    state_topic: "Devices/PLC/House/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001/ACTP"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    qos: 2
    availability:
      - topic: "Devices/PLC/House/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001/availability"
      - topic: "Devices/PLC/House/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
```

In addition to the above a [Riemann sum integral](https://www.home-assistant.io/integrations/integration/) integration can be added to calculate the energy (kWh) from the power (W):
```YAML
- platform: integration
  source: sensor.car_charger_power
  name: "car charger energy"
  unit_prefix: k
  round: 3
```