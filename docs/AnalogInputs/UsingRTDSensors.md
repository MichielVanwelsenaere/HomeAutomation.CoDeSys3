## Reading a temperature sensor (Pt1000) with a WAGO RTD module

### **Content**

How to connect a resistance temperature sensor to a WAGO 750-series RTD input module, map its
channel in CODESYS, and publish it with
[`FB_INPUT_TEMPERATURE_RTD_MQTT`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md). The
reference bench uses a **750-463** and a Pt1000; the same steps apply to its relatives.

### **Which module**

| Module | What it is | Sensor |
|:--|:--|:--|
| [750-463](https://www.wago.com/global/i-o-systems/4-channel-analog-input/p/750-463) | 4-channel analog input, adjustable | **Pt1000** / RTD resistance sensors, 2-conductor |
| 750-461 | 2-channel analog input | Pt100 / RTD, supports 3-conductor |
| 750-467 | 2-channel analog input | 0–10 V — **not** for an RTD |

:rotating_light: **A resistance sensor cannot go on a voltage input.** The 0–10 V module measures
voltage and has no excitation current, so a Pt1000 on it reads nothing meaningful. Check the
module number printed on the front before wiring anything.

### **Wiring**

A Pt1000 element is a resistor, so **it has no polarity** — either lead may go to either terminal
of the pair. What matters is landing on *one channel's pair*.

Each channel is a `+R`/`−R` pair, and the terminal numbers do **not** run in channel order:

| Terminal | Label | Sensor | CODESYS channel | First module | Second | Third |
|:--|:--|:--|:--|:--|:--|:--|
| 1 + 2 | `+R1` / `−R1` | 1 | Analog Input Channel 0 | `RTD_001` | `RTD_005` | `RTD_009` |
| 5 + 6 | `+R2` / `−R2` | 2 | Analog Input Channel 1 | `RTD_002` | `RTD_006` | `RTD_010` |
| 3 + 4 | `+R3` / `−R3` | 3 | Analog Input Channel 2 | `RTD_003` | `RTD_007` | `RTD_011` |
| 7 + 8 | `+R4` / `−R4` | 4 | Analog Input Channel 3 | `RTD_004` | `RTD_008` | `RTD_012` |

:rotating_light: **The pair next to sensor 1 is not sensor 2.** Terminals 3 and 4 are sensor
**3**; sensor 2 is on 5 and 6. Wire "the next pair along" and the reading appears on a channel two
places from the one being watched — which looks exactly like a dead channel if only one topic is
being watched, and is why the sweep watches all twelve at once.

Go by the `+R`/`−R` labels moulded into the module front rather than by counting terminals, and
note that CODESYS numbers its channels from **0** while WAGO numbers the sensors from **1**: WAGO's
sensor 1 is CODESYS's *Analog Input Channel 0*, which this project maps to `RTD_001`.

Two more points:

- **No jumper is needed.** The 750-463 measures 2-conductor only, so unlike the 3-wire-capable
  Pt100 modules there is nothing to bridge — the pair is the whole connection.
- **Use shielded cable** and land the screen on the DIN-rail shield clamp, at one end only.

Three practical points:

- **2, 3 or 4 leads on the sensor?** The 750-463 measures 2-conductor. A 3-wire or 4-wire probe
  works on it — join the doubled leads at the terminal, or simply use one lead of each pair. The
  third wire exists to compensate lead resistance, which the module cannot use; with a *Pt1000*
  that hardly matters, because the element changes about 3.85 Ω/°C, so even a metre or two of
  cable is worth a few hundredths of a degree. (On a Pt100 the same cable would be ten times as
  significant, which is why the Pt100 modules offer 3-conductor.)
- **Screened cable**: land the screen on the module's shield terminal or the DIN-rail shield
  clamp, at one end only.
- **Keep it away from the switched outputs.** A temperature signal is a high-impedance
  measurement sharing a rail with relay and dimmer wiring; run it separately where you can.

### **Configuring the channel — and who has to do it**

The module decides *what kind of sensor* a channel is measuring, and this is the one step no IEC
code in this project can perform:

- The **750-463 is the Pt1000 variant**, and Pt1000 is its factory default. If the module has
  never been reconfigured, **a Pt1000 needs no configuration at all.**
- It is *adjustable* — Pt1000, Ni1000, KTY81 and plain resistance ranges — and those settings live
  in the module, changed with **WAGO-I/O-CHECK** over the controller's service interface, or by
  register communication through the process image.
- **Register communication is not available at all, and not because of how this project is set
  up.** The installed device description is the authority, and it was read rather than assumed —
  `C:\ProgramData\CODESYS\Devices\288\0000 0001\4.19.0.0\device.xml` defines exactly **one**
  `01CF_75x_463` module, whose entire parameter set is a Modulecode, four `INT` input channels, and
  four bit-length WORDs marked `onlineaccess="none" offlineaccess="none"`. There is no sensor-type
  parameter, no control/status byte and no second variant to switch to, so there is nothing to
  enable in the IDE either. Its own description calls the module *"parameterizable"* — just not
  from here.

So: a factory-default 750-463 with a Pt1000 is plug-and-play. Anything else is a
[WAGO-I/O-CHECK](../WagoIoCheck.md) job at a laptop, and the symptom that says so is described
below.

:rotating_light: **The reference bench's own modules are broken, and configuration was never the
problem.** Channel 0, with a Pt1000 connected, reads exactly `1500` — 150.0 °C — and has never
moved a digit. This page spent a long time assuming that meant they had been set up for some other
sensor. They had not: WAGO-I/O-CHECK eventually showed every parameter already correct and the
analog front end producing no conversion at all. See
[where that leaves it](#where-that-leaves-it), and
[configuring a module with WAGO-I/O-CHECK](../WagoIoCheck.md) for how that was established.

### **Mapping the channel in CODESYS**

Each channel needs a variable name in the module's **I/O mapping** tab before any code can read
it. The reference bench carries three 750-463 modules and maps all twelve channels:

| Module on the rail | Node | Channel 0 | Channel 1 | Channel 2 | Channel 3 |
|:--|:--|:--|:--|:--|:--|
| first | `_75x_463` | `RTD_001` | `RTD_002` | `RTD_003` | `RTD_004` |
| second | `_75x_463_1` | `RTD_005` | `RTD_006` | `RTD_007` | `RTD_008` |
| third | `_75x_463_2` | `RTD_009` | `RTD_010` | `RTD_011` | `RTD_012` |

:rotating_light: **The order of the modules in the device tree must match their order on the
rail.** The K-bus hands the process image out in physical order, so a terminal in the wrong slot
of the tree reads its neighbour's words — silently, with a plausible number, which is the failure
this whole page is about.

**Check it in the IDE, and only there.** A script can add a terminal but cannot place one, and
cannot see where one sits: `insert` ignores the index it is given, remove-and-re-add does not move
a node, and the order the ScriptEngine and the PLCopen export both report is *creation* order
rather than rail position. The `codesys-loop` skill has the full account. Adding a terminal at the
far right of the rail sidesteps the question, because then appending is correct.

Naming the channels *is* scriptable, and doing it by hand is a double-click each:

```powershell
./tools/ai/codesys.ps1 device -MapIo .ai/edits/rtd-map.json -Force
```

Each is an `INT` carrying **tenths of a degree Celsius**, two's complement: `213` is 21.3 °C,
`-105` is -10.5 °C. That is the module's own scaling — there is nothing to calibrate in software.

### **Publishing it**

```
(* declaration, beside the other input blocks *)
fbAiRtd001 : FB_INPUT_TEMPERATURE_RTD_MQTT := (FriendlyName := 'Buffer tank top');
```

```
(* in the action the task calls every cycle *)
fbAiRtd001(Raw := RTD_001);
```

That is the whole of it: the block wires itself from `GVL_MQTT`, publishes to
`.../Out/AnalogInputs/fbAiRtd001/TEMP`, and announces one temperature sensor to Home Assistant —
which goes unavailable, rather than raising a separate problem entity, whenever the reading cannot
be trusted. See
[`FB_INPUT_TEMPERATURE_RTD_MQTT`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md).

### **Sweeping one sensor across every channel**

The fastest way to find out which channels on a rail are really measuring is to put a block on
every one of them, publish fast, and move a single probe from terminal to terminal while watching
all of them at once. The reference project does exactly that: twelve instances in `PRG_MAIN`,
called from `READ_PUSHBUTTONS`, each handed the sweep interval:

```
fbAiRtd001(Raw := RTD_001, HeartbeatInterval := tRtdPublishInterval);
```

`tRtdPublishInterval` is one place to change it for all twelve, and it matches the block's own
default of one minute. Drop it to `T#1S` while a probe is actually being moved from terminal to
terminal — but note the block sets each entity's `expire_after` to three heartbeats, so a
one-second interval also means Home Assistant gives up on a silent channel after three.

```powershell
mosquitto_sub -h 10.101.1.11 -v -t 'Devices/PLC/Lab/Out/AnalogInputs/+/TEMP'
```

Read it as a table: eleven values that never change and one that follows the probe is the answer.
Two channels moving together means the probe is bridging a pair. Nothing moving anywhere means
the modules are configured for something other than what is plugged in.

:bulb: **The 1 s heartbeat also shortens `expire_after`**, which the block sets to three
heartbeats — so a channel that stops publishing goes unavailable in Home Assistant within
seconds rather than a quarter of an hour. During a sweep that is useful; put the interval back
before treating any of these as a commissioned sensor.

### **Commissioning: what the reading tells you**

Read the channel word — online, or on the `/TEMP` topic — and compare against a room thermometer.
**Watch it for a minute**: whether it moves matters as much as what it says.

| Reading | Means |
|:--|:--|
| ≈ ambient, one decimal, **dithering in the last digit** | Correct. A real channel is never still; that jitter is what `PublishDeadband` exists to absorb. |
| Far out of range, `Fault` set | Open circuit, on a module that reports over-range. A lead is not in the terminal, or is in the wrong channel's. |
| **Any value, dead still for minutes** | The channel is not measuring: switched off, configured for a fixed value, or clamped at the end of a range that has nothing to do with the sensor. `Stuck` catches this and takes the entity unavailable; the value itself will look perfectly reasonable. |
| Plausible, moving, but roughly 2.6× the true value | The channel is set for Pt100 and a Pt1000 is connected. **Nothing automatic catches this** — it is in range and it tracks. Compare against a thermometer once. |
| ≈ 0.26× the true value, moving | The reverse: a Pt100 on a channel set to Pt1000. |

:bulb: **Measure the element with a multimeter and you know what the channel ought to say.** A
Pt1000 follows IEC 60751, so resistance converts straight to a temperature and to the channel
word the module should be reporting:

| Measured | Temperature | Channel word |
|:--|:--|:--|
| 1000 Ω | 0.0 °C | `0` |
| 1039 Ω | 10.0 °C | `100` |
| 1078 Ω | 20.0 °C | `200` |
| 1092 Ω | 23.6 °C | `236` |
| 1097 Ω | 25.0 °C | `250` |
| 1194 Ω | 50.0 °C | `500` |

The element moves at about 3.9 Ω/°C, so `(R - 1000) / 3.9` is good to a few hundredths of a
degree at room temperature and a quarter of a degree by 50 °C — far more than enough to judge a
reading by.

This is the check that needs no second thermometer and no tooling, and on this bench it is
conclusive: **1092 Ω at the terminals means the channel should report `236`, and it reports
`1500`.** Those are not the same measurement, and no amount of staring at a plausible-looking
150.0 °C would have said so.

### **What the readings actually said**

Measured on the reference bench, PFC200 + 750-463, one Pt1000 on channel 0:

```
RTD_001   1500  1500  1500  1500  1500  1500  1500      seven samples, 70 seconds
RTD_002      0    RTD_003  0    RTD_004  0               unwired channels
AI_001       0    AI_002   0                             the 0-10 V module, unwired
input image  %IW1 = 1500, every other word 0
```

Three things worth keeping from that:

- **The mapping is right and the module is not.** `%IW1` carries the channel, the value reaches
  `RTD_001` intact, and it is a constant. A misconfigured module produces a confident number, not
  an error.
- **An unwired channel here reads `0`, not over-range.** So on this hardware a disconnected sensor
  cannot be told from a genuine 0.0 °C by value alone — which is exactly why the block's second
  check is *movement* rather than range. Do not assume the over-range behaviour some data sheets
  describe; measure what your module does, on a channel you have deliberately left empty.
- **`0` is also what an unused 0-10 V channel reads**, so `0` on this bus means "nothing here"
  more often than it means zero.

#### 1500 is the top of the range — which is what an open circuit looks like

Three 750-463 modules, all channels configured, a block on each at 1 Hz, and **no sensor
connected to any of them**:

```
RTD_001..RTD_012   1500 on every one of them, twice, six seconds apart
```

Twelve open-circuit channels, twelve times `1500`. So on this module, as configured, **`1500` is
what a channel with nothing on its terminals reports** — and the three `0`s in the earlier
reading were *disabled* channels, not unwired ones. `0` never meant "nothing here"; it meant
"not switched on".

That retires the mystery this page opened with. The very first reading — `1500`, rock steady, on
a channel that had a Pt1000 wired to it — was the module reporting an open circuit. It was not a
misconfigured channel inventing a number. The sensor was not being seen at all.

:bulb: **Why `1500` and not some other constant.** The module's own description, read off its
front page in WAGO-I/O-CHECK much later, is `4AI RTD -30 °C - 150 °C`. So `1500` is not an
arbitrary value and not a fault code — it is *exactly the top of the range*, and an RTD input
saturates high when it sees infinite resistance. Knowing the range would have named this on day
one. **Read the module's stated range before theorising about its readings.**

:rotating_light: **And it is why the range check can never catch a broken wire on this hardware.**
`1500` is 150.0 °C, comfortably inside the -200…850 °C a platinum RTD can produce, so the range
check passes it. On a module that signals an open circuit by going *outside* the range the check
works; on this one it cannot.

That is what `PlausibleMin`/`PlausibleMax` were added for. Their -40…80 °C default is what a room,
a buffer tank or a floor loop can actually be, and 150 °C is not, so an open circuit on this module
is rejected on the first scan. Before that the twelve channels published as healthy `150.0 °C` for
the fifteen minutes `StaleTimeout` took to notice — and every restart bought another fifteen, which
is why the sensors kept looking fine every time anybody checked.

#### Except it was not an open circuit either — the bus was not running

With a Pt1000 verified at 1092 Ω on channel 0 of the first module, every mapped input word read:

```
RTD_001..RTD_012   1500      twice, eight seconds apart
AI_001, AI_002        0      the 0-10 V module's two words
```

**The sensor's value is in none of the fourteen words.** That is the reading that settles it: if
any module were measuring 1092 Ω, the number would have to appear *somewhere* in the process
image, and every word is accounted for. So no channel was measuring, and the wiring was never the
problem.

Two details name the cause. The values are constant to the digit across two reads — nothing is
dithering, so nothing is being sampled. And they cluster by **configured module type**, not by
position on the rail: `1500` on every word belonging to a configured 750-463 and `0` on both
belonging to the 750-467. Real bus data cannot sort itself by what the *project* thinks is
plugged in. These are the values the words hold when the driver never fills them.

The device tree looked like the culprit: it listed the terminals as
`440, 540, 540_1, 463, 550, 467, 463, 463` while the rail carried
`440, 540, 540_1, 463, 463, 463, 550, 467`. A K-bus is a shift register and the configured
sequence has to match the physical one, so a mismatch is a real fault and would explain a process
image full of values that never move.

**It was not the cause.** The 750-550 and 750-467 were unplugged from the rail and removed from
the tree, leaving `440, 540, 540_1, 463, 463, 463` on both sides — matched, verified — and all
twelve channels still read exactly `1500`. So the tree order was a genuine defect worth fixing and
it was not what made the channels read a constant. Both things were true at once, which is what
made it convincing.

:bulb: **Two faults at once is the normal case on a bench, not the exception.** Fixing one and
re-testing is the only way to tell which one you were looking at; the mistake here was writing
down a cause before re-testing.

#### Where that leaves it

Established, and not in doubt:

- Three separate 750-463 modules, twelve channels, all reading exactly `1500`, constant to the
  digit across reads seconds apart.
- A Pt1000 measuring 1092 Ω at the terminals — 23.6 °C, so the channel owes `236` — changes
  nothing, on whichever channel it is connected to.
- The value appears in no other word of the process image either, so nothing is measuring it and
  reading it somewhere unexpected.
- The device tree now matches the rail, so terminal order is not it.

**The K-bus is not the alternative.** Switching a digital output moved its LED, so the bus is
delivering in both directions and the analog modules really are reporting a constant of their own.

**And the terminals were shorted.** A scrap of wire across a channel is zero ohms, below the
bottom of every range a 750-463 can be set to, so a channel that is measuring *must* move. `TEMP`
did not change.

#### The verdict: the modules are faulty

WAGO-I/O-CHECK ended it. The full account of that session, and how to run one, is on
[configuring a module with WAGO-I/O-CHECK](../WagoIoCheck.md); the findings are:

| What was checked | What it showed |
|:--|:--|
| Channel 1 parameters | `Pt1000 (IEC751)`, 2-wire, two's complement — **already correct** |
| Manufacturer calibration | offset `88`, gain `16380` — intact factory data, not a wiped module |
| Module description | `4AI RTD -30 °C - 150 °C` |
| Process value | `150.00 °C`, i.e. the top of that range |
| A/D raw value | `9999998976` — an all-nines sentinel, not a measurement |
| A/D raw value with the terminals shorted | `9999998976`, **unchanged** |

So the analog front end is not converting, and no setting is going to fix that. **The modules are
faulty.** The parameters were right the whole time.

:rotating_light: **This page was wrong about the cause for weeks, and the wrong theory was
plausible at every step.** It read a rock-steady constant as a misconfigured channel; it then read
three modules agreeing to the digit as three modules configured alike before we owned them. Both
survived because nothing available at the time could see *upstream of the scaling stage*. What
settled it was one number no amount of process-image staring can produce — the A/D raw value —
and a second instrument agreeing with the first. **When two theories both fit, go and find an
instrument that only one of them survives.**

:bulb: **What to do instead, if a temperature is actually needed.** The sensor does not have to be
on this module at all. A 1-Wire probe on the ESERA gateway
([`FB_RS485_ESERA_OWD_MQTT`](../FunctionBlocks/FB_RS485_ESERA_OWD_MQTT.md)) publishes a
temperature over the RS485 bus that is already commissioned, and needs no module configuration
whatsoever.

### **Three 30-second tests before reaching for a laptop**

The first two change the sensor's electrical situation and ask whether the number follows. A
channel that is really measuring cannot ignore either.

1. **Move the sensor to another channel.** If only one channel was reconfigured, a neighbour may
   be untouched and will simply work — and the answer arrives without any tooling. Change the
   call to `Raw := RTD_002` to match.
2. **Short the terminals**, briefly, with a bit of wire. A measuring channel drops to the bottom
   of its scale immediately. A channel that stays where it was is not looking at its terminals at
   all, which is conclusive.
3. **Restart the K-bus** - pulse `PRG_MAIN.bKbusRestart` from an online view, with
   `bKbusEnableIoCheck` left `FALSE`. It costs one click, it needs no cable, and it is the answer
   whenever the I/O LED is anything but steady green. It asks a different question from the other
   two: not whether the channel is measuring, but whether the bus is delivering at all. See
   [reconfiguring the module](#reconfiguring-the-module-if-it-comes-to-that) for the flags.

### **Reconfiguring the module, if it comes to that**

If neither of the first two tests moves the number, the channel's settings have to be changed
inside the module, and that means **WAGO-I/O-CHECK** over the service cable — it is chargeable,
it cannot be reached over Ethernet, and something has to make the PLC let go of the K-bus first.

**All of that now has its own page: [configuring an I/O module with
WAGO-I/O-CHECK](../WagoIoCheck.md).** What to order, why a network scan cannot work, how to hand
the bus over with `PRG_MAIN.bKbusEnableIoCheck`, and how to read a module's pages once you are in.

Two things from it worth having in front of you before a session on an RTD module:

- **The flag is `bKbusEnableIoCheck` in `PRG_MAIN`**, written every cycle from
  `PRG_MAIN.READ_PUSHBUTTONS`, and it is **`FALSE` by default**. Set it `TRUE`, pulse
  `bKbusRestart`, do the work, then set it `FALSE` and pulse `bKbusRestart` again. The restart is
  what applies it, both ways.
- **Turn on `Diagnosis: Wire Break / Short-Circuit` while you are in there.** It is off from the
  factory, and it is the whole reason an open circuit on this module publishes a confident
  `150.0 °C` instead of announcing itself.

Then set the channel to **Pt1000, 0.1 °C, 2-conductor, enabled**, write it into the module, and
power-cycle the node.

**IEC code can hand the bus over, but it cannot do the configuring.** `EnableIoCheck` gets
I/O-CHECK access to the modules; it does not give the application any. The CODESYS device
description for `01CF_75x_463` offers a single layout of four input words, with no control/status
byte, so there is no mailbox to write a sensor type through — which is why the licence and the
cable are still the only way to change one.
