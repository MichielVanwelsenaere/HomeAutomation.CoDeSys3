## FB_RS485_EASTRON_SDM220_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Used to process Modbus RTU data received over RS485 into human-understandable values and publish data updates through MQTT if desired.
Due to the large number of Modbus registers exposed and the Eastron SDM220 limitation of reading at most 40 registers at once, the function block requires three Modbus read commands to read out all the available data. Each of these three Modbus read commands reads out multiple registers at once, which guarantees a consistent data readout as datapoints are extracted at a single point in time.

----------------------------

:rotating_light: Several users have reported that the 'kWh' measurement readings of the Eastron SDM meters are unreliable. Specifically, there are huge spikes containing faulty values in the data retrieved.

----------------------------

Eastron SDM220 datasheets:
- [Manual](../RS485/datasheets/SDM220_Manual.pdf)
- [Modbus registers](../RS485/datasheets/SDM220_Modbus_Registers.pdf)

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌──────────────────────────────┐
   │ FB_RS485_EASTRON_SDM220_MQTT │
   ├──────────────────────────────┤
   │                      VOLTAGE ├── REAL
   │                      CURRENT ├── REAL
   │                  ACTIVEPOWER ├── REAL
   │               APPARENT_POWER ├── REAL
   │               REACTIVE_POWER ├── REAL
   │                 POWER_FACTOR ├── REAL
   │                  PHASE_ANGLE ├── REAL
   │               DataAvailable1 ├── BOOL
   │                       Error1 ├── BOOL
   │                    FREQUENCY ├── REAL
   │         IMPORT_ACTIVE_ENERGY ├── REAL
   │         EXPORT_ACTIVE_ENERGY ├── REAL
   │       IMPORT_REACTIVE_ENERGY ├── REAL
   │       EXPORT_REACTIVE_ENERGY ├── REAL
   │               DataAvailable2 ├── BOOL
   │                       Error2 ├── BOOL
   │          TOTAL_ACTIVE_ENERGY ├── REAL
   │        TOTAL_REACTIVE_ENERGY ├── REAL
   │               DataAvailable3 ├── BOOL
   │                       Error3 ├── BOOL
   └──────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `VOLTAGE` | REAL | Datatype real, part of Modbus read command 1. |
