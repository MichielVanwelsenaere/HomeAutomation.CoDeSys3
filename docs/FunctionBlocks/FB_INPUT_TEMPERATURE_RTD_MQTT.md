## FB_INPUT_TEMPERATURE_RTD_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Publishes a temperature read by an **RTD input module** and announces it to Home Assistant as
**one** temperature sensor, which goes unavailable whenever the reading cannot be trusted.

It works with any WAGO 750-series RTD module that puts tenths of a degree in the process image —
the **750-450**, **750-451**, **75x-461** and **750-463** all do. The block reads a single channel
word, so how many channels the module has and which sensor it is set for are the module's
business, not the block's.

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

Changing one of those settings, or finding out what a channel is really doing, needs
**WAGO-I/O-CHECK** over the service cable — and the PLC has to let go of the K-bus first. That is
a flag in this project: **`bKbusEnableIoCheck` in `PRG_MAIN`**, `FALSE` by default and written
every cycle from `PRG_MAIN.READ_PUSHBUTTONS`. See
[configuring an I/O module with WAGO-I/O-CHECK](../WagoIoCheck.md), which is also where to look
when this block reports a channel that will not move: the module's **A/D raw value** is the one
number that says whether the front end is converting at all, and no amount of reading the process
image can produce it.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────────┐
       │   FB_INPUT_TEMPERATURE_RTD_MQTT   │
       ├───────────────────────────────────┤
 INT ──┤ Raw                   Temperature ├── REAL
