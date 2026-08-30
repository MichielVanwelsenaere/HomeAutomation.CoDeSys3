## Configuring an I/O module with WAGO-I/O-CHECK

### **Content**

Some things about a WAGO 750-series module are not settings in CODESYS at all — they live in the
module's own memory and are reached with **WAGO-I/O-CHECK** over the service cable. This page
covers when you need it, what to buy, how to make the PLC let go of the K-bus so the tool can get
in, and how to read what it shows you.

The worked example throughout is a **750-463** RTD input. See
[reading a temperature sensor](AnalogInputs/UsingRTDSensors.md) for the sensor side of that story
and [`FB_INPUT_TEMPERATURE_RTD_MQTT`](FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md) for the
block that publishes the channel.

### **When you need it — and when you do not**

The CODESYS device tree exposes a module's **process image**: its input and output words, which
you map to variables and read from IEC code. It does not expose the module's **parameters** —
what kind of sensor a channel is measuring, whether a diagnosis is enabled, what the scaling and
calibration are. Those live in the module.

For most terminals that distinction never comes up, because the defaults are what you want. It
comes up when:

- an analog input has to be told **which sensor type** is on it (Pt1000 versus Ni1000 versus a
  plain resistance range, and 2- versus 3-conductor on the modules that offer it);
- a channel's **diagnosis** needs enabling — wire break and short-circuit detection is off from
  the factory on the 750-463, and it is the difference between a broken sensor announcing itself
  and one quietly reading the top of its range;
- a module needs a **user scaling or calibration** rather than the manufacturer's;
- or you want to know what a module is *actually doing*, because the process image is telling you
  something you do not believe.

That last one is the case this page was written for, and I/O-CHECK is very good at it: it will
show you a channel's **A/D raw value**, upstream of every scaling stage, which is a thing no
amount of staring at the process image can give you.

:bulb: **Check whether the device description offers the parameter first.** If a setting is
reachable from CODESYS it will be in the module's parameter list in the device tree, and that is a
much cheaper route. On this project's bus, the description at
`C:\ProgramData\CODESYS\Devices\288\0000 0001\4.19.0.0\device.xml` defines the 750-463 as four
`INT` input words and a module code — no sensor-type parameter, no control or status byte. There
is nothing to try, which is how you know the cable is required.

### **What to buy**

One item covers both halves:

| Item number | WAGO's product name | What it is |
|:--|:--|:--|
| **759-302/000-923** | WAGO-I/O-CHECK; USB-Set | the software **and** the USB service cable |
| 759-302 | WAGO-I/O-CHECK | software only |
| 759-920 | WAGO-I/O-CHECK | software only, listed cheaper than 759-302 |
| 750-923 | Configuration cable; USB connector; Length: 2.5 m | cable only, 4-pole to USB-A |
| 750-920 | Configuration cable | cable only, RS-232 rather than USB |
| 750-921 | Radio adapter | wireless alternative to the cable |

