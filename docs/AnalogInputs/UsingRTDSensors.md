## Reading a temperature sensor (Pt1000) with a WAGO RTD module

### **Content**

How to connect a resistance temperature sensor to a WAGO 750-series RTD input module, map its
channel in CODESYS, and publish it with
[`FB_INPUT_TEMPERATURE_RTD_MQTT`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md). The
reference bench uses a **750-451** and a Pt1000 on `R1`; the same steps apply to its relatives.

### **Which module**

| Module | Channels | Sensor | Leads |
|:--|:--|:--|:--|
| 750-450 | 4 | RTD, adjustable | 2-, 3- and 4-conductor |
| [750-451](https://www.wago.com/global/i-o-systems/8-channel-analog-input/p/750-451) | 8 | RTD, adjustable — the bench's module, set for **Pt1000** | 2-conductor |
| 75x-461 | 2 | RTD. **The ordering variant fixes the sensor**: `/000-003` is Pt1000, `/000-006` Pt100, `/000-005` and `/000-009` Ni1000. Plain `75x-461` is adjustable. | 2- and 3-conductor |
| [750-463](https://www.wago.com/global/i-o-systems/4-channel-analog-input/p/750-463) | 4 | RTD, adjustable | 2-conductor |

Taken from the device description this controller actually carries rather than from a catalogue,
so it is the list of modules CODESYS here can be told it has.

### **Wiring**

A Pt1000 element is a resistor, so **it has no polarity** — either lead may go to either terminal
of the pair. What matters is landing on *one channel's pair*.

Each channel is a `+R`/`−R` pair. On the bench's **750-451** the eight sensors run straight
through to the eight channels, and this project maps them straight through again:

| Sensor | Label | CODESYS channel | Mapped variable | Block |
|:--|:--|:--|:--|:--|
| 1 | `R1` | Analog Input Channel 0 | `RTD_001` | `fbAiRtd001` |
| 2 | `R2` | Analog Input Channel 1 | `RTD_002` | `fbAiRtd002` |
| … | … | … | … | … |
| 8 | `R8` | Analog Input Channel 7 | `RTD_008` | `fbAiRtd008` |

:rotating_light: **Go by the `+R`/`−R` labels moulded into the module front, never by counting
terminal numbers.** Sensor *n* is not always on the *n*-th pair down the block: on the 4-channel
750-463 the pairs run `R1, R3, R2, R4`, so wiring "the next pair along" puts the reading two
channels from the one being watched — which looks exactly like a dead channel if only one topic
is open. That is the reason a sweep watches every channel at once rather than one.

Note also that CODESYS numbers its channels from **0** while WAGO numbers the sensors from **1**:
WAGO's sensor 1 is CODESYS's *Analog Input Channel 0*, which this project maps to `RTD_001` and
reads with `fbAiRtd001`.

Two more points:

- **No jumper is needed.** The 750-451 and the 750-463 both measure 2-conductor only, so unlike
  the 3-wire-capable Pt100 modules there is nothing to bridge — the pair is the whole connection.
- **Use shielded cable** and land the screen on the DIN-rail shield clamp, at one end only.

Three practical points:

- **2, 3 or 4 leads on the sensor?** The 750-451 measures 2-conductor. A 3-wire or 4-wire probe
  works on it — join the doubled leads at the terminal, or simply use one lead of each pair. The
  third wire exists to compensate lead resistance, which the module cannot use; with a *Pt1000*
  that hardly matters over a short run, because the element changes about 3.9 Ω/°C, so a metre or
  two of cable is worth a few hundredths of a degree. (On a Pt100 the same cable would be ten
  times as significant, which is why the Pt100 modules offer 3-conductor.)
- **Over a long run it does matter, and the block can take it off.** 2×50 m of 0.25 mm² is about
  6.8 Ω, which reads 1.8 °C high. Measure the loop with the sensor disconnected and the far end
  shorted, then pass it as
  [`LeadResistance`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md#lead-resistance-and-the-one-place-to-correct-it):
  `fbAiRtd001(Raw := RTD_001, LeadResistance := 6.8);`. **Do it there or in the module's user
  scaling, never both** — the PLC cannot see what WAGO-I/O-CHECK wrote, so a correction in each
  place is applied twice.
- **Screened cable**: land the screen on the module's shield terminal or the DIN-rail shield
  clamp, at one end only.
- **Keep it away from the switched outputs.** A temperature signal is a high-impedance
  measurement sharing a rail with relay and dimmer wiring; run it separately where you can.

### **Configuring the channel — and who has to do it**

The module decides *what kind of sensor* a channel is measuring, and this is the one step no IEC
code in this project can perform:

- The bench's **750-451 is set for Pt1000**, and that was established by measurement rather than
  from a data sheet: a Pt1000 on `R1` reads 25.9 °C in a room that is about that. A Pt1000 on a
  channel set for Pt100 sees ten times the resistance it expects and saturates at the top of
  scale, so **a correct absolute reading is itself the proof of the sensor type** — no tooling
  needed to establish it.
- The **750-463 is the Pt1000 variant**, and Pt1000 is its factory default. If the module has
  never been reconfigured, **a Pt1000 needs no configuration at all.**
- It is *adjustable* — Pt1000, Ni1000, KTY81 and plain resistance ranges — and those settings
  live inside the module. Changing one means **WAGO-I/O-CHECK** over the controller's service
  interface; there is no way to reach it from IEC code, because the channel words are the module's
  entire interface to the application, with no parameter or control byte beside them.

So: a module already set for the sensor you are plugging in is plug-and-play. Anything else is a
[WAGO-I/O-CHECK](../WagoIoCheck.md) job at a laptop.

### **Mapping the channel in CODESYS**

A channel has no name until it is given one, and code cannot read it until it has. Open the
module in the device tree, go to its **I/O mapping** tab, and type a variable name against each
channel you are using. The bench maps all eight:

| Node | CODESYS channel | Mapped variable |
|:--|:--|:--|
| `_750_451` | Analog Input Channel 0 … 7 | `RTD_001` … `RTD_008`, in order |

Each is an `INT` carrying **tenths of a degree Celsius**, two's complement: `213` is 21.3 °C,
`-105` is -10.5 °C. That is the module's own scaling — there is nothing to calibrate in software.

:rotating_light: **The order of the modules in the device tree must match their order on the
rail**, and it can only be checked in the IDE. The K-bus hands the process image out in physical
order, so a terminal in the wrong slot of the tree reads its neighbour's words — silently, and
with a number that looks perfectly reasonable.

### **Publishing it**

```
(* declaration, beside the other input blocks *)
fbAiRtd001 : FB_INPUT_TEMPERATURE_RTD_MQTT := (FriendlyName := 'Buffer tank top');
```

```
(* in the action the task calls every cycle *)
fbAiRtd001(Raw := RTD_001, ProcessImageValid := Pfc200Bus.xConfigFinished);
```

:rotating_light: **`ProcessImageValid` is not optional, and it defaults to `FALSE`.** Every mapped
word reads `0` until the K-bus has started, and `0` is a perfectly plausible 0.0 °C — so without
it the block publishes a fabricated zero on every restart, a moment before the real value. Wire it
to the bus driver's own output as above. Leave it out and the channel simply stays unavailable,
which is the loud failure rather than the silent one.

That is the whole of it: the block wires itself from `GVL_MQTT`, publishes to
`.../Out/AnalogInputs/fbAiRtd001/TEMP`, and announces one temperature sensor to Home Assistant —
which goes unavailable, rather than raising a separate problem entity, whenever the reading cannot
be trusted. See
[`FB_INPUT_TEMPERATURE_RTD_MQTT`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md).

### **Sweeping one sensor across every channel**

The fastest way to find out which channels on a rail are really measuring is to put a block on
every one of them, publish fast, and move a single probe from terminal to terminal while watching
all of them at once. The reference project does exactly that: eight instances in `PRG_MAIN`,
called from `READ_PUSHBUTTONS`, each handed the sweep interval:

```
fbAiRtd001(Raw := RTD_001, HeartbeatInterval := tRtdPublishInterval);
```

`tRtdPublishInterval` is one place to change it for all eight, and it matches the block's own
default of one minute. Drop it to `T#1S` while a probe is actually being moved from terminal to
terminal — but note the block sets each entity's `expire_after` to three heartbeats, so a
one-second interval also means Home Assistant gives up on a silent channel after three.

```powershell
mosquitto_sub -h 10.101.1.11 -v -t 'Devices/PLC/Lab/Out/AnalogInputs/+/TEMP'
```

Read it as a table: seven values that never change and one that follows the probe is the answer.
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
| ≈ ambient, one decimal | Correct. Do not expect it to dither: in still air a Pt1000 can hold the same tenth of a degree for an hour or more. |
| Far out of range, `Fault` set | Open circuit, on a module that reports over-range. A lead is not in the terminal, or is in the wrong channel's. **On the 750-451 that is `8500`** — 850.0 °C, the top of the platinum scale — on every unwired channel. |
| **A plausible value that never moves at all** | Possibly a front end that has stopped converting, and possibly just a very quiet room — a Pt1000 in still air can hold one tenth of a degree for over an hour. Nothing in the block catches this, because nothing can tell the two apart. Short the terminals briefly: a channel that is measuring drops to the bottom of its scale at once. |
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

This is the check that needs no second thermometer and no tooling: measure the element, convert,
and compare against the channel word. If the two disagree, the channel is not measuring what is
on its terminals — however reasonable the number looks.

### **What the 750-451 reads**

Measured on the reference bench, PFC200 + 750-451, one Pt1000 on `R1` and nothing on the other
seven, immediately after a download:

```
RTD_001    259     25.9 °C     Valid  Fault=FALSE  DataAvailable=TRUE
RTD_002..008  8500  850.0 °C   the seven unwired channels, all identical
```

and, watching the state topic for a further 140 s, `fbAiRtd001/TEMP` published `26.0` three
times — once per minute, which is the heartbeat, and **one digit above where it started**.

Four things that reading establishes, none of which a single sample could:

- **The channel is measuring.** 25.9 °C is right for the room, and the last digit moved within
  minutes — which a channel that is merely holding a plausible constant does not do.
- **The module is set for Pt1000.** A Pt1000 on a Pt100 channel cannot read correctly — it would
  saturate — so a correct absolute value settles the sensor type with no tooling at all.
- **An unwired channel saturates high**, at `8500`. That is the useful behaviour: an open circuit
  announces itself rather than impersonating a plausible 0.0 °C.
- **`PlausibleMin`/`PlausibleMax` are what catch it.** `8500` is 850.0 °C, comfortably inside the
  IEC 60751 range the block checks first, so that check passes it. It is the -40…80 °C plausible
  range that fails it, and the seven empty channels duly report `offline` and show as unavailable
  in Home Assistant rather than as seven confident 850 °C sensors.

:bulb: **The one test still outstanding** is warming the element by hand and watching the value
follow. A dithering last digit is strong evidence of a live conversion; a number that tracks a
deliberate change is proof. Nothing on this page depends on it, but say so rather than implying
it was done.

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
  factory, and it is the whole reason an open circuit publishes a confident end-of-scale reading
  — `850.0 °C` on the 750-451 — instead of announcing itself.

Then set the channel to **Pt1000, 0.1 °C, 2-conductor, enabled**, write it into the module, and
power-cycle the node.

**IEC code can hand the bus over, but it cannot do the configuring.** `EnableIoCheck` gets
I/O-CHECK access to the modules; it does not give the application any. An RTD module offers the
application its channel words and nothing else — no control or status byte to write a sensor type
through — which is why the licence and the cable are still the only way to change one.