| `CURRENT` | REAL | Datatype real, part of Modbus read command 1. |
| `ACTIVEPOWER` | REAL | Datatype real, part of Modbus read command 1. |
| `APPARENT_POWER` | REAL | Datatype real, part of Modbus read command 1. |
| `REACTIVE_POWER` | REAL | Datatype real, part of Modbus read command 1. |
| `POWER_FACTOR` | REAL | Datatype real, part of Modbus read command 1. |
| `PHASE_ANGLE` | REAL | Datatype real, part of Modbus read command 1. |
| `DataAvailable1` | BOOL | Datatype bool, high when data is available read by Modbus read command 1. This means the output is only low on startup until Modbus read command 1 has been executed successfully. |
| `Error1` | BOOL | Datatype bool, high when an error occurred while executing Modbus read command 1. |
| `FREQUENCY` | REAL | Datatype real, part of Modbus read command 2. |
| `IMPORT_ACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 2. |
| `EXPORT_ACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 2. |
| `IMPORT_REACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 2. |
| `EXPORT_REACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 2. |
| `DataAvailable2` | BOOL | Datatype bool, high when data is available read by Modbus read command 2. This means the output is only low on startup until Modbus read command 2 has been executed successfully. |
| `Error2` | BOOL | Datatype bool, high when an error occurred while executing Modbus read command 2. |
| `TOTAL_ACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 3. |
| `TOTAL_REACTIVE_ENERGY` | REAL | Datatype real, part of Modbus read command 3. |
| `DataAvailable3` | BOOL | Datatype bool, high when data is available read by Modbus read command 3. This means the output is only low on startup until Modbus read command 3 has been executed successfully. |
| `Error3` | BOOL | Datatype bool, high when an error occurred while executing Modbus read command 3. |

### **Methods**

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO A_RS485_STEP_LIST |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
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
| `Device` | POINTER TO FB_EASTRON_SDM_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `DeviceName` | STRING(50) |  | Name of that Home Assistant device. The self-wiring prologue passes `FriendlyName`. |
| `Model` | STRING(20) | `'SDM220'` | Model shown on the Home Assistant device page. This block reads the SDM220 register map, so the default is right unless you are pointing it at a meter that shares that map. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |

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

Set `FriendlyName` at the declaration and the block wires itself; see the code example
below. Calling `InitMqtt` explicitly still works and is what an older call site does.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix, the function block name and a unique value:

| output       | MQTT topic suffix | Unit         |
|:-------------|:------------------|:------------------|
| VOLTAGE | `/VOLT` | Volts 
| CURRENT | `/CURR` | Amps 
| ACTIVEPOWER |  `/ACTP` | Watts 
| APPARENT_POWER | `/APPP` | VoltAmps 
| REACTIVE_POWER | `/REAP` | VAr 
| POWER_FACTOR | `/POWF` | None 
| PHASE_ANGLE | `/PHAA` | Degree 
| FREQUENCY | `/FREQ` | Hz 
| IMPORT_ACTIVE_ENERGY | `/IMAE` | kwh 
| EXPORT_ACTIVE_ENERGY | `/EXAE` | kwh 
| IMPORT_REACTIVE_ENERGY | `/IMRE` | kvarh 
| EXPORT_REACTIVE_ENERGY | `/EXRE` | kvarh 
| TOTAL_ACTIVE_ENERGY | `/TOTAE` | kwh 
| TOTAL_REACTIVE_ENERGY | `/TOTRE` | kvarh 

### **Code example**

The declaration is the whole configuration — Modbus address and polling interval through
`FB_init`, the Home Assistant name through the initialiser:

```
FB_RS485_EASTRON_SDM220_001 : FB_RS485_EASTRON_SDM220_MQTT(1, T#5S)
                            := (FriendlyName := 'Garage energy meter');
```

Register it with the bus controller once at startup, in `RS485_INIT`:

```
RS485BusController.RegisterDevice(device := GVL_RS485.FB_RS485_EASTRON_SDM220_001);
```

and call it cyclically, in `RS485_RUN`:

```
GVL_RS485.FB_RS485_EASTRON_SDM220_001();
```

That is all of it. No `InitRS485`, no `InitMqtt`, no `InitMqttDiscovery`: the block wires itself
from `GVL_MQTT` on its first cyclic call. The publish topic becomes
`Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM220_001` — the `MqttPubRS485Prefix` plus the
instance name. **A block wired this way must be called cyclically** — an instance whose body
never runs stays unwired and never appears in Home Assistant, and nothing warns about it.

:bulb: **One interval, three reads.** The SDM220 will not return more than 40 registers in a
reply and its measurements are not in one contiguous run, so reading it takes three requests.
That is a property of the meter, not a decision worth passing to a caller, so there is a single
`DataPollingInterval` — the three requests go out together as one transaction and cost one turn
of the bus, not three. The block used to take three separate intervals; nothing was gained by it.

### **Wago PFC wiring diagram**
Wire the device as below in order to establish communication between a Wago PFC device and an Eastron SDM220:

<img src="../_img/FB_RS485_EASTRON_SDM220_MQTT_WiringDiagram.png" width="500">

Note: RS485 terminator resistors are not shown in the image but are nevertheless required.

### **Home Assistant**

The block publishes its own discovery configs, so no YAML is needed. It announces the meter
as a device of its own — manufacturer `Eastron`, model from the `Model` parameter — with all
fourteen measurements as entities underneath it, rather than adding fourteen entities to the
PLC device.

| Entity | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|
| Voltage | `voltage` | `measurement` | V |
| Current | `current` | `measurement` | A |
| Active Power | `power` | `measurement` | W |
| Apparent Power | `apparent_power` | `measurement` | VA |
| Reactive Power | `reactive_power` | `measurement` | var |
| Power Factor | `power_factor` | — | — |
| Phase Angle | — | — | ° |
| Frequency | `frequency` | `measurement` | Hz |
| Import Active Energy | `energy` | `total_increasing` | kWh |
| Export Active Energy | `energy` | `total_increasing` | kWh |
| Import Reactive Energy | `reactive_energy` | `total_increasing` | kvarh |
| Export Reactive Energy | `reactive_energy` | `total_increasing` | kvarh |
| Total Active Energy | `energy` | `total_increasing` | kWh |
| Total Reactive Energy | `reactive_energy` | `total_increasing` | kvarh |

`state_class: total_increasing` on the three kWh counters is what makes them selectable in the
**energy dashboard**. Power factor and phase angle carry no state class, because neither is
meaningful to sum or average over time.

:rotating_light: **The three kvarh counters need Home Assistant 2025.9 or newer.** They carry
`device_class: reactive_energy`, which is a recent addition. An older Home Assistant does not
merely ignore a device class it does not know — it **rejects the whole discovery config**, so
those three entities would not appear at all. The symptom is a missing entity rather than a
wrong one, which is worth knowing because nothing on the PLC side looks any different. On an
older install, set `DeviceClass := ''` on those three `CreateSensorEntity` calls; the entities
come back with their units and their statistics, just without the classification.