:rotating_light: **It is chargeable.** WAGO's own download-center entry for 3.25.03 says so in as
many words: *"Please note that this software package is chargeable... A download link will only be
sent after the proof of purchase has been verified."* The download is requested at
[wago.com/de/d/6599903](https://www.wago.com/de/d/6599903) and the manual is
[wago.com/global/d/388](https://www.wago.com/global/d/388). It is not on winget — the one
`winget search wago` hit is *wago.io*, a World of Warcraft addon manager, and emphatically not
this.

### **It is a cable, not a network**

I/O-CHECK reaches a PFC200 through the **4-pin service header under the front flap**, and only
there. Scanning the controller's IP returns *"the communication protocol is not supported by this
device or it's deactivated in the device"*, and that message is accurate rather than a hint to go
looking for a setting to switch on.

WAGO's own firmware configuration for this family
([pfc-firmware-sdk](https://github.com/WAGO/pfc-firmware-sdk/blob/master/configs/wago-pfcXXX/ptxconfig_generic))
starts the service like this:

```
PTXCONF_IO_CHECK_RS232=y
PTXCONF_IO_CHECK_RS232_STARTLINE="localhost:wago-serv-ser stream tcp nowait.3 root /usr/bin/iocheckd iocheckd serial"
```

`iocheckd` is an on-demand service **bound to localhost**, fed by the serial service interface.
Nothing network-facing serves the I/O-Check protocol, so no WBM setting will make an Ethernet
scan work. Point the tool at the **virtual COM port** the USB cable presents.

:rotating_light: **Do not touch *Ports and Services → Serial Interface* in the WBM.** That page
governs the onboard RS232/485 port, which on this bench carries the Modbus bus at 9600 and had to
be assigned to the PLC runtime with `serialmode RS485` before any of the meters worked. The
service interface under the flap is a different connector and needs nothing configured.

### **Releasing the K-bus — the flag lives in `PRG_MAIN`**

**Something has to let go of the K-bus before I/O-CHECK can talk to the modules**, because the PLC
runtime owns it. There are two ways, and the cheap one is a flag in this project.

The K-bus driver has a property for exactly this case. `Pfc200Bus` — the node the device tree
declares under the controller — is an `IoDrvPfc200_Diag`, and it inherits `EnableIoCheck` and
`xRestart` from `IoDrvPfc200`:

> Enables the control mode for Wago I/O check software if set to true. In this case the K-Bus
> transmission cycle is controlled by the PFC software and not by CODESYS therefore the K-Bus bus
> cycle time is independent of the CODESYS bus cycle. It should be only enabled if the WAGO I/O
> Check software is used for the time of setting special parameters in the modules.

That is the library's own documentation, which the *CODESYS Control for PFC200 SL* package already
installed locally — `C:\ProgramData\CODESYS\LibDoc\CODESYS\IoDrvPfc200\4.10.0.0\`, the page
`enableiocheck.html`.

#### Where the flags are

**`PRG_MAIN`**, in its own `VAR` block at the end of the declaration, wired every cycle from the
action **`PRG_MAIN.READ_PUSHBUTTONS`**:

```
Pfc200Bus.EnableIoCheck := bKbusEnableIoCheck;
Pfc200Bus.xRestart      := bKbusRestart;
Pfc200Bus();                                  (* this is what reads xRestart *)
```

| Variable | Type | Default | What it does |
|:--|:--|:--|:--|
| `bKbusEnableIoCheck` | BOOL | **`FALSE`** | Hands the K-bus transmission cycle to the PFC firmware, so I/O-CHECK can reach the modules while the runtime keeps running. |
| `bKbusRestart` | BOOL | `FALSE` | A **rising edge** restarts the K-bus. Nothing else applies a change of mode. |

:rotating_light: **`bKbusEnableIoCheck` is `FALSE` by default and nothing in the project ever
writes either flag.** They exist to be set by hand from an online view for the length of a
session, and that is the only way they are meant to be used. A project shipped with the flag
`TRUE` would run its K-bus on the firmware's clock instead of the application's for as long as the
PLC was powered.

The cyclic call sits in `READ_PUSHBUTTONS` because that is the one action the SFC chart runs every
scan, and [a chart cannot be edited from a script](../CLAUDE.md). It deserves an action of its own
the next time that program is open in the IDE.

#### Using them

Log in to the PLC, open `PRG_MAIN`, and in the online view:

| Step | Set | Then |
|:--|:--|:--|
| hand over | `bKbusEnableIoCheck := TRUE` | pulse `bKbusRestart` TRUE → FALSE |
| | *do the work in I/O-CHECK* | |
| hand back | `bKbusEnableIoCheck := FALSE` | pulse `bKbusRestart` TRUE → FALSE |

Two ways to get this wrong, both of which look like the property not working:

- **Forgetting the restart.** Setting the property changes nothing until the bus restarts. Going
  straight from the flag to I/O-CHECK finds the same locked bus as before.
- **Forgetting to hand it back.** CODESYS does not take its bus cycle back on its own, and nothing
  warns you. Put the flag to `FALSE` and pulse the restart again before you call the session
  finished.

:bulb: **`bKbusRestart` on its own is worth knowing about.** With `bKbusEnableIoCheck` left
`FALSE`, a pulse is a plain K-bus restart — the first thing to try whenever the I/O LED is
anything but steady green, and it costs one click and no cable.

#### The fallback: stop the runtime

If the handover does not do it, stop the PLC runtime instead. The 750-8202 manual requires this,
because the runtime owns the K-bus — the firmware is built with `PTXCONF_CDS3_IODRVKBUS=y`.

:rotating_light: **A stopped *application* is not a stopped *runtime*.** `codesys.ps1 download
-Force -NoStart` leaves the application loaded but not running, and the K-bus driver belongs to the
runtime process, which is still up. Stop the service itself — the WBM's *PLC Runtime* page, or
`codesyscontrol` over SSH. Both are reversible.

The two are alternatives, not a sequence: `EnableIoCheck` is written by the running application, so
stopping the runtime is precisely what stops anything from writing it.

**Which runtime is selected does not matter.** `iocheckd` is a firmware-level service, started on
demand and bound to localhost, so I/O-CHECK behaves the same whether the controller is set up for
e!RUNTIME or, as the bench units are, for CODESYS Control for PFC200 SL.

### **Reading a module: what the pages mean**

Select a module in the node view, open its settings, and press **Read** — the status bar confirms
*"The parameters were successfully read from I/O module!"*, which on its own already tells you the
cable, the port and the K-bus handover are all working.

| Page | What is on it | Worth knowing |
|:--|:--|:--|
| *title bar* | order number, a one-line description, firmware version | **The description carries the module's measuring range** — `4AI RTD -30 °C - 150 °C`. Read it before anything else; it is what a saturated channel will be reporting. |
| **Common** | settings shared by all channels | On the 750-463 that is only the PSRR mode — 50 Hz here, which is right for Europe. |
| **Channel 1..4** | sensor type, connection, diagnosis, limits | The page that usually matters. See below. |
| **Scaling** | manufacturer versus user scaling, plus a **live Process value** per channel | The per-channel tabs are the fastest way to find out which terminal pair feeds which channel. |
| **Calibration** | manufacturer versus user calibration, and the **A/D raw value** | The raw value is upstream of all scaling, which makes it the one number that says whether the front end is converting at all. |

#### The channel page

A correctly set up Pt1000 channel on a 750-463 reads:

| Setting | Value |
|:--|:--|
| Sensor Type | `Pt1000 (IEC751)` |
| Type of Connection | `2-Wire` — greyed out, because the 463 does only 2-wire |
| Process Value Representation | `Two's Complement` — tenths of a degree, signed |
| SIEMENS Format | `Off` |
| Watchdog Timer | `On` |
| Average Value Filter | either; off is fine |
| Diagnosis: Measuring range violation | `On` |
| Diagnosis: Wire Break / Short-Circuit | **`Off` from the factory — turn it on** |
| Lower / Upper user limit | `-32767` / `32767`, i.e. not clamping anything |

:bulb: **Turn on wire break / short-circuit diagnosis before you diagnose anything else.** With it
off, an RTD channel with nothing on its terminals does not complain — it drives to the top of its
range and reports a temperature that is perfectly legal for a platinum sensor. With it on, the
module says so and lights the channel's status LED. It is one checkbox and a **Write**, and it
converts a silent failure into a loud one.

#### Reading the A/D raw value

The Calibration page's *A/D raw value* is the number the converter produced, before manufacturer
calibration and before scaling. Two things it tells you that nothing else can:

- **Does it move?** Short a channel's terminals and watch it. A channel that is measuring cannot
  ignore zero ohms — that is below the bottom of every range a 750-463 can hold. A raw value that
  does not budge is a front end that is not looking at its terminals.
- **Is it a number at all?** A value like `9999998976` is not a measurement, it is a sentinel. The
  arithmetic is exact: `9999998976 = 9765624 × 2^10`, the largest 32-bit float below 10^10, and
  precisely what you get by truncating the all-nines decimal **9,999,999,999** into a float. An
  all-nines sentinel means the module has no valid conversion to report.

:bulb: **Sane calibration values are evidence the module is not wiped.** Manufacturer gain `16380`
is within a whisker of 2^14 — unity in a fixed-point representation — with a small offset beside
it. A module that had been mis-flashed or had its memory corrupted would not still be holding
plausible factory calibration, so seeing this narrows the fault to the analog front end rather than
to the module's stored settings.

### **Related**

- [Reading a temperature sensor (Pt1000) with a WAGO RTD module](AnalogInputs/UsingRTDSensors.md)
- [`FB_INPUT_TEMPERATURE_RTD_MQTT`](FunctionBlocks/FB_INPUT_TEMPERATURE_RTD_MQTT.md)
- [Choosing and preparing your WAGO PFC device](WagoPfcPrep.md)
