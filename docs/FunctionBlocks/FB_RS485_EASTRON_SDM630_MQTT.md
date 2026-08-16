## FB_RS485_EASTRON_SDM630_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Reads an Eastron SDM630 three-phase energy meter over Modbus RTU and publishes every measurement
over MQTT, announcing each one to Home Assistant.

The whole measurement block is read in **one transaction** — function 4, 64 input registers from
`16#000C` to `16#004B` — so all 26 values come from the same instant and the bus spends one slot
per polling interval instead of 26.

Note the overlap with [FB_RS485_EASTRON_SDM_POWER_MQTT](./FB_RS485_EASTRON_SDM_POWER_MQTT.md),
which also speaks to an SDM630: that block covers the SDM120, SDM220 and SDM630 with one register
read and publishes **total active power only**. Use it when active power is all you need from any
of the three; use this block when you want the full picture from an SDM630.

Eastron SDM630 datasheet:
- [Manual and Modbus registers](../RS485/datasheets/SDM630-Modbus-V2.pdf)

----------------------------

:rotating_light: **Not yet run against hardware.** The block is compile-verified only; no SDM630
has answered it. See [Using Modbus RTU with the CODESYS 3S runtime](../RS485/UsingModbusRTU_CODESYS3S.md).

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌──────────────────────────────┐
   │ FB_RS485_EASTRON_SDM630_MQTT │
   ├──────────────────────────────┤
   │               L1_ACTIVEPOWER ├── REAL
   │               L2_ACTIVEPOWER ├── REAL
   │               L3_ACTIVEPOWER ├── REAL
   │                        L1_VA ├── REAL
   │                        L2_VA ├── REAL
   │                        L3_VA ├── REAL
   │                       L1_VAR ├── REAL
   │                       L2_VAR ├── REAL
   │                       L3_VAR ├── REAL
   │                        L1_PF ├── REAL
   │                        L2_PF ├── REAL
   │                        L3_PF ├── REAL
   │                       L1_PHI ├── REAL
   │                       L2_PHI ├── REAL
   │                       L3_PHI ├── REAL
   │                     AVG_LN_V ├── REAL
   │                   AVG_LINE_I ├── REAL
   │                   SUM_LINE_I ├── REAL
   │                  ACTIVEPOWER ├── REAL
   │                     TOTAL_VA ├── REAL
   │                    TOTAL_VAR ├── REAL
   │                     TOTAL_PF ├── REAL
   │                    TOTAL_PHI ├── REAL
   │                    FREQUENCY ├── REAL
   │          TOTAL_IMPORT_ENERGY ├── REAL
   │          TOTAL_EXPORT_ENERGY ├── REAL
   │                DataAvailable ├── BOOL
   │                        Error ├── BOOL
   └──────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `L1_ACTIVEPOWER` | REAL | Phase 1 active power, in watts. Input register `16#000C`. |
| `L2_ACTIVEPOWER` | REAL | Phase 2 active power, in watts. Input register `16#000E`. |
| `L3_ACTIVEPOWER` | REAL | Phase 3 active power, in watts. Input register `16#0010`. |
| `L1_VA` | REAL | Phase 1 apparent power, in volt-amperes. Input register `16#0012`. |
| `L2_VA` | REAL | Phase 2 apparent power, in volt-amperes. Input register `16#0014`. |
| `L3_VA` | REAL | Phase 3 apparent power, in volt-amperes. Input register `16#0016`. |
| `L1_VAR` | REAL | Phase 1 reactive power, in reactive volt-amperes. Input register `16#0018`. |
| `L2_VAR` | REAL | Phase 2 reactive power, in reactive volt-amperes. Input register `16#001A`. |
| `L3_VAR` | REAL | Phase 3 reactive power, in reactive volt-amperes. Input register `16#001C`. |
| `L1_PF` | REAL | Phase 1 power factor. Input register `16#001E`. |
| `L2_PF` | REAL | Phase 2 power factor. Input register `16#0020`. |
| `L3_PF` | REAL | Phase 3 power factor. Input register `16#0022`. |
| `L1_PHI` | REAL | Phase 1 phase angle, in degrees. Input register `16#0024`. |
| `L2_PHI` | REAL | Phase 2 phase angle, in degrees. Input register `16#0026`. |
| `L3_PHI` | REAL | Phase 3 phase angle, in degrees. Input register `16#0028`. |
| `AVG_LN_V` | REAL | Average line-to-neutral voltage, in volts. Input register `16#002A`. |
| `AVG_LINE_I` | REAL | Average line current, in amperes. Input register `16#002C`. |
| `SUM_LINE_I` | REAL | Sum of the three line currents, in amperes. Input register `16#002E`. |
| `ACTIVEPOWER` | REAL | Total system active power, in watts. Input register `16#0034`. |
| `TOTAL_VA` | REAL | Total system apparent power, in volt-amperes. Input register `16#0038`. |
| `TOTAL_VAR` | REAL | Total system reactive power, in reactive volt-amperes. Input register `16#003C`. |
| `TOTAL_PF` | REAL | Total system power factor. Input register `16#003E`. |
| `TOTAL_PHI` | REAL | Total system phase angle, in degrees. Input register `16#0042`. |
| `FREQUENCY` | REAL | Supply frequency, in hertz. Input register `16#0046`. |
| `TOTAL_IMPORT_ENERGY` | REAL | Cumulative imported active energy, in kilowatt-hours. Input register `16#0048`. Announced with `state_class: total_increasing`, which is what the Home Assistant energy dashboard consumes. |
| `TOTAL_EXPORT_ENERGY` | REAL | Cumulative exported active energy, in kilowatt-hours. Input register `16#004A`. Announced with `state_class: total_increasing`, which is what the Home Assistant energy dashboard consumes. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |

