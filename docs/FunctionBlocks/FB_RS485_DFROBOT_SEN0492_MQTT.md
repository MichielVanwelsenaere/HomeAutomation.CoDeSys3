## FB_RS485_DFROBOT_SEN0492_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Reads a **DFRobot SEN0492** laser rangefinder over Modbus RTU and publishes the distance,
optionally announcing itself to Home Assistant. The sensor measures 4 cm to 4 m with roughly
±2 cm accuracy over RS485.

Distance and measurement state sit in adjacent registers (`16#34` and `16#35`) and are read in
one request, so the two always describe the same measurement rather than two moments a poll
apart. Everything on this sensor — readings and settings alike — is a **holding register**, so
it is function 3 to read and function 6 to write, not the input registers the Eastron meters use.

DFRobot documentation:
- [Product wiki](https://wiki.dfrobot.com/Laser_Ranging_Sensor_RS485_4m_SKU_SEN0492)
- [Modbus reference and register table](https://wiki.dfrobot.com/sen0492/docs/21034)

----------------------------

:rotating_light: **It ships at 115200 baud and this bus runs at 9600.** There is no switch on
the sensor. Until it is moved the two cannot talk at all — it is not slow to answer, it is
inaudible. `PLC_PRG_RS485` scans for it at startup and writes the new baud rate into it; see
[A device that ships on the wrong baud rate](../RS485/UsingModbusRTU_CODESYS3S.md) for how that
works and why it scans rather than assuming.

----------------------------

:rotating_light: **Not yet confirmed against hardware.** The block compiles, instantiates,
wires itself and announces itself to Home Assistant — all verified on a PFC200 — but no SEN0492
has yet answered on the bench, so the register decoding is unproven. A ten-rate scan at address
`16#50` found nothing, while the transport's `LeadNulls` counter moved: something is on the wire
but nothing framed. Wiring is the first thing to rule out.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌───────────────────────────────┐
   │ FB_RS485_DFROBOT_SEN0492_MQTT │
   ├───────────────────────────────┤
   │                      DISTANCE ├── UINT
   │                  OUTPUT_STATE ├── BYTE
   │              MeasurementValid ├── BOOL
   │                 DataAvailable ├── BOOL
   │                         Error ├── BOOL
   └───────────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `DISTANCE` | UINT | Distance to the target in **millimetres**, straight from register `16#34` with no scaling to undo. Only updated while `OUTPUT_STATE` says the reading is good, so after a failed measurement this holds the last trustworthy value rather than a plausible-looking wrong one. |
| `OUTPUT_STATE` | BYTE | The sensor's own verdict on the measurement: `0` valid, `1` sigma fail, `2` signal fail, `3` min range fail, `4` phase fail, `5` hardware fail, `7` no update. Published on every poll whatever it says — it is the only thing that explains a distance that has stopped moving. |
| `MeasurementValid` | BOOL | `OUTPUT_STATE = 0`, as a flag. FALSE means `DISTANCE` is being held, not refreshed. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |

### **Methods**

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO RS485_StepList |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `DataPollingInterval` | TIME |  | How often this block polls the device. |

**`HasWork`** — Asked by the bus controller whether this device wants the bus, and how badly: `NONE`, `POLL`, or `COMMAND` for something a person or Home Assistant is waiting on. Must be free of side effects - it is called on every device, twice per cycle.

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_DFROBOT_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `DeviceName` | STRING(50) |  | Name of that Home Assistant device. The self-wiring prologue passes `FriendlyName`. |
| `Model` | STRING(20) | `'SEN0492'` | Model shown on the Home Assistant device page. One discovery device serves the whole DFRobot RS485 range, so it is set per instance. |
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

**`RequestConfigWrite`** — Queues a single-register write for the next time this device is granted the bus, jumping ahead of routine polling. This is how the sensor's own settings are changed: they live in ordinary holding registers, so changing one is an FC6 step like any other. Returns FALSE if a write is already pending.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Register` | UINT |  | Holding register to write. `16#04` baud rate, `16#1A` slave id, `16#08` measurement interval (1..1000 ms), `16#36` measurement mode (1 = 1.3 m, 2 = 3 m, 3 = 4 m), `16#00` write 1 to restore factory settings. |
| `Value` | WORD |  | Value to write. The baud rate register takes a **code, not a rate**: 0..9 select 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600. |
<!-- fb-interface:end -->

### **Code example**

The declaration is the whole configuration — Modbus address and polling interval through
`FB_init`, the Home Assistant name through the initialiser:

```
FB_RS485_SEN0492_1 : FB_RS485_DFROBOT_SEN0492_MQTT(16#50, T#2S)
                   := (FriendlyName := 'Cistern level');
```

`16#50` is the factory slave address and collides with nothing else on this bus, so there is no
need to change it — only the baud rate has to move. Register it with the bus controller once in
`RS485_INIT`:

```
RS485BusController.RegisterDevice(device := RS485Variables.FB_RS485_SEN0492_1);
```

and call it cyclically, in `RS485_RUN`:

```
RS485Variables.FB_RS485_SEN0492_1();
```

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from `MqttVariables`
on its first cyclic call. **A block wired this way must be called cyclically** — an instance
whose body never runs stays unwired and never appears in Home Assistant, and nothing warns
about it.

### **Changing the sensor's settings from the PLC**

The sensor's configuration lives in holding registers, so `RequestConfigWrite` reaches all of it
through the ordinary bus arbitration — the write is a `COMMAND`, which goes ahead of routine
polling on every device:

```
(* move it to slave address 16#20 *)
RS485Variables.FB_RS485_SEN0492_1.RequestConfigWrite(Register := 16#1A, Value := 16#20);

(* measure to 4 m rather than the default range *)
RS485Variables.FB_RS485_SEN0492_1.RequestConfigWrite(Register := 16#36, Value := 3);
```

:rotating_light: **Two of these registers change how the sensor talks, and after writing one the
block can no longer reach it.** Changing the slave address (`16#1A`) leaves this instance
addressing the old one; changing the baud rate (`16#04`) leaves the whole bus at the wrong speed
for it. Both need the instance's `FB_init` arguments — or the bus — updated to match, so treat
them as commissioning rather than runtime control. The write is deliberately never retried, for
the same reason: its acknowledgement comes back at the new setting and this end cannot hear it.

### **MQTT publish behavior**

Set `FriendlyName` at the declaration and the block wires itself; see the code example above.

| output | MQTT topic suffix | Unit | Published |
|:--|:--|:--|:--|
| `OUTPUT_STATE` | `/STATE` | — | every poll |
| `DISTANCE` | `/DIST` | mm | only while the measurement is valid |
| — | `/availability` | `online` / `offline` | once per transaction |

Publishing the state always and the distance only when it is good is what lets a reader tell a
held reading from a fresh one. A sensor pointed at nothing, or at something beyond 4 m, reports
a state other than `0` and its distance simply stops updating.

### **Home Assistant**

The block publishes its own discovery configs, so no YAML is needed. It announces the sensor as
a device of its own — manufacturer `DFRobot`, model from the `Model` parameter — with two
entities underneath it:

| Entity | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|
| Distance | `distance` | — | mm |
| Measurement state | — | — | — |

Distance carries no state class on purpose: it is a position, not a quantity worth averaging or
totalling, and Home Assistant's long-term statistics on it would be meaningless. Measurement
state is registered as a **diagnostic** entity, so it lands under the device's diagnostics
rather than on a dashboard — it is what you look at when the distance stops making sense.
