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
apart.

DFRobot documentation:
- [Product wiki](https://wiki.dfrobot.com/Laser_Ranging_Sensor_RS485_4m_SKU_SEN0492)
- [Modbus reference and register table](https://wiki.dfrobot.com/sen0492/docs/21034)

----------------------------

:rotating_light: **It ships at 115200 baud and there is no switch on the sensor.** A bus has one
baud rate, so a sensor that disagrees with it cannot be heard at all — it is not slow to answer,
it is inaudible. **The PLC moves it, from PLC logic alone:** `PLC_PRG_RS485` finds the sensor at
whatever rate it is on and writes the bus rate into it at startup, so no configuration tool,
adapter or vendor software is needed to commission one. See
[A device that ships on the wrong baud rate](../RS485/UsingModbusRTU_CODESYS3S.md).

----------------------------

:white_check_mark: **Verified on hardware.** Runs on a CODESYS 3 PFC200 against a real SEN0492:
distance reads and tracks, `OUTPUT_STATE` reads `0`, and both entities appear in Home Assistant.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌──────────────────────────────────────────┐
       │      FB_RS485_DFROBOT_SEN0492_MQTT       │
       ├──────────────────────────────────────────┤
TIME ──┤ PollIntervalOverride            DISTANCE ├── UINT
 INT ──┤ AvailabilityFailLimit       OUTPUT_STATE ├── BYTE
       │                         MeasurementValid ├── BOOL
       │                            DataAvailable ├── BOOL
       │                                    Error ├── BOOL
       │                              SuccessRate ├── USINT
       └──────────────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PollIntervalOverride` | TIME | The poll interval that can be changed **without the IDE**. Zero means use whatever `FB_init` was given; anything else wins, subject to the same 8 s floor. It exists because CODESYS stores an instance's `FB_init` arguments outside the declaration text, so no script can revise the constructor argument — see [CLAUDE.md](../../CLAUDE.md). Settable from `RS485_INIT` or online while the PLC runs, and applied on the next poll. |
| `AvailabilityFailLimit` | INT | Consecutive failed transactions before the sensor is declared offline. Defaults to 3, so around half a minute at the 8 s minimum poll. Raise it on a bus that is busy or long; 1 would mean every transient shows up in Home Assistant as a disconnection. Recovery is immediate on the first good transaction regardless. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `DISTANCE` | UINT | Distance to the target in **millimetres**, straight from register `16#34` with no scaling to undo. Only updated while `OUTPUT_STATE` says the reading is good, so after a failed measurement this holds the last trustworthy value rather than a plausible-looking wrong one. |
| `OUTPUT_STATE` | BYTE | The sensor's own verdict on the measurement: `0` valid, `1` sigma fail, `2` signal fail, `3` min range fail, `4` phase fail, `5` hardware fail, `7` no update. Published on every poll whatever it says — it is the only thing that explains a distance that has stopped moving. |
| `MeasurementValid` | BOOL | `OUTPUT_STATE = 0`, as a flag. FALSE means `DISTANCE` is being held, not refreshed. |
| `DataAvailable` | BOOL | High once the block has completed a successful read. Low only at startup. |
| `Error` | BOOL | High when an error occurred while executing the Modbus read command. |
| `SuccessRate` | USINT | Percentage of the last sixteen transactions that succeeded, published to `/QUALITY`. 100 is a healthy sensor. This is the signal that says how well the device is working rather than whether it is reachable at all — it moves while `/availability` is still `online`, which is the point. |

### **Methods**

**`BuildTransaction`** — Called once after this device has been granted the bus. Fills in every step it wants executed and returns how many; they then run back to back with the bus held. Returning 0 withdraws.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pSteps` | POINTER TO RS485_StepList |  | Scheduler-owned scratch to fill. Only valid for the duration of the call. |

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DeviceAddress` | BYTE |  | Modbus RTU address of the device on the RS485 bus. |
| `DataPollingInterval` | TIME |  | How often this block polls the device. **Anything below 8 s is silently raised to 8 s** — the sensor cannot answer faster and asking only produces failures. See *It cannot be polled quickly* below. |

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
FB_RS485_SEN0492_1 : FB_RS485_DFROBOT_SEN0492_MQTT(80, T#10S)
                   := (FriendlyName := 'Cistern level');
```

`80` is the sensor's factory slave address — `16#50`, which is how DFRobot's own documentation
writes it. Change it only if something else on your bus already answers there; the baud rate is
the setting that always has to move, and `PLC_PRG_RS485` does that once at startup. Register it
with the bus controller in `RS485_INIT`:

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

### **What commissioning found**

The startup sweep publishes its result retained to `.../RS485/SEN0492_COMMISSION`, so it can be
read off the broker without an online debug session:

```
probes=1 found=9600/255 maxrx=9 at=9600/255 written=FALSE
```

Read that as: the sensor answered on the **first** probe, at 9600 with `255` — the sentinel for
the ordinary framing — so **one stop bit is fine**, despite forum reports of 8N2. `maxrx=9` is
exactly the length of a two-register function 3 reply. `written=FALSE` because it was already at
9600: an earlier sweep had moved it, and **that setting survives both PLC restarts and the
sensor's own power cycle**, so the baud rate is stored in the sensor rather than held in RAM. The
sweep runs every boot anyway, so a sensor that has been factory-reset is simply found and moved
again.

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
| — | `/availability` | `online` / `offline` | **only when it changes** |

Publishing the state always and the distance only when it is good is what lets a reader tell a
held reading from a fresh one. A sensor pointed at nothing, or at something beyond 4 m, reports
a state other than `0` and its distance simply stops updating.

### **Telling "unreachable" apart from "getting worse"**

Two signals, because they answer different questions and one cannot do both jobs.

| | `/availability` | `/QUALITY` |
|:--|:--|:--|
| answers | can it be reached at all | how well is it working |
| shape | binary, debounced, published on change | percentage, no hysteresis, published every transaction |
| moves when | the sensor stops answering entirely | the sensor starts missing some polls |

`/availability` has to be debounced or it reports noise — a single missed reply on a shared
RS485 bus is ordinary. But that same debounce means a sensor answering two polls in three still
reads `online`, which is true and useless if what you want to know is whether it is degrading.

`/QUALITY` is that second signal: the share of the last sixteen transactions that succeeded. It is announced as a **diagnostic** entity — it belongs beside the measurement state, under the device's diagnostics, not on a dashboard — but it keeps a unit and a state class so Home Assistant still graphs it and holds statistics.
**It is the entity to put an automation on.** A sensor that starts answering nine polls in ten
instead of ten shows up there immediately, while availability is still reporting a cheerful
`online`; a loose pair, a failing driver or a bus getting busier all appear as a number settling
below 100 long before anything disconnects.

### **It cannot be polled quickly, and the interval is clamped**

`FB_init` refuses an interval below **8 seconds** and quietly substitutes it. That is a
hardware limit rather than a preference, and it was measured rather than assumed — on a PFC200
with the sensor alone on the bus, nothing else registered:

| Poll interval | Requests / 30 s | Answered | Success |
|:--|--:|--:|--:|
| 2 s | ~19 | ~4 | **~25%** |
| 7 s | ~4 | ~4 | ~100% |
| 10 s | 3 | 3 | ~100% |
| 30 s | 1 | ~0.7 | ~70% |

The sensor answers roughly **once every six or seven seconds however often it is asked**, and
drops the requests in between. The 30 s row is a later measurement on a rewired bench and shows
where the ceiling actually is: slowing down past the floor buys nothing, because what remains is
not a rate problem. Asking faster changes nothing except the proportion that fail —
which is what made the Home Assistant connectivity sensor flap, because three consecutive
misses is easy to reach at 2 s and hard at 8 s.

A caller who asks for something the device cannot sustain gets a working sensor and a slower
one. The alternative is a reading that is right a quarter of the time and an entity that keeps
going unavailable, which is worse in every way that matters.

:bulb: **The shipped instance in `RS485Variables` still declares `T#2S`, and does not run at
it.** Two things stop it: the clamp would hold it at 8 s on its own, and `RS485_INIT` sets
`PollIntervalOverride := T#10S` on top of that, which is the rate this project actually polls
the sensor at. The declaration is wrong and stays wrong because CODESYS stores an instance's
`FB_init` arguments outside the declaration text — see [CLAUDE.md](../../CLAUDE.md) — so that
argument cannot be corrected by any script, only in the IDE. The clamp exists partly because of
that: a value that cannot be fixed automatically should not be able to break the device.

:rotating_light: **A residual failure rate remains, it is specific to this sensor, and slowing
the poll further does not help.** Raising the interval from 8 s to 30 s was tried and changed
nothing: `/QUALITY` settled at **60–75%** either way. The poll rate mattered enormously at 2 s
and is not the limiter beyond about 8 s.

What the failed frames contain says why. Every one has the shape

```
00 04 00 12 00 00 1A F3        expected: 50 03 04 00 12 00 00 crc crc
```

— eight bytes where nine are expected, carrying the sensor's real data (`00 12` is the 18 mm it
was reporting at the time), with the first **two** bytes `50 03` collapsed into a single `00`.
A byte is genuinely lost on the wire, so no amount of resynchronising in software can recover
it: the CRC covers the address, and the address is what got destroyed.

**The control is on the same bus.** An Eastron SDM220 sharing the pair runs at roughly 90%
success with `CrcFail` barely moving, so this is not the wiring in general — it is something
about how this sensor turns its driver on. The most likely candidate is turnaround timing: the
SEN0492 answers very quickly, so its first byte can begin while the PLC's own driver is still
enabled, where a slower meter would not collide. Termination and bias resistors are the standard
remedy and this bus still has neither fitted, which remains the first thing to try.

### **Availability is debounced, and published on change**

`/availability` is deliberately not a per-transaction verdict, because that is not what a
connectivity sensor is for.

**One missed reply does not mean offline.** On a shared RS485 bus a single failure is ordinary —
a slave that was mid-measurement, a collision with another device's turnaround, a round in which
three non-responding devices each held the bus for their reply timeout. Declaring the sensor
down on the strength of one of those makes the Home Assistant connectivity sensor flap between
two states that are both wrong. `AvailabilityFailLimit` consecutive failures are required
instead; recovery is immediate on the first good transaction. Slow to distrust, quick to
forgive, because the cost of a false `offline` is an entity that looks broken.

**And it is published only when the verdict changes**, plus once at startup so a retained value
exists before anything has gone wrong. Republishing `online` every couple of seconds for the
life of the PLC tells nobody anything, and on this block it was the majority of the MQTT traffic.

:bulb: **The other RS485 blocks in this project still publish availability on every
transaction.** `FB_RS485_EASTRON_SDM220_MQTT`, `FB_RS485_EASTRON_SDM630_MQTT` and
`FB_RS485_EASTRON_SDM_POWER_MQTT` all carry the older idiom, so a meter that is absent or
intermittent produces the same flapping this block used to. Worth propagating.

### **Home Assistant**

The block publishes its own discovery configs, so no YAML is needed. It announces the sensor as
a device of its own — manufacturer `DFRobot`, model from the `Model` parameter — with two
entities underneath it:

| Entity | Category | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|:--|
| Distance | — | `distance` | — | mm |
| Measurement state | diagnostic | — | — | — |
| Link quality | diagnostic | — | `measurement` | % |

Distance carries no state class on purpose: it is a position, not a quantity worth averaging or
totalling, and Home Assistant's long-term statistics on it would be meaningless. Measurement
state is registered as a **diagnostic** entity, so it lands under the device's diagnostics
rather than on a dashboard — it is what you look at when the distance stops making sense.
