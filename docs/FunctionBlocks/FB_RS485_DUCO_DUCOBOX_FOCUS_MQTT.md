## FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Used to process Modbus RTU data received over RS485 into human-understandable values and publish data updates through MQTT if desired. Allows fine-grained local control of your DucoBox.

----------------------------

:rotating_light: **The read-back uses function 3.** A write is paired with a read of the same register, so what gets published is what the device actually holds rather than what it was told. If a Ducobox mirrors those registers into the input register space instead, the read-back needs function 4 — a one-line change in `BuildTransaction`.

----------------------------

:rotating_light: In order to leverage this Modbus integration a communication board (part number 0000-4251) is required on the DucoBox.

----------------------------

DUCO DUCOBOX Focus data:
- [Productlink](https://www.duco.eu/uk/products/mechanical-ventilation/ventilation-units/ducobox-focus)
- [Modbus registers](../RS485/datasheets/DUCO_DUCOBOX_Modbus_Registers.pdf)

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌──────────────────────────────────┐
   │ FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT │
   ├──────────────────────────────────┤
   │                      ACTIVEPOWER ├── REAL
   │                    DataAvailable ├── BOOL
   │                            Error ├── BOOL
   └──────────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `ACTIVEPOWER` | REAL | Power consumption reported by the ventilation unit, in W. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |

### **Methods**

**`AnnounceNode`** — Announces one component and the entity set its module type carries. Called from the body, at most one component per cycle, once that component has reported what it is. Not for calling directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `iN` | INT |  | Index into the internal node array, 2..30 — not the Duco node number, which is one higher. |

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO A_RS485_STEP_LIST |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

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
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceName` | STRING(50) |  | Name for the box itself in Home Assistant. Each component is named by the `FriendlyName` its `AddNode` call supplied, not from here. |
| `overruleId` | STRING(255) |  | Overrides the generated entity id. Leave empty to derive it from the function block name. |

**`InitRS485`** — Configures the Modbus RTU device address and the execution/polling interval for the multiple Modbus read commands.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DataPollingInterval` | TIME |  | How often this block polls the device. |
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |

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

**`PubAvailability`** — Publish the device availability, retained. Called from the block's

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Online` | BOOL |  | `TRUE` publishes `online`, `FALSE` publishes `offline`. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

Read parameter 0 of every node is its module type, and it decides what the other
registers mean. The block resolves it on each read and publishes the values under
the names that type gives them, scaled, so nothing downstream needs a template.

The topic is the publish prefix, the instance name, the node number, then the
quantity:

`Devices/PLC/Lab/Out/RS485/<instance>/<node>/TEMP`

| Suffix | Nodes that publish it | Payload |
|:--|:--|:--|
| `/TYPE` | every node | the component in words, e.g. `CO2 valve` |
| `/STATUS` | every node except a box sensor | `Auto`, `Manual low`, `Unoccupied`, `Error`, … |
| `/POS` | the box, valves, user control, switch sensor, actuator board | ventilation position, % |
| `/OPEN` | window ventilator | opening, % — 0 shut, 100 open |
| `/TEMP` | valves, user control, room sensors | indoor temperature, °C |
| `/TEMP_OUT` | window ventilator, actuator board | outdoor temperature, °C |
| `/CO2` | CO2 valve, humidity + CO2 valve, CO2 sensor | ppm |
| `/RH` | humidity valve, humidity + CO2 valve, humidity sensor | % |
| `/PWM` | actuator board | PWM duty cycle, % |
| `/PWR`, `/PWR_AVG`, `/PWR_MAX` | the box | current, average and maximum power, W |
| `/ZONE` | every node | the zone grouping, read once |
| `/availability` | the instance | `online` / `offline` |

All are QoS 2, not retained, published on each successful read.

:bulb: **Two registers change meaning with the component.** Read parameter 3 is the
indoor temperature on a valve and the *outdoor* temperature on a window ventilator
and an actuator board; read parameter 4 is CO2 nearly everywhere but a PWM duty
cycle on an actuator board. That is why the type is resolved before anything is
published, and why a node whose type this project does not recognise falls back to
`/read/0`…`/read/5` with no labels rather than guessing.

:bulb: **The zone number is read once, in a step of its own.** Read parameters 6, 7
and 8 are undefined on every component type, and the box answers a span that
crosses them with an exception rather than zeroes — so the six measurements and the
zone number cannot be fetched in one ten-register read. The zone only changes when
the network is re-paired, so it is requested when a node's type is first
established and not polled after that.

### **MQTT subscribe behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **write holding** | Writes an integer value to a specific write register. | `INT` | Only integer values are processed further.

MQTT subscription topic is a concatenation of the subscribe prefix variable, function block name, node number and register number. For example, topic `Devices/PLC/Lab/In/RS485/FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT/1/write/0` with payload `30` will set the 'Target value (%)' parameter for node 1 (which in this case represents the entire system). Go through the DUCO Modbus register documentation linked above for a deeper understanding.

Upon a successful write operation the received payload will be published on the 'Out' topic. Continuing with the example above this will result in a payload `30` to be published on topic `Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT/1/write/0`.

### **Code example**

- variables initiation:
```
MQTTPubRS485Prefix                :STRING(100) := 'Devices/PLC/Lab/Out/RS485/';
FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001    :FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT;
```

- Init RS485 method call (called once during startup):
```
FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001.InitRS485(
	DataPollingInterval := T#20S,       (* Polling interval *)		
	DeviceAddress := 1                  (* Device address of the modbus device *)			
);
```

- Init MQTT method call (called once during startup):
```
FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttRS485Prefix),                       (* pointer to string prefix for the mqtt publish topic *)
	pMqttPublishQueue := ADR(GVL_MQTT.fbMqttPublishQueue)      (* pointer to MqttPublishQueue to send a new Mqtt event *)
);

```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/RS485/FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001` (MQTTPubSwitchPrefix variable + function block name).

- Adding the components on the network (called once during startup, after
  `InitRS485`). The name is the room; what the component *is* is read off the bus,
  so a valve swapped for a sensor needs no change here:
```
FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001.AddNode(
	FriendlyName := 'Kitchen',
	DataPollingInterval := T#15S
);
```

- Registering device to a bus controller (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_DUCO_DUCOBOX_FOCUS_MQTT_001);
```

### **Home Assistant**

Nothing to configure. Call `InitMqttDiscovery` once at startup and the box
announces itself, then each component as the bus reports what it is. Every
component becomes a device of its own named by the `FriendlyName` its `AddNode`
call supplied, carrying the sensors its module type has and a number, switch or
button for every write parameter that type defines.

The component set is discovered, not declared: a valve replaced by a sensor
re-announces as a sensor on its next read, with no change here.
