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

So: a factory-default 750-463 with a Pt1000 is plug-and-play. Anything else is a WAGO-I/O-CHECK
job at a laptop, and the symptom that says so is described below.

:rotating_light: **The reference bench's own module is not factory default, and this is what that
looks like.** Channel 0, with a Pt1000 connected, reads exactly `1500` — 150.0 °C — and has never
moved a digit. The other three channels read `0` rather than an over-range value. Both facts point
the same way: the channels are not measuring what is connected to them. See
[what the readings said](#what-the-readings-actually-said).

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
fbAiRtd001(Raw := RTD_001, HeartbeatInterval := tRtdSweepPublish);
```

`tRtdSweepPublish` is `T#1S` — one place to change it for all twelve. The block's own default is
five minutes, which is right for a commissioned sensor and useless for watching a value move as a
probe goes in.

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

#### 1500 is an open circuit, and that is the whole story

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

:rotating_light: **And it is why the range check can never catch a broken wire on this hardware.**
`1500` is 150.0 °C, comfortably inside the -200…850 °C a platinum RTD can produce, so
`FB_INPUT_TEMPERATURE_RTD_MQTT` passes it and publishes it as a healthy reading. On a module that
signals an open circuit by going *outside* the range the check works; on this one it cannot. The
`StaleTimeout` check is what catches it here — an open circuit does not dither — which is the
whole reason that second test exists.

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

Which points at the modules rather than the wiring or the project, and **weakens this page's own
claim that a 750-463 is plug-and-play for a Pt1000**. Three modules that have never seen
WAGO-I/O-CHECK all report the same constant and none responds to a sensor; the simplest reading of
that is that `1500` is what an unconfigured channel reports, and that these do not measure until
they are configured.

**The K-bus is not the alternative any more.** Switching a digital output moved its LED, so the
bus is delivering in both directions and the analog modules really are reporting a constant of
their own.

**And the terminals were shorted.** A scrap of wire across a channel is zero ohms, below the
bottom of every range a 750-463 can be set to, so a channel that is measuring *must* move. `TEMP`
did not change. That is the end of the diagnosis: the channel is not looking at its terminals, and
the module needs WAGO-I/O-CHECK. There is no route to it from the PLC, the IDE or this project.

:bulb: **Three modules behaving identically is worth a thought about provenance.** Three
independent ADCs agreeing to the digit is what you would expect from a shared default *or* from
three modules that were configured the same way before you owned them. If they came from one
second-hand batch, "factory default" may not be what any of them holds.

### **Two 30-second tests before reaching for a laptop**

Both change the sensor's electrical situation and ask whether the number follows. A channel that
is really measuring cannot ignore either.

1. **Move the sensor to another channel.** If only one channel was reconfigured, a neighbour may
   be untouched and will simply work — and the answer arrives without any tooling. Change the
   call to `Raw := RTD_002` to match.
2. **Short the terminals**, briefly, with a bit of wire. A measuring channel drops to the bottom
   of its scale immediately. A channel that stays where it was is not looking at its terminals at
   all, which is conclusive.

### **Reconfiguring the module, if it comes to that**

If neither test moves the number, the channel's settings have to be changed in the module, and
that means **WAGO-I/O-CHECK**. Three things to know before planning for it:

- **It is chargeable.** WAGO's own download-center entry for 3.25.03 says so in as many words:
  *"Please note that this software package is chargeable... A download link will only be sent
  after the proof of purchase has been verified."* The download is requested at
  [wago.com/de/d/6599903](https://www.wago.com/de/d/6599903) and the manual is
  [wago.com/global/d/388](https://www.wago.com/global/d/388). It is not on winget and there is no
  free installer - the one `winget search wago` hit is *wago.io*, a World of Warcraft addon
  manager, and emphatically not this.
- **What to order.** One item covers both halves:

  | Item number | WAGO's product name | What it is |
  |:--|:--|:--|
  | **759-302/000-923** | WAGO-I/O-CHECK; USB-Set | the software **and** the USB service cable |
  | 759-302 | WAGO-I/O-CHECK | software only |
  | 759-920 | WAGO-I/O-CHECK | software only, listed cheaper than 759-302 |
  | 750-923 | Configuration cable; USB connector; Length: 2.5 m | cable only, 4-pole to USB-A |
  | 750-920 | Configuration cable | cable only, RS-232 rather than USB |
  | 750-921 | Radio adapter | wireless alternative to the cable |

  The USB-Set is the one to buy unless a cable is already on the shelf.
- **It needs a cable, not a network.** The PFC200 talks to it through the 4-pin service header
  under the front flap. That interface exists for I/O-CHECK, I/O-PRO and firmware download, and
  750-920, 750-921 and 750-923 are the three ways into it.

:rotating_light: **I/O-CHECK cannot reach a PFC200 over Ethernet. It is the cable or nothing.**
Scanning the controller's IP returns *"the communication protocol is not supported by this device
or it's deactivated in the device"*, and that message is accurate rather than a hint to go looking
for a switch. WAGO's own firmware config for this family
([pfc-firmware-sdk](https://github.com/WAGO/pfc-firmware-sdk/blob/master/configs/wago-pfcXXX/ptxconfig_generic))
starts the service like this:

```
PTXCONF_IO_CHECK_RS232=y
PTXCONF_IO_CHECK_RS232_STARTLINE="localhost:wago-serv-ser stream tcp nowait.3 root /usr/bin/iocheckd iocheckd serial"
```

`iocheckd` is an on-demand service **bound to localhost**, fed by the serial service interface.
Nothing network-facing serves the I/O-Check protocol, so no WBM setting will make an Ethernet scan
work.

Then, with the cable in the 4-pin header:

1. **Release the K-bus, and do not assume a stopped application is enough.** The 750-8202 manual
   requires the PLC runtime to be stopped or deactivated before I/O-CHECK can reach the I/O
   modules, because the runtime owns the K-bus - the firmware is built with
   `PTXCONF_CDS3_IODRVKBUS=y`. That is about the runtime *process*, not the IEC application, so
   `codesys.ps1 download -Force -NoStart`, which leaves the application loaded but stopped, may
   well not be sufficient: the K-bus driver belongs to the runtime, and the runtime is still up.
   Stopping the runtime service itself is the certain version - the WBM's *PLC Runtime* page, or
   stopping `codesyscontrol` over SSH - and either is reversible.

   **Which runtime is selected does not matter.** The service interface is a firmware-level
   service: `iocheckd`, started on demand, bound to localhost and fed by the serial port. It is
   not part of any PLC runtime, so I/O-CHECK behaves the same whether the controller is set up
   for e!RUNTIME or, as the bench units are, for CODESYS Control for PFC200 SL - `scan` reports
   those as *"CODESYS GmbH CODESYS Control for PFC200 SL"*. The only requirement either way is
   that whatever owns the K-bus lets go of it.
2. Point I/O-CHECK at the **virtual COM port** the USB cable presents, not at an IP, and let it
   identify the node.
3. Select the 750-463 and set the channel to **Pt1000, 0.1 °C, 2-conductor, enabled**. Write the
   settings into the module, power-cycle the node, and start the application again.

:rotating_light: **Do not touch *Ports and Services → Serial Interface* in the WBM.** That page
governs the onboard RS232/485 port, which on this bench carries the Modbus bus at 9600 and had to
be assigned to the PLC runtime with `serialmode RS485` before any of the meters worked. The
service interface under the flap is a different connector and needs nothing configured.

There is no route to this from IEC code as this project is configured, and it is not a matter of
enabling something: the CODESYS device description for `01CF_75x_463` offers a single layout of
four input words, with no control/status byte, so there is no mailbox to write registers through.

:bulb: **Cheaper than the licence, if this is a one-off:** the sensor does not have to be on this
module at all. A 1-Wire probe on the ESERA gateway
([`FB_RS485_ESERA_OWD_MQTT`](../FunctionBlocks/FB_RS485_ESERA_OWD_MQTT.md)) publishes a
temperature over the RS485 bus that is already commissioned, and needs no module configuration
whatsoever.
