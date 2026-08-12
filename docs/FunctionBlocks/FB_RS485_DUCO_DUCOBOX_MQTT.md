## FB_RS485_DUCO_DUCOBOX_MQTT
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
Used to process Modbus RTU data received over RS485 into human-understandable values and publish data updates through MQTT if desired. Allows fine-grained local control of your DucoBox.

----------------------------

:rotating_light: **Untested since the CODESYS conversion.** The RS485 chain has not yet been run against real hardware on a CODESYS runtime — see [Using Modbus RTU with the CODESYS 3S runtime](../RS485/UsingModbusRTU_CODESYS3S.md).

----------------------------

:rotating_light: In order to leverage this Modbus integration a communication board (part number 0000-4251) is required on the DucoBox.

----------------------------

DUCO DUCOBOX Focus data:
- [Productlink](https://www.duco.eu/uk/products/mechanical-ventilation/ventilation-units/ducobox-focus)
- [Modbus registers](../RS485/datasheets/DUCO_DUCOBOX_Modbus_Registers.pdf)

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌────────────────────────────┐
   │ FB_RS485_DUCO_DUCOBOX_MQTT │
   ├────────────────────────────┤
   │                ACTIVEPOWER ├── REAL
   │              DataAvailable ├── BOOL
   │                      Error ├── BOOL
   └────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `ACTIVEPOWER` | REAL | Power consumption reported by the ventilation unit, in W. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |

### **Methods**

**`GetRtuQuery`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`InitRS485`** — Configures the Modbus RTU device address and the execution/polling interval for the multiple Modbus read commands.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DataPollingInterval` | TIME |  | How often this block polls the device. |
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |

**`ProcessDataArray`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Error` | POINTER TO BOOL |  | Pointer to the bus error flag for the RTU query. |
| `Data` | POINTER TO ARRAY [0..124] OF WORD |  | Pointer to the response data returned by the RTU query. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |

**`RequestBusTime`** — Method implemented by each RS485 device function block. More information in the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **register is polled**   | a Modbus register is polled | int value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix, the function block name, the node number and a register number. For example:

`Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/1/read/0`

Depending on the type of the node the published register value represents a certain parameter value. 

### **MQTT subscribe behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **write holding** | Writes an integer value to a specific write register. | `INT` | Only integer values are processed further.

MQTT subscription topic is a concatenation of the subscribe prefix variable, function block name, node number and register number. For example, topic `Devices/PLC/Lab/In/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/1/write/0` with payload `30` will set the 'Target value (%)' parameter for node 1 (which in this case represents the entire system). Go through the DUCO Modbus register documentation linked above for a deeper understanding.

Upon a successful write operation the received payload will be published on the 'Out' topic. Continuing with the example above this will result in a payload `30` to be published on topic `Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT/1/write/0`.

### **Code example**

- variables initiation:
```
MQTTPubRS485Prefix                :STRING(100) := 'Devices/PLC/Lab/Out/RS485/';
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
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001` (MQTTPubSwitchPrefix variable + function block name).

- Registering device to a bus controller (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_DUCO_DUCOBOX_MQTT_001);
```

### **Home Assistant YAML**
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config.

Main node:

```YAML
mqtt:
  sensor:
  - name: "Ventilation Status"
    object_id: "ventilation_1_1"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/1/read/1"
    value_template: >-
          {% set val = value | float(0) %}
          {% if val == 0 %} Auto
          {% elif val == 1 %} 10 minutes high
          {% elif val == 2 %} 20 minutes high
          {% elif val == 3 %} 30 minutes high
          {% elif val == 4 %} Manual low
          {% elif val == 5 %} Manual medium
          {% elif val == 6 %} Manual high
          {% elif val == 7 %} Unoccupied
          {% elif val == 99 %} Error
          {% else %} Unknown
          {% endif %}
    icon: "mdi:state-machine"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
  - name: "Ventilation Pos"
    object_id: "Ventilation_1_2"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/1/read/2"
    unit_of_measurement: "%"
    icon: "mdi:valve"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
  - name: "Ventilation Power"
    object_id: "ventilation_1_3"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/1/read/3"
    unit_of_measurement: "W"
    device_class: "power"
    state_class: "measurement"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
```

Additional nodes (for example valves):

```YAML
mqtt:
  sensor:
  - name: "Ventilation Node 2 Status"
    object_id: "ventilation_2_1"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/read/1"
    value_template: >-
          {% set val = value | float(0) %}
          {% if val == 0 %} Auto
          {% elif val == 1 %} 10 minutes high
          {% elif val == 2 %} 20 minutes high
          {% elif val == 3 %} 30 minutes high
          {% elif val == 4 %} Manual low
          {% elif val == 5 %} Manual medium
          {% elif val == 6 %} Manual high
          {% elif val == 7 %} Unoccupied
          {% elif val == 99 %} Error
          {% else %} Unknown
          {% endif %}
    icon: "mdi:state-machine"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
  - name: "Ventilation Node 2 Pos"
    object_id: "ventilation_2_2"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/read/2"
    unit_of_measurement: "%"
    icon: "mdi:valve"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
  - name: "Ventilation Node 2 Temp"
    object_id: "ventilation_2_3"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/read/3"
    value_template: "{{ value | multiply(0.10) | round(2) }}" 
    unit_of_measurement: "°C"
    device_class: "temperature"
    state_class: "measurement"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
  - name: "Ventilation Node 2 CO2"
    object_id: "Ventilation_2_4"
    state_topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/read/4"
    unit_of_measurement: "µg/m³"
    device_class: "PM25"
    state_class: "measurement"
    qos: 2
    availability:
      - topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
      - topic: "Devices/PLC/Lab/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
```

Writing registers (for example action on valves):

```YAML
mqtt:
  button:
  - object_id: "ventilation_2_write_9_15high"
	name: "Ventilation Kitchen 15 min high"
	command_topic: "Devices/PLC/Lab/In/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/write/9"
	payload_press: "4"
	availability:
	- topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
	- topic: "Devices/PLC/Lab/availability"
	availability_mode : "all"
	payload_available: "online"
	payload_not_available: "offline"
	entity_category: "config"
  - object_id: "ventilation_2_write_9_Auto"
	name: "Ventilation Kitchen auto"
	command_topic: "Devices/PLC/Lab/In/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/2/write/9"
	payload_press: "5"
	availability:
	- topic: "Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_MQTT_001/availability"
	- topic: "Devices/PLC/Lab/availability"
	availability_mode : "all"
	payload_available: "online"
	payload_not_available: "offline"
	entity_category: "config"
```
