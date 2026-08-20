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
of the pair. What matters is using *one channel's pair* and not straying into a neighbouring
channel or a shield terminal. The channel-to-terminal assignment is printed on the module's own
front label and in its data sheet; on the 750-463 each channel is a 2-conductor pair.

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
- **Register communication is not available as this project is configured.** The device tree maps
  the module as four 16-bit input words and nothing else; the optional control/status byte per
  channel is not enabled, so there is no mailbox for IEC code to write. Enabling it is an IDE
  change to the module's I/O configuration.

So: a factory-default 750-463 with a Pt1000 is plug-and-play. Anything else is a WAGO-I/O-CHECK
job at a laptop, and the symptom that says so is described below.

:rotating_light: **The reference bench's own module is not factory default, and this is what that
looks like.** Channel 0, with a Pt1000 connected, reads exactly `1500` — 150.0 °C — and has never
moved a digit. The other three channels read `0` rather than an over-range value. Both facts point
the same way: the channels are not measuring what is connected to them. See
[what the readings said](#what-the-readings-actually-said).

### **Mapping the channel in CODESYS**

Each channel needs a variable name in the module's **I/O mapping** tab before any code can read
it. The reference project maps all four:

| Channel | Variable |
|:--|:--|
| Analog Input Channel 0 | `RTD_001` |
| Analog Input Channel 1 | `RTD_002` |
| Analog Input Channel 2 | `RTD_003` |
| Analog Input Channel 3 | `RTD_004` |

Each is an `INT` carrying **tenths of a degree Celsius**, two's complement: `213` is 21.3 °C,
`-105` is -10.5 °C. That is the module's own scaling — there is nothing to calibrate in software.

### **Publishing it**

```
(* declaration, beside the other input blocks *)
FB_AI_RTD_001 : FB_INPUT_TEMPERATURE_RTD_MQTT := (FriendlyName := 'Buffer tank top');
```

```
(* in the action the task calls every cycle *)
FB_AI_RTD_001(Raw := RTD_001);
```

That is the whole of it: the block wires itself from `MqttVariables`, publishes to
`.../Out/AnalogInputs/FB_AI_RTD_001/TEMP`, and announces a temperature sensor plus a diagnostic
fault flag to Home Assistant. See
[`FB_INPUT_TEMPERATURE_RTD_MQTT`](../FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md).

### **Commissioning: what the reading tells you**

Read the channel word — online, or on the `/TEMP` topic — and compare against a room thermometer.
**Watch it for a minute**: whether it moves matters as much as what it says.

| Reading | Means |
|:--|:--|
| ≈ ambient, one decimal, **dithering in the last digit** | Correct. A real channel is never still; that jitter is what `PublishDeadband` exists to absorb. |
| Far out of range, `Fault` set | Open circuit, on a module that reports over-range. A lead is not in the terminal, or is in the wrong channel's. |
| **Any value, dead still for minutes** | The channel is not measuring: switched off, configured for a fixed value, or clamped at the end of a range that has nothing to do with the sensor. `Stuck` and `/FAULT` catch this; the value itself will look perfectly reasonable. |
| Plausible, moving, but roughly 2.6× the true value | The channel is set for Pt100 and a Pt1000 is connected. **Nothing automatic catches this** — it is in range and it tracks. Compare against a thermometer once. |
| ≈ 0.26× the true value, moving | The reverse: a Pt100 on a channel set to Pt1000. |

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
that means **WAGO-I/O-CHECK**. Two things to know before planning for it:

- **It is chargeable.** WAGO's own download-center entry for 3.25.03 says so in as many words:
  *"Please note that this software package is chargeable... A download link will only be sent
  after the proof of purchase has been verified."* The licence is article **759-920** (or
  759-302/000-923); the download is requested at
  [wago.com/de/d/6599903](https://www.wago.com/de/d/6599903) and the manual is
  [wago.com/global/d/388](https://www.wago.com/global/d/388). It is not on winget and there is no
  free installer — the one `winget search wago` hit is *wago.io*, a World of Warcraft addon
  manager, and emphatically not this.
- **It needs a cable, not a network.** The PFC200 talks to it through the 4-pin service header
  under the front flap, using
  [750-923](https://www.wago.com/global/accessories/configuration-cable/p/750-923/) (USB, 2.5 m)
  or 750-920 (serial). That interface exists for I/O-CHECK, I/O-PRO and firmware download.

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

1. **Stop the PLC application.** The CODESYS runtime owns the K-bus — the firmware is built with
   `PTXCONF_CDS3_IODRVKBUS=y` — and it does not share it. `codesys.ps1 download -Force -NoStart`
   leaves the controller loaded but stopped; a normal `download` afterwards puts it back.
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