REAL ──┤ LeadResistance              Valid ├── BOOL
REAL ──┤ PublishDeadband             Fault ├── BOOL
TIME ──┤ HeartbeatInterval           Stuck ├── BOOL
TIME ──┤ StaleTimeout        DataAvailable ├── BOOL
REAL ──┤ PlausibleMin                      │
REAL ──┤ PlausibleMax                      │
       └───────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Raw` | INT | The mapped channel word of the RTD module, in tenths of a degree Celsius. Wire it to the channel variable — `Raw := RTD_001` — and nothing else is needed to make the block work. |
| `LeadResistance` | REAL | Round-trip resistance of the sensor leads, in ohms; defaults to 0, which corrects nothing. The 750-451 and 750-463 both measure **2-conductor**, so the leads sit in series with the element and the channel reads *high* by them. A Pt1000 moves about 3.9 Ω/°C near room temperature, so the error is `LeadResistance / 3.9` °C — about 0.18 °C down 2×10 m of 0.5 mm², and 1.8 °C down 2×50 m of 0.25 mm². Measure it with the sensor disconnected, by shorting the far end of the pair and reading the loop at the terminals. :rotating_light: **Correct this in one place only** — see below. |
| `PublishDeadband` | REAL | Degrees Celsius of change required before the value is published again. Defaults to 0.2. The last digit of an RTD channel jitters continuously, and nobody wants 0.1 °C of noise in their history; zero publishes every change. |
| `HeartbeatInterval` | TIME | Republish even when nothing changed, so a reader can tell a steady temperature from a PLC that has stopped. Defaults to **1 minute**, and the discovery config's `expire_after` is set to three of these — so changing it changes both, but only for entities announced after the change. |
| `StaleTimeout` | TIME | How long the channel word may go without changing by a single digit before the reading is called into question. Defaults to 15 minutes; **zero disables the check**. :rotating_light: A quiet room can genuinely hold one tenth of a degree for far longer than that — see *[a wrong number that holds still](#a-wrong-number-that-holds-still)* for how to size it, and why too short a value takes a working sensor out of Home Assistant. |
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

### **Lead resistance, and the one place to correct it**

Both RTD modules this block is used with measure **2-conductor**. Nothing compensates for the
wire: the leads are in series with the element, so the channel reads high by their resistance.
A Pt1000 moves about **3.9 Ω/°C** near room temperature, which sets the scale of the problem:

| Cable | Loop resistance | Error |
|:--|:--|:--|
| 2×10 m of 0.5 mm² | ≈ 0.7 Ω | ≈ **0.18 °C** — ignorable |
| 2×25 m of 0.5 mm² | ≈ 1.7 Ω | ≈ **0.44 °C** |
| 2×50 m of 0.25 mm² | ≈ 6.8 Ω | ≈ **1.8 °C** — not ignorable |

So on a bench it does not matter and on a real run it does. Set `LeadResistance` to the measured
loop resistance and the block takes `LeadResistance / 3.9` degrees off the reading, in tenths and
in integers, so the single decimal the module actually has survives to the payload unchanged.
Leave it at 0 and the block behaves bit-for-bit as it did before the input existed.

```
fbAiRtd001(Raw := RTD_001, LeadResistance := 1.7);   (* 2x25 m of 0.5 mm2 *)
```

To measure it: disconnect the sensor, short the far end of the pair, and read the loop at the
terminals.

:rotating_light: **Correct it in exactly one place.** The module carries its own *user scaling*
and *user calibration*, written with [WAGO-I/O-CHECK](../WagoIoCheck.md) and stored in the
module's flash. The PLC cannot read them. Put an offset there **and** here and the correction is
applied twice, with nothing anywhere to say so — a 1.8 °C fix becomes a 1.8 °C error in the other
direction, and it will read as a badly calibrated sensor.

Prefer the PLC, for three reasons that have nothing to do with taste:

- the value is **in source control**, shows up in a diff and appears in the PLCopen export;
- it **survives swapping the terminal** — a module-side offset does not, and is worse than absent
  if the replacement module carries somebody else's;
- module-side settings are **invisible from CODESYS**, which is the whole reason
  [that page](../WagoIoCheck.md) had to be written.

The one argument the other way: a module-side correction applies to everything reading that
channel, not just this block. Nothing else reads it here.

:bulb: **This corrects a systematic offset, not noise, and it is not a calibration.** It assumes
the element itself is accurate — a Class B Pt1000 is ±0.3 °C at 0 °C on its own, which is larger
than most lead corrections. If you need better than that, one point against a reference
thermometer beats any amount of arithmetic.

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

:rotating_light: **The IEC 60751 range rarely fires, and that is why `PlausibleMin`/
`PlausibleMax` exist.** A module signals an open circuit by driving the channel to an end of its
scale, and both ends are legal platinum temperatures: a 750-463 reports `1500` — 150.0 °C — and a
750-451 reports `8500` — 850.0 °C. Both sit inside -200…850 °C, so the range check passes them.
With the default -40…80 °C plausible range, an open circuit is rejected on the **first scan**
instead of waiting out `StaleTimeout` — about 34 seconds after a restart, which is as fast as the
startup publish allows.

### **A wrong number that holds still**

The range checks above catch a number no sensor could produce, and an implausible one. Neither
catches the worst case: a **plausible** number that is not a measurement at all — a channel frozen
at a believable room temperature because its front end has stopped converting.

`StaleTimeout` is the guard for that. A channel whose word has not moved by a single digit for
that long sets `Stuck`, which sets `Fault`:

- `/availability` publishes `offline`, so the entity goes unavailable rather than showing a number
  nothing stands behind.
- **The value keeps being published** to `/TEMP`. It may be perfectly correct; what is in doubt is
  whether anything measured it. So it stays on the broker for anyone who wants to judge it, and
  stops being presented as a measurement.

Set `StaleTimeout` to zero to switch the check off.

:rotating_light: **Choose the timeout from how fast the process really moves, and be generous.**
The tempting assumption is that a live channel always dithers in its last digit, so any long
stillness is suspicious. That is not true of a quiet room. Measured on the reference bench, a
Pt1000 on a 750-451 moved from `259` to `262` over about three and a half hours — roughly **one
digit every 75 minutes**, holding each value dead still in between. A fifteen-minute timeout on
that channel would spend most of its life reporting `Stuck`, and the entity would be unavailable
in Home Assistant far more often than not.

So the check is only useful when the timeout is comfortably longer than the process's own quiet
periods. A draughty hallway may move every minute; a large water buffer or a cellar may not move
for half a day. **A false `Stuck` is not harmless** — it takes a working sensor out of Home
Assistant — so if you cannot name a period the value certainly cannot stay still for, leave the
check off rather than guessing.

:bulb: **`StaleTimeout` is the second line of defence, not the first.** `PlausibleMin`/
`PlausibleMax` catch the common case — an open circuit parked at an end of scale — on the first
scan, without waiting for any timeout. What is left for the stale check is the narrower case of a
value that is plausible *and* not being measured.

:bulb: **The remaining blind spot is a wrong sensor type that still moves.** Configure a channel
for Pt100, connect a Pt1000, and the reading tracks the temperature while being roughly 2.6 times
too high in the middle of the scale — in range, plausible, and moving. Nothing here catches that.
Compare against a second thermometer once, at commissioning.

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