### **Methods**

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `DataPollingInterval` | TIME |  | How often this block polls the device. |

**`GetRtuQuery`** — `RS485Device` interface method. See the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_EASTRON_SDM_MQTT_DISCOVERY_DEVICE |  | Pointer to the Home Assistant device the meter is announced as. The self-wiring prologue passes the block's own `MqttDiscoveryDevice` member, so every meter becomes a device of its own rather than an entity on the PLC device. |
| `DeviceName` | STRING(50) |  | Name of that Home Assistant device. The self-wiring prologue passes `FriendlyName`. |
| `Model` | STRING(20) | `'SDM630'` | Model shown on the Home Assistant device page. One discovery device serves the whole SDM family, so the model is set per instance. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |

**`ProcessDataArray`** — `RS485Device` interface method. See the [RS485Device interface docs](../RS485/RS485Device_Interface.md).

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Error` | POINTER TO BOOL |  | Pointer to the bus error flag for the RTU query. |
| `Data` | POINTER TO ARRAY [0..124] OF WORD |  | Pointer to the response data returned by the RTU query. |

**`RequestBusTime`** — `RS485Device` interface method. See the [RS485Device interface docs](../RS485/RS485Device_Interface.md).
<!-- fb-interface:end -->

### **MQTT publish behavior**

Set `FriendlyName` in the declaration and the block wires itself — see
[MQTT self-wiring](../AdditionalFunctionality/MQTT_SelfWiring.md). Leave it empty and call
`InitMqtt` and `InitMqttDiscovery` yourself instead.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:--|:--|:--|:--|:--|:--|
| **new reading** | a Modbus response arrived and was decoded | real value | 2 | `FALSE` | no |
| **read succeeded** | first successful read, and after every recovery | `online` | 2 | `FALSE` | no |
| **read failed** | the Modbus request errored or timed out | `offline` | 2 | `FALSE` | no |

All 26 measurements are published together on each successful read. The publish topic is the
publish prefix, the function block instance name, and the suffix below:

| Output | MQTT topic suffix | Unit |
|:--|:--|:--|
| `L1_ACTIVEPOWER` | `/L1_ACTP` | W |
| `L2_ACTIVEPOWER` | `/L2_ACTP` | W |
| `L3_ACTIVEPOWER` | `/L3_ACTP` | W |
| `L1_VA` | `/L1_VA` | VA |
| `L2_VA` | `/L2_VA` | VA |
| `L3_VA` | `/L3_VA` | VA |
| `L1_VAR` | `/L1_VAR` | var |
| `L2_VAR` | `/L2_VAR` | var |
| `L3_VAR` | `/L3_VAR` | var |
| `L1_PF` | `/L1_PF` | — |
| `L2_PF` | `/L2_PF` | — |
| `L3_PF` | `/L3_PF` | — |
| `L1_PHI` | `/L1_PHI` | ° |
| `L2_PHI` | `/L2_PHI` | ° |
| `L3_PHI` | `/L3_PHI` | ° |
| `AVG_LN_V` | `/AVG_V` | V |
| `AVG_LINE_I` | `/AVG_I` | A |
| `SUM_LINE_I` | `/SUM_I` | A |
| `ACTIVEPOWER` | `/ACTP` | W |
| `TOTAL_VA` | `/TOT_VA` | VA |
| `TOTAL_VAR` | `/TOT_VAR` | var |
| `TOTAL_PF` | `/TOT_PF` | — |
| `TOTAL_PHI` | `/TOT_PHI` | ° |
| `FREQUENCY` | `/FREQ` | Hz |
| `TOTAL_IMPORT_ENERGY` | `/IMPE` | kWh |
| `TOTAL_EXPORT_ENERGY` | `/EXPE` | kWh |
| — | `/availability` | `online` / `offline` |

### **Code example**

The declaration is the whole configuration — Modbus address and polling interval through
`FB_init`, the Home Assistant name through the initialiser:

```
FB_RS485_EASTRON_SDM630_1 : FB_RS485_EASTRON_SDM630_MQTT(4, T#10S)
                          := (FriendlyName := 'Garage energy meter');
```

Register it with the bus controller once at startup, in `RS485_INIT`:

```
RS485BusController.RegisterDevice(device := RS485Variables.FB_RS485_EASTRON_SDM630_1);
```

and call it cyclically, in `RS485_RUN`:

```
RS485Variables.FB_RS485_EASTRON_SDM630_1();
```

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from `MqttVariables`
on its first cyclic call. **A block wired this way must be called cyclically** — an instance whose
body never runs stays unwired and never appears in Home Assistant, and nothing warns about it.

### **Home Assistant**

The block publishes its own discovery configs, so no YAML is needed. It announces the meter as a
device of its own — manufacturer `Eastron`, model from the `Model` parameter — with all 26
measurements as entities underneath it, rather than adding 26 entities to the PLC device.

The two energy totals carry `state_class: total_increasing`, which is what makes them selectable
in the **energy dashboard**. The instantaneous powers carry `state_class: measurement`; power
factor, phase angle, voltage, current and frequency carry none, so Home Assistant keeps no
long-term statistics on them.
