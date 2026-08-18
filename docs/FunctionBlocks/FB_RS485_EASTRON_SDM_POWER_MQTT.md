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

:rotating_light: **Compile-verified only.** No SDM120 or SDM630 has been on a bench with a CODESYS runtime, so the register decoding here has not been checked against a real meter — unlike [FB_RS485_EASTRON_SDM220_MQTT](FB_RS485_EASTRON_SDM220_MQTT.md), which has. The bus underneath it is verified; this block's own register map is not.

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

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO RS485_StepList |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

**`HasWork`** — Asked by the bus controller whether this device wants the bus, and how badly: `NONE`, `POLL`, or `COMMAND` for something a person or Home Assistant is waiting on. Must be free of side effects - it is called on every device, twice per cycle.

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

**`OnStepResult`** — Called once per executed step, in order, while the bus is still held. A step skipped by an `AbortOnError` predecessor is never reported.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `StepIndex` | INT |  | Which step of the transaction this answers, indexed as `BuildTransaction` filled them. |
| `Failed` | BOOL |  | No reply, a bad frame, or a Modbus exception. `pData` holds nothing meaningful. |
| `pData` | POINTER TO RS485_ReadBuffer |  | Registers returned by a read step, big-endian, index 0 being the first register requested. |
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
