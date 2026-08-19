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

:white_check_mark: **The SDM220 branch is verified on hardware, and stays verified.** The reference project registers an instance of this block on the **same meter** as [FB_RS485_EASTRON_SDM220_MQTT](FB_RS485_EASTRON_SDM220_MQTT.md), declared as an `SDM220`. Both decode active power out of register 30013, so the two publish the same number continuously and any drift between them is a real regression in one of them. It is also the only way this block is exercised at all — see [the standing cross-check](#the-standing-cross-check) below.

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

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `DeviceType` | RS485_EASTRON_SDM_Devices |  | Which Eastron SDM model is connected, from `RS485_EASTRON_SDM_Devices`. It decides which register active power is read from — `30013` on the SDM120 and SDM220, `30053` on the SDM630 — and is also the model announced to Home Assistant. |
| `DataPollingInterval` | TIME |  | How often this block polls the device. |

**`GetCommissioning`** — Asked once at startup, by `FB_RS485_COMMISSIONER`, whether this device needs something written into it before it can be spoken to at all - a device that ships on a baud rate the bus does not use, say. Returning FALSE, which is the ordinary case, means there is nothing to do.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `BusBaudrate` | UDINT |  | What the bus runs at, so a device can encode that rate the way its own register expects - and can withdraw if it cannot be told to use it. |
| `pRequest` | POINTER TO RS485_CommissionRequest |  | Commissioner-owned scratch to fill when the answer is TRUE: what to probe, which register to write, and the rates worth trying. Only valid for the duration of the call. |

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

The declaration is the whole configuration. `FB_init` takes the Modbus address, **which meter
this is**, and the poll rate; the initialiser takes the Home Assistant name:

```
FB_RS485_EASTRON_SDM_POWER_001 : FB_RS485_EASTRON_SDM_POWER_MQTT(1, RS485_EASTRON_SDM_Devices.SDM630, T#15S)
                               := (FriendlyName := 'Car charger');
```

`DeviceType` is the parameter the other two Eastron blocks do not need: one block serves the
SDM120, SDM220 and SDM630, and the register it reads depends on the answer — `30013` on the
single-phase meters, `30053` on the SDM630. It is also the model this block announces itself to
Home Assistant as.

Register it with the bus controller once at startup, in `RS485_INIT`:

```
RS485BusController.RegisterDevice(device := RS485Variables.FB_RS485_EASTRON_SDM_POWER_001);
```

and call it cyclically, in `RS485_RUN`:

```
RS485Variables.FB_RS485_EASTRON_SDM_POWER_001();
```

No `InitRS485`, no `InitMqtt`, no `InitMqttDiscovery`: the block wires itself from
`MqttVariables` on its first cyclic call. **A block wired this way must be called cyclically** —
an instance whose body never runs stays unwired and never appears in Home Assistant, and nothing
warns about it.

### **The standing cross-check**

`RS485Variables.FB_RS485_EASTRON_SDM_POWER_1` is wired in `PLC_PRG_RS485` against the lab
SDM220 at address 1 — the same meter `FB_RS485_EASTRON_SDM220_1` reads. That is deliberate
and it is not redundant instrumentation:

- **It is the only call site this block has.** An unreferenced POU is never compiled, so
  without an instance somewhere a broken edit here passes `verify` with a clean build.
- **It gives the decoding a continuous witness.** Both blocks read register `30013` of the
  same meter, so `.../FB_RS485_EASTRON_SDM_POWER_1/ACTP` and
  `.../FB_RS485_EASTRON_SDM220_1/ACTP` should track each other. They will not be
  bit-identical every time — each block polls on its own timer and the meter updates
  between reads — but a persistent difference means one of them has stopped decoding
  correctly.

:bulb: **Both will publish an exact `0.0` from time to time and neither is broken.** A meter
carrying a few watts reports zero for some updates. The control that settles it is a
different value out of the *same* frame: the SDM220 block reads current and power factor
from the same 40-register reply as active power, and those hold steady on the cycles where
active power reads 0.

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
