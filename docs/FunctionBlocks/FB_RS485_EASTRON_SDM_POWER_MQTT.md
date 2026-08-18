## FB_RS485_EASTRON_SDM_POWER_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
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

:white_check_mark: **The SDM220 branch is verified on hardware.** Pointed at a real SDM220 it read active power from register 30013 and agreed, reading for reading, with [FB_RS485_EASTRON_SDM220_MQTT](FB_RS485_EASTRON_SDM220_MQTT.md) reading the same register of the same meter.

:rotating_light: **The SDM120 and SDM630 branches are compile-verified only.** Neither meter has been on a bench with a CODESYS runtime. The SDM120 shares the SDM220's register (`30013`) so it is likely right; the SDM630 uses a different one (`30053`) and nothing has checked it.

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

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_EASTRON_SDM_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `DeviceName` | STRING(50) |  | Name of that Home Assistant device. The self-wiring prologue passes `FriendlyName`. |
| `Model` | STRING(20) | `''` | Model shown on the Home Assistant device page. Empty means derive it from `DeviceType`, which is what the self-wiring prologue relies on; pass a string to overrule that. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |

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

Set `FriendlyName` at the declaration and the block wires itself; see the code example
below. Calling `InitMqtt` explicitly still works and is what an older call site does.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **output is updated**   | the output is updated. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatenation of the publish prefix, the function block name and a unique value:

| output       | MQTT topic suffix | Unit         |
|:-------------|:------------------|:------------------|
| ACTIVEPOWER |  `/ACTP` | Watts

### **Code example**

`FriendlyName` is what turns the MQTT and Home Assistant wiring on:

```
FB_RS485_EASTRON_SDM_POWER_001 : FB_RS485_EASTRON_SDM_POWER_MQTT
                               := (FriendlyName := 'Car charger');
```

`InitRS485` carries the address, the poll rate and — unlike the other two Eastron blocks —
**which meter this is**, because one block serves the whole family and the register it reads
depends on the answer. Put it in `RS485_INIT` with the registration:

```
RS485Variables.FB_RS485_EASTRON_SDM_POWER_001.InitRS485(
	DataPollingInterval := T#15S,
	DeviceAddress := 1,
	DeviceType := RS485_EASTRON_SDM_Devices.SDM630
);

RS485BusController.RegisterDevice(device := RS485Variables.FB_RS485_EASTRON_SDM_POWER_001);
```

and call it cyclically, in `RS485_RUN`:

```
RS485Variables.FB_RS485_EASTRON_SDM_POWER_001();
```

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from
`MqttVariables` on its first cyclic call. **A block wired this way must be called cyclically** —
an instance whose body never runs stays unwired and never appears in Home Assistant, and nothing
warns about it.

:bulb: **Discovery waits for `InitRS485`, not just for a name.** The model this meter announces
itself as is derived from `DeviceType`, so the prologue holds off until `InitRS485` has run.
Give it a `FriendlyName` and no `InitRS485` and it will publish its topics but never announce
itself — which is the same state it would be in if it had no address to poll either.

### **Home Assistant**

The block publishes its own discovery config, so no YAML is needed. It announces the meter as a
device of its own — manufacturer `Eastron`, model from `DeviceType` — carrying a single entity:

| Entity | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|
| Active Power | `power` | `measurement` | W |

`state_class: measurement` means Home Assistant keeps short-term statistics but no energy total,
because this block reads power and not energy. To get kWh out of it, add a
[Riemann sum integral](https://www.home-assistant.io/integrations/integration/) on the Home
Assistant side:

```YAML
- platform: integration
  source: sensor.car_charger_active_power
  name: "car charger energy"
  unit_prefix: k
  round: 3
```

If the meter is one whose own energy registers you want instead, use
[FB_RS485_EASTRON_SDM220_MQTT](FB_RS485_EASTRON_SDM220_MQTT.md) or
[FB_RS485_EASTRON_SDM630_MQTT](FB_RS485_EASTRON_SDM630_MQTT.md), which read them directly and
announce them with `state_class: total_increasing` for the energy dashboard.
