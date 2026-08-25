## FB_INPUT_TEMPERATURE_RTD_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Publishes a temperature read by an **RTD input module** — a Pt1000 on a WAGO
[750-463](https://www.wago.com/global/i-o-systems/4-channel-analog-input/p/750-463) is what it
was written for — and announces it to Home Assistant as **one** temperature sensor, which goes
unavailable whenever the reading cannot be trusted.

**There is no scaling to configure and no calibration to do.** The module puts *tenths of a
degree Celsius* in the process image, two's complement, so `213` is 21.3 °C and `-105` is
-10.5 °C. Wire the channel word straight to `Raw` and the block is configured:

```
fbAiRtd001(Raw := RTD_001);
```

Everything else is a default that can be changed while the PLC runs, which is deliberate — none
of it lives in `FB_init`, so none of it is stuck behind the IDE (see
[CLAUDE.md](../../CLAUDE.md) for why that matters here).

:bulb: **This block reads a channel; it does not configure the module.** Which sensor type a
channel measures — Pt1000, Ni1000, KTY81, or a plain resistance range — is a setting inside the
module, not something IEC code can reach in this project's device configuration. See
[wiring an RTD sensor](../AnalogInputs/UsingRTDSensors.md).

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────────┐
       │   FB_INPUT_TEMPERATURE_RTD_MQTT   │
       ├───────────────────────────────────┤
 INT ──┤ Raw                   Temperature ├── REAL
REAL ──┤ PublishDeadband             Valid ├── BOOL
TIME ──┤ HeartbeatInterval           Fault ├── BOOL
TIME ──┤ StaleTimeout                Stuck ├── BOOL
REAL ──┤ PlausibleMin        DataAvailable ├── BOOL
REAL ──┤ PlausibleMax                      │
       └───────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Raw` | INT | The mapped channel word of the RTD module, in tenths of a degree Celsius. Wire it to the channel variable — `Raw := RTD_001` — and nothing else is needed to make the block work. |
| `PublishDeadband` | REAL | Degrees Celsius of change required before the value is published again. Defaults to 0.2. The last digit of an RTD channel jitters continuously, and nobody wants 0.1 °C of noise in their history; zero publishes every change. |
| `HeartbeatInterval` | TIME | Republish even when nothing changed, so a reader can tell a steady temperature from a PLC that has stopped. Defaults to **1 minute**, and the discovery config's `expire_after` is set to three of these — so changing it changes both, but only for entities announced after the change. |
| `StaleTimeout` | TIME | How long the channel word may go without changing by even one digit before the reading is called into question. Defaults to 15 minutes; zero disables the check. See *[a wrong number that holds still](#a-wrong-number-that-holds-still)* — this is not a theoretical safeguard, it is what the bench module needed. |
| `PlausibleMin` | REAL | Bottom of the range this sensor could plausibly be measuring, in °C. Defaults to -40. |
| `PlausibleMax` | REAL | Top of that range; defaults to 80. **This is the check that earns its keep.** The IEC 60751 bounds only ask whether a platinum RTD could produce a reading at all, which a 750-463's open-circuit `150.0 °C` passes comfortably — it is a legal Pt1000 temperature. No room, buffer tank or floor loop reaches it, so saying what the sensor is *for* rejects an open circuit on the first scan instead of waiting out `StaleTimeout`. Widen it deliberately for a flue, a solar collector or a freezer; set `Max <= Min` to switch the check off. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Temperature` | REAL | Degrees Celsius. **Held** at the last in-range reading while the channel is out of range, rather than following it into whatever the module reports for a broken wire. A *stuck* channel keeps updating it — the number may be right; what is in doubt is whether anything measured it. |
| `Valid` | BOOL | The channel is reading a real sensor, within the range this sensor type can measure. |
| `Fault` | BOOL | **Do not trust this reading.** Set when the value is outside what a platinum RTD can produce — usually a wire out of a terminal — and when the channel has stopped moving. This is what drives the entity's availability: while it is set, Home Assistant shows the sensor as unavailable. |
| `Stuck` | BOOL | The channel has not moved a digit for `StaleTimeout`. Kept separate from `Fault` so a debugger can tell *impossible number* from *not measuring*; both set `Fault`. |
| `DataAvailable` | BOOL | High once a plausible reading has been seen, and it **latches**: it answers *has this channel ever worked*, not *is it working now* — `Valid` is that one. One wart, found by a bench assertion that expected better: a mapped channel reads `0` for the first cycles before the K-bus fills the process image, and `0.0 °C` is perfectly plausible, so this latches TRUE (and `Temperature` holds `0.0`) even on a channel that goes on to measure nothing at all. Do not read it as proof a sensor is connected. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup. Not needed when `FriendlyName` is set at the declaration: the block then wires itself.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes the Home Assistant MQTT discovery config for the temperature sensor, including a per-entity availability topic so this one entity can go unavailable while the rest of the PLC stays up. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. An RTD channel is part of the PLC rather than a device of its own. |
| `Name` | STRING(255) |  | Name of the entity in Home Assistant. The self-wiring prologue passes `FriendlyName`. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **Code example**

Declare the instance where the program's other input blocks live, and let it wire itself:

```
fbAiRtd001 : FB_INPUT_TEMPERATURE_RTD_MQTT := (FriendlyName := 'Buffer tank top');
```

Then call it cyclically, handing it the module channel:

```
fbAiRtd001(Raw := RTD_001);
```

`RTD_001` is the variable the module's channel 0 is mapped to in the device tree's I/O mapping —
map the channel first, or the name will not resolve.

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from `GVL_MQTT`
on its first cyclic call. **A block wired this way must be called cyclically** — an instance
whose body never runs stays unwired and never appears in Home Assistant, and nothing warns about
it.

### **MQTT publish behavior**

| output | MQTT topic suffix | Unit | Published |
|:--|:--|:--|:--|
| `Temperature` | `/TEMP` | °C | on a change beyond `PublishDeadband`, on the heartbeat, and once at startup — **never while the value is out of range**, but a stuck channel keeps publishing |
| `Fault` | `/availability` | — | `offline` / `online`, **only when it changes**, plus once at startup — and that startup publish is required, because Home Assistant treats a missing availability payload as unavailable |

One decimal, always, formatted from the integer rather than through `REAL_TO_STRING` — which
would publish `21.299999` for a channel reading `213`. One decimal is all the module has, and
all anyone should be told it has.

### **A broken wire is not a temperature**

An RTD module reports a dead sensor by driving the channel to the end of its range, and both
which end and which exact value depend on the module and on how it was configured. This block
therefore does not look for a fault code. It asks the only question with a stable answer:
**could a platinum RTD produce this reading at all?** Anything outside -200 °C to +850 °C — the
range IEC 60751 defines for the type — is the module talking about the wiring rather than the
temperature.

What follows from that:

- `Temperature` **holds** its last trustworthy value, so a chart shows the reading stopping
  rather than a plunge to some sentinel.
- Nothing is published to `/TEMP` while the fault lasts. The discovery config carries
  `expire_after` at three heartbeats, so Home Assistant retires the entity on its own if the
  silence lasts — which is a truer signal than a made-up number, or a fault code dressed up as
  a temperature.
- `/availability` goes `offline` immediately, so the entity greys out where somebody is already
  looking at it — no waiting for `expire_after`, and no separate problem entity to notice.

:rotating_light: **On this hardware the IEC 60751 range never fires, and that is why
`PlausibleMin`/`PlausibleMax` exist.** A 750-463 reports an open circuit as `1500` — 150.0 °C —
which is inside -200…850 °C and therefore *passes*. Before the plausible range was added, twelve
open-circuit channels published as healthy `150.0 °C` readings for the fifteen minutes it took
`StaleTimeout` to catch them, and every restart bought another fifteen. With the default
-40…80 °C the same twelve went unavailable **34 seconds** after a restart, which is as fast as the
startup publish allows.

### **A wrong number that holds still**

The range check above catches a number no sensor could produce. It does not catch the worse case,
and this block was **wrong about that on its first run on real hardware**: a plausible number
that is not a measurement at all.

The bench's own 750-463 sat at exactly `1500` — a confident 150.0 °C, published to Home Assistant
with `dev_cla: temperature` and a fault flag reading `OFF`. Seven samples over seventy seconds:
`1500` every time, not one digit of movement. The module had been configured for something other
than the sensor plugged into it, and nothing in the process image said so.

What says so is that **a real channel is never still.** The last digit of an RTD reading dithers
continuously; 0.1 °C is far below the noise floor of any room. So a channel that has not moved a
single digit in `StaleTimeout` — fifteen minutes by default — is not trusted, whatever it is
holding:

- `Stuck` and `Fault` go TRUE and `/availability` publishes `offline`, so the entity goes
  unavailable rather than showing a number nothing stands behind.
- **The value keeps being published** to `/TEMP` regardless. It may be perfectly correct; what is
  in doubt is whether anything is measuring it. So it stays on the broker for anyone who wants to
  judge it, and stops being presented as a measurement.

Verified on hardware against the misconfigured channel, with `StaleTimeout` written down to 30 s
for the test: `Stuck=TRUE`, `Fault=TRUE`, `/availability offline`, and `/TEMP` still carrying
`150.0`.

:bulb: **`StaleTimeout` is the second line of defence now, not the first.** A plausible range
catches an implausible constant at once; the stale check remains for the harder case — a value
that *is* plausible and still is not being measured, such as a channel frozen at a believable
room temperature.

:bulb: **A slow-moving process can be genuinely still for minutes** — a large water buffer, a
cellar. Fifteen minutes of *zero* movement is still implausible on a 0.1 °C channel, but if a
process really is that quiet, raise `StaleTimeout` rather than living with an entity that keeps
going unavailable.

:bulb: **The remaining blind spot is a wrong sensor type that still moves.** Configure a channel
for Pt100, connect a Pt1000, and the reading tracks the temperature while being roughly 2.6 times
too high in the middle of the scale — in range, and moving. Compare against a second thermometer
once, at commissioning; after that the two flags cover what can be covered automatically.

### **Home Assistant**

The block publishes its own discovery config, so no YAML is needed. One entity appears, under the
PLC's own device:

| Entity | Category | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|:--|
| *FriendlyName* | — | `temperature` | `measurement` | °C |

**There is deliberately no diagnostic entity.** An earlier version published a `problem` binary
sensor alongside the reading, which put the fault in the diagnostics section of the device page —
somewhere nobody looks while reading a temperature. Instead the config carries two availability
topics with `avty_mode: all`:

```
"avty": [ {"topic": "Devices/PLC/Lab/availability"},
          {"topic": "Devices/PLC/Lab/Out/AnalogInputs/fbAiRtd001/availability"} ]
```

so the sensor is shown only while the PLC **and** the channel both say `online`. The second slot
is free to use because a PLC discovery device fills both with the same topic, so overriding one
loses nothing — see `CreateSensorEntity`'s `AvailabilityTopic`.

:rotating_light: **Removing the diagnostic entity orphans its retained config.** Anything that
published the old `problem` entity leaves `homeassistant/binary_sensor/<id>_FAULT/config` retained
on the broker, and Home Assistant goes on showing that entity forever. Clear it with an empty
retained message, along with the old `/FAULT` state topic.

`state_class: measurement` is set on purpose, unlike on the rangefinder: a temperature is
exactly the kind of quantity whose mean, minimum and maximum are worth keeping, so Home
Assistant's long-term statistics earn their place here.
