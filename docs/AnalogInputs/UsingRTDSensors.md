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

| Reading | Means |
|:--|:--|
| ≈ ambient, one decimal, drifting slightly | Correct. The last digit always moves; that is what `PublishDeadband` is for. |
| Far out of range, `Fault` set | Open circuit. A lead is not in the terminal, or is in the wrong channel's terminal. |
| ≈ 0.0 °C and immovable | A short across the terminals, or a channel measuring resistance rather than temperature. |
| Plausible but wrong, roughly 2.6× the true value | **The channel is configured for Pt100 and a Pt1000 is connected.** This is the failure the block cannot detect for you — a wrong sensor type produces a believable number. WAGO-I/O-CHECK, or use the module variant that matches the sensor. |
| ≈ 0.26× the true value | The reverse: a Pt100 on a channel set to Pt1000. |

:bulb: **An unwired channel is a free reference.** On a 4-channel module with one sensor, the
other three channels sit at whatever the module reports for an open circuit — which tells you
exactly what a broken wire looks like on your hardware, without breaking anything.
