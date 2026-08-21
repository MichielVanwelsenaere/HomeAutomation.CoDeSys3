## FB_RS485_ESERA_OWD_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Designed to communicate with the [Esera](https://esera.de/) 1-Wire Modbus gateway, this function block allows pulling data from an extensive 1-Wire network into the PLC and publishing updates through MQTT if desired.

Esera supports and produces a wide range of 1-Wire devices; indoor/outdoor temperature sensors, humidity sensors, brightness sensors, air quality sensors, etc.

Required hardware:

[1-Wire Gateway 10 Modbus RTU](https://esera.de/en/Produkte/11324/1-Wire-Gateway-10-Modbus-RTU): [manual](../RS485/datasheets/Esera_ModbusGateway10_Manual.pdf), [wiring](../RS485/datasheets/Esera_ModbusGateway10_Wiring.pdf), [software](https://download.esera.de/download/technical/config%20tool%203)

### **Modbus configuration**
The Esera gateways & controllers use a fixed communication baud rate of 19200 with an 8N1 bit configuration, making them dominant slave devices in terms of configuration. Make sure any other Modbus devices on the network are able to leverage the same settings.

The slave ID of the gateway is configurable by setting the controller number in the Esera configuration tool.

### **OWD**
The gateway exposes 30 so-called "OWDs" (One Wire Devices). The Esera configuration tool allows assigning a specific and static OWD number to a sensor. This allows the user to create a sensor map, for example: 'OWD1: temperature sensor living room'.

Programmatically each OWD is represented by an [FB_RS485_ESERA_OWD_MQTT](FB_RS485_ESERA_OWD_MQTT.md) function block, which is where the sensor data is processed.

The following 1-Wire devices are currently supported:

<!-- markdown-link-check-disable -->
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
<!-- markdown-link-check-enable -->

Note that Esera documents the full list of supported devices here: [link](https://esera.de/en/Produkte/11324/1-Wire-Gateway-10-Modbus-RTU). Yet only the devices above are supported in the software, due to a lack of actual testing devices.
Nevertheless, adding a new device is a simple task, feel free to reach out.

----------------------------

:rotating_light: **Compile-verified only.** No ESERA gateway has been on a bench with a CODESYS runtime, so the register decoding and the per-sensor model handling here have not been checked against real hardware. The bus underneath it is verified; this block's own register map is not.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌─────────────────────────┐
   │ FB_RS485_ESERA_OWD_MQTT │
   ├─────────────────────────┤
   │             OWD_VOLTAGE ├── REAL
   │             TEMPERATURE ├── REAL
   │                HUMIDITY ├── REAL
   │               DEW_POINT ├── REAL
   │             AIR_QUALITY ├── REAL
   │              BRIGHTNESS ├── REAL
   │           DataAvailable ├── BOOL
   │                   Error ├── BOOL
   └─────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `OWD_VOLTAGE` | REAL | Supply voltage measured at the 1-Wire device, in V. |
| `TEMPERATURE` | REAL | Measured temperature, in °C. |
| `HUMIDITY` | REAL | Measured relative humidity, in %. |
| `DEW_POINT` | REAL | Calculated dew point, in °C. |
| `AIR_QUALITY` | REAL | Measured air quality, in ppm. |
| `BRIGHTNESS` | REAL | Measured brightness, in Lux. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |

### **Methods**

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO A_RS485_STEP_LIST |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `OwdNumber` | UINT |  | The OWD number (1-30) this block reads, as assigned in the Esera configuration tool. |
| `DataPollingInterval` | TIME |  | How often this block polls the device. |

**`GetCommissioning`** — Asked once at startup, by `FB_RS485_COMMISSIONER`, whether this device needs something written into it before it can be spoken to at all - a device that ships on a baud rate the bus does not use, say. Returning FALSE, which is the ordinary case, means there is nothing to do.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `BusBaudrate` | UDINT |  | What the bus runs at, so a device can encode that rate the way its own register expects - and can withdraw if it cannot be told to use it. |
| `pRequest` | POINTER TO ST_RS485_COMMISSION_REQUEST |  | Commissioner-owned scratch to fill when the answer is TRUE: what to probe, which register to write, and the rates worth trying. Only valid for the duration of the call. |

**`HasWork`** — Asked by the bus controller whether this device wants the bus, and how badly: `NONE`, `POLL`, or `COMMAND` for something a person or Home Assistant is waiting on. Must be free of side effects - it is called on every device, twice per cycle.

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_1WIRE_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `ParentDevice` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the PLC discovery device, so the sensor hub appears beneath it in Home Assistant. |
| `DeviceName` | STRING(50) |  | Name shown in Home Assistant for the 1-Wire sensor hub itself. |
| `SupportsTemperature` | BOOL | `FALSE` | Set TRUE if the physical sensor reports temperature, so the entity is created. |
| `SupportsHumidity` | BOOL | `FALSE` | Set TRUE if the physical sensor reports humidity, so the entity is created. |
| `SupportsCO2` | BOOL | `FALSE` | Set TRUE if the physical sensor reports air quality, so the entity is created. |
| `SupportsDewPoint` | BOOL | `FALSE` | Set TRUE if the dew point should be published as an entity. |
| `SupportsBrightness` | BOOL | `FALSE` | Set TRUE if the physical sensor reports brightness, so the entity is created. |
| `SupportsOwdVoltage` | BOOL | `FALSE` | Set TRUE to publish the 1-Wire supply voltage as a diagnostic entity. |

**`OnStepResult`** — Called once per executed step, in order, while the bus is still held. A step skipped by an `AbortOnError` predecessor is never reported.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `StepIndex` | INT |  | Which step of the transaction this answers, indexed as `BuildTransaction` filled them. |
| `Failed` | BOOL |  | No reply, a bad frame, or a Modbus exception. `pData` holds nothing meaningful. |
| `pData` | POINTER TO A_RS485_READ_BUFFER |  | Registers returned by a read step, big-endian, index 0 being the first register requested. |
| `Count` | INT |  | How many registers `pData` actually holds. Trusting this rather than the quantity requested is what stops a short reply being read past the end of. |

**`OnTransactionDone`** — Called once, after the last `OnStepResult`, as the bus is released. The one place to publish `/availability` and clear a pending command.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `StepsRun` | INT |  | Steps actually executed. Fewer than requested means an `AbortOnError` step failed. |
| `Failures` | INT |  | How many of those failed. Zero is the only wholly good outcome. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **sensor data is received**   | temperature, humidity, etc. readings received. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix, the function block name, the OWD number and a unique sensor value. For example:

`Devices/PLC/Lab/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/TEMP`

Naturally `/TEMP` will only be published by the OWD if the physical sensor exposes it.

| output       | MQTT topic suffix | Unit         |
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

- In RS485_Init, register the device to the RS485 bus controller:
```
RS485BusController.RegisterDevice(device := GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01);
```

- In RS485_Init, initialize MQTT configuration for the function block:
```
GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01.InitMqtt(	
	MQTTPublishPrefix:= ADR(GVL_MQTT.MqttPubRS485Prefix),	
	pMqttPublishQueue := ADR(GVL_MQTT.fbMqttPublishQueue)
);
GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01.InitMqttDiscovery(
	Device := ADR(GVL_MQTT.OWD_MULTISENSOR_01),
	ParentDevice:= ADR(GVL_MQTT.PLC_Device),
	DeviceName := '1-Wire sensorhub Garage',
	SupportsTemperature := TRUE,
	SupportsHumidity := TRUE,
	SupportsDewPoint := TRUE,
	SupportsOwdVoltage := TRUE);
```

- In RS485_Run, call the function block so it can do its work:
```
GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01();
```
