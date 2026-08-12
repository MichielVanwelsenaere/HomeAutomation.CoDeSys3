## FB_RS485_EASTRON_SDM_POWER_MQTT
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
Used to process Modbus RTU data received over RS485 into human-understandable values and publish data updates through MQTT if desired.
This function block aims to read power consumption from a range of Eastron SDM power meters. Currently the Eastron SDM120, SDM220 and SDM630 are supported.

Eastron SDM120 datasheets:
- [Manual](../RS485/datasheets/SDM120_Manual.pdf)
- [Modbus registers](../RS485/datasheets/SDM120_Modbus_Registers.pdf)

Eastron SDM220 datasheets:
- [Manual](../RS485/datasheets/SDM220_Manual.pdf)
- [Modbus registers](../RS485/datasheets/SDM220_Modbus_Registers.pdf)

Eastron SDM630 datasheet:
- [Manual and Modbus registers](../RS485/datasheets/SDM630-Modbus-V2.pdf)

----------------------------

:rotating_light: **Untested since the CODESYS conversion.** The RS485 chain has not yet been run against real hardware on a CODESYS runtime — see [Using Modbus RTU with the CODESYS 3S runtime](../RS485/UsingModbusRTU_CODESYS3S.md).

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌─────────────────────────────────┐
   │ FB_RS485_EASTRON_SDM_POWER_MQTT │
   ├─────────────────────────────────┤
   │                     ACTIVEPOWER ├── REAL
   │                   DataAvailable ├── BOOL
   │                           Error ├── BOOL
   └─────────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `ACTIVEPOWER` | REAL | Datatype real. |
| `DataAvailable` | BOOL | Datatype bool, high when data is available read by Modbus read command. This means the output is only low on startup until Modbus read command has been executed successfully. |
| `Error` | BOOL | Datatype bool, high when an error occurred while executing Modbus read command. |

### **Methods**

**`GetRtuQuery`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitRS485`** — Configures the Modbus RTU device address and the execution/polling interval for the Modbus read command.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DataPollingInterval` | TIME |  | How often this block polls the device. |
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `DeviceType` | RS485_EASTRON_SDM_Devices |  | Which Eastron SDM model is connected, from `RS485_EASTRON_SDM_Devices`. |

**`ProcessDataArray`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Error` | POINTER TO BOOL |  | Datatype bool, high when an error occurred while executing Modbus read command. |
| `Data` | POINTER TO ARRAY [0..124] OF WORD |  | Pointer to the response data returned by the RTU query. |

**`RequestBusTime`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix, the function block name and a unique value:

| output       | MQTT topic suffix | Unit         |
|:-------------|:------------------|:------------------|
| ACTIVEPOWER |  `/ACTP` | Watts

### **Code example**

- variables initiation:
```
MQTTPubRS485Prefix                :STRING(100) := 'Devices/PLC/Lab/Out/RS485/';
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
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001` (MQTTPubSwitchPrefix variable + function block name).

- Registering device to a bus controller (called once during startup):
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
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001/ACTP"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM_POWER_001/availability"
      - topic: "Devices/PLC/Lab/availability"
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
