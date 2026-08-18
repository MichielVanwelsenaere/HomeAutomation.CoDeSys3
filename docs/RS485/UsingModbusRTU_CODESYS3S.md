## Using Modbus RTU with the CODESYS 3S runtime

### **Content**
This page describes adding a Modbus RTU device using the CODESYS 3S runtime.
In case a function block for your specific device is not present in this project yet, please consider reading the [RS485 tips and tricks](../FAQ/RS485_tips_and_tricks.md) page if this is your first time connecting an RS485 device.

### **Assign the PLC serial port to the PLC runtime**
In order to use the onboard PLC serial port from the PLC runtime this needs to be configured from the Web-Based Management tool, under *Ports and Services / Serial Interface*, by assigning the serial interface to the PLC runtime instead of the Linux console.

Note that it's necessary to reboot the controller after a change to this setting.

### **Setting the serial mode on the PLC**

Assigning the port to the runtime does **not** put it into RS485 mode. That is a separate step,
and it is required **once per controller**:

1. Open CODESYS
1. Connect to your PLC
1. Use the PLC shell to set the serial mode to RS485:

<img src="../_img/RS485_CODESYS3S_PLCShell.png" width="550">

The controller reboots afterwards and the setting survives it.

:rotating_light: **Do this even if the mode already reads RS485.** Explicitly setting it again
has fixed connectivity on a controller that reported the right mode and would not talk. Until it
is done the bus is simply silent — no error, no exception, nothing in any counter.

There is no IEC alternative: WAGO's `CmpPfcx00` library exposes LEDs, logging and error codes,
and nothing that reaches the serial mode. Treat it as commissioning, alongside setting the
device's Modbus address.

### **Required libraries**
Make sure the following libraries are present in the project:
```
SysCom
SysTypes2 Interfaces
```

`IoDrvModbus` is no longer used — see below.

### **How the project talks to the bus**

Three blocks, each with one job:

| | |
|:--|:--|
| [`FB_RS485_TRANSPORT_RTU`](../FunctionBlocks/FB_RS485_TRANSPORT_RTU.md) | Builds and judges Modbus RTU frames over `SysCom`. Implements `RS485Transport`. |
| [`FB_RS485_BUSCONTROLLER`](../FunctionBlocks/FB_RS485_BUSCONTROLLER.md) | Decides whose turn it is and runs one device's transaction at a time. |
| [device blocks](RS485Device_Interface.md) | Say what they want read or written, and interpret what comes back. |

`PLC_PRG_RS485` wires them together in `RS485_INIT` and calls the controller in `RS485_RUN`. A
worked example lives there.

### **How fast the bus goes, and what actually decides it**

The single biggest performance decision on this bus is **the `RS485` task's cycle
time**, not the baud rate. It is set to **50 ms**.

The reason is that one Modbus exchange costs a fixed number of task *cycles* -
measured at roughly 6.5 to 8.5 per step - rather than a fixed amount of time.
Sending, collecting, judging and the silence afterwards each need at least one
cycle, and several need a cycle to reset a timer before they can start counting.
So the whole exchange scales with the task period:

| `RS485` task | per step | per transaction |
|:--|--:|--:|
| 200 ms | 1.30 s | 3.75 s |
| **50 ms** | **0.42 s** | **0.53 s** |

An SDM220 read is about 100 ms of actual wire time at 9600 baud, so even at 50 ms
the bus spends most of its time waiting for the next cycle rather than for the
slave. Lowering it further would keep paying, in smaller absolute amounts.
[FB_RS485_TRANSPORT_RTU](../FunctionBlocks/FB_RS485_TRANSPORT_RTU.md) has the full
comparison, including what the transport itself contributes.

Two things make a short interval safe here, and both are worth checking before
copying the setting into an installation project:

- **`RS485` runs at priority 15**, the lowest of the five tasks in this project -
  below `MainTask` (4), `MqttCommunication` (5) and `HvacTask` (8). It yields to
  all of them, so polling a meter faster cannot delay a light or a valve.
- **Every task in this project has its watchdog disabled.** That is a pre-existing
  convention rather than anything to do with the interval, but it is the reason
  there is nothing to catch an overrun: a task that cannot keep up degrades
  quietly. If the interval is ever pushed below 50 ms, enable the watchdog first
  so the failure is loud.

:bulb: **`StepsExecuted / Transactions` falling is the bus getting faster, not
batching breaking.** It measures how many of a device's register blocks were due
in the same grant, so a bus that keeps up with demand serves each one as it falls
due and the ratio drops - 2.7 with a 200 ms task, 1.4 with a 50 ms one.

### **A device that ships on the wrong baud rate**

One bus has one baud rate, and not every device agrees to it out of the box. The DFRobot
SEN0492 rangefinder ships at **115200** with no switch to change it; this bus runs at 9600.
Until the sensor is moved, the two cannot talk at all — the sensor is not slow to answer, it
is inaudible.

The settings that matter live in ordinary holding registers, so they can be written over
Modbus like anything else. The catch is the chicken-and-egg: to tell a device to change its
baud rate you have to talk to it at the rate it is on now.

**The transport can be re-opened at a different rate at runtime**, which is what makes this
solvable from the PLC.
[`FB_RS485_TRANSPORT_RTU.Init`](../FunctionBlocks/FB_RS485_TRANSPORT_RTU.md) re-opens the
port when it is already open, so a startup sequence can drop the bus to the device's speed,
write the new setting, and bring it back:

```mermaid
flowchart LR
  A["bus at 9600<br/>probe 16#50"] -->|answers| E["done<br/>nothing to change"]
  A -->|silent| B["re-open at the next rate<br/>probe again"]
  B -->|silent| B
  B -->|answers| C["write 9600 into<br/>the device's baud register"]
  C --> D["re-open at 9600"]
  D --> E
```

`PLC_PRG_RS485` does exactly this in `RS485_RUN`, before it lets the bus controller start.
Three things about it are deliberate:

- **It scans rather than assumes.** The first version wrote the new baud rate blind at the
  documented factory speed. When the device stayed silent afterwards there was no way to tell
  whether the write had missed or had landed and moved the device somewhere unexpected —
  which is a worse position than before. It now probes first and writes only to a device that
  has actually answered.
- **It tries the bus speed first.** A device that is already commissioned answers on the first
  probe and the sequence ends there, costing one Modbus exchange.
- **It holds the bus controller off.** At any speed but 9600 nothing else on the bus can be
  addressed either, so nothing is polled until it finishes.

:rotating_light: **The reply to a baud-rate write cannot be heard.** The device changes speed
the moment it accepts the write, so its acknowledgement comes back at the new rate and the
old one is deaf to it. A failed write is therefore the *expected* result of a successful one,
and nothing may retry on it — a retry loop here spins forever on a device that already obeyed.

The sweep covers **framing as well as rate**, because those are the two things that silence a
device on a working pair. Stop bits are set through
[`FB_RS485_TRANSPORT_RTU.SetStopBitsRaw`](../FunctionBlocks/FB_RS485_TRANSPORT_RTU.md) using the
numeric SysCom code rather than the `SYS_COM_STOPBITS` enumerators, because the enumerator names
are not portable across runtimes and a hunt has to be able to try codes it cannot name.

The result is published **retained** to `.../RS485/SEN0492_COMMISSION`:

```
probes=1 found=9600/255 maxrx=9 at=9600/255 written=FALSE
```

That channel matters more than it looks. The obvious place to read a commissioning result is an
online debug session, and on this bench that is the least reliable thing in the chain — the
runtime drops the session long before it drops MQTT. A result nobody can read is not a result.

:rotating_light: **When a sweep finds nothing, suspect the wiring before the settings — and the
byte count tells you which.** A bus with nothing on it returns zero bytes at every setting. A
device that is present but unreadable returns *something*: noise, partial characters, the
leading null this hardware produces as a driver enables. `CommissionMaxRx` and
`CommissionMaxRxBaud` record the largest byte count and where, and `LeadNulls` climbing while
`Ok` stays at zero says the same thing.

That is exactly how the SEN0492 was diagnosed. It was silent through a sweep of every rate the
register can select, while `LeadNulls` moved — so it was powered and talking, and only the
polarity of the pair could turn that into nothing framable. **A and B were swapped.** Once
reversed, the sweep found it on the first probe, at 9600 with ordinary framing, and `maxrx`
became 9 — exactly the length of the reply it had been trying to send all along.

### **Why this project frames its own RTU rather than using a driver**

Worth knowing before anyone tries to simplify it back.

`IoDrvModbus.ModbusRequest2` does not work on this hardware. Every reply from a slave arrives
wrapped in glitch bytes:

```
00 | 01 04 04 43 69 69 78 10 6E | 00
     └────── a perfect Modbus reply ──────┘
```

A `00` as the slave's driver enables onto the pair and another as it releases, because the line
is undriven between frames. Measured across 34 consecutive captures on the bench: **34 leading
nulls, 34 trailing nulls, 34 CRC-valid frames once trimmed, 0 CRC failures.** The data is fine;
the framing is what an off-the-shelf request block objects to.

`ModbusRequest2` rejects anything that is not a bare frame. WAGO's e!COCKPIT
`FbMbMasterSerial` frames on the 3.5-character silence that RTU actually specifies and discards
those bytes silently, which is why no e!COCKPIT installation ever saw this.

So `FB_RS485_TRANSPORT_RTU` does what RTU specifies: read until the line has been quiet, trim,
and let the CRC decide whether what remains is real. Its `LeadNulls` and `TrailNulls` counters
climbing in step with `Ok` is the **normal healthy picture** on this hardware, not a fault.

Whether `ModbusFB.ClientSerial` tolerates the same bytes has not been established — that is
[#181](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/issues/181). Because the
protocol sits behind `RS485Transport`, adopting it would be an adapter rather than a redesign.

### **e!COCKPIT**

This project is CODESYS-first, and the e!COCKPIT-specific code that used to sit commented out in
`PLC_PRG_RS485` has been removed rather than lost: `WagoAppPlcModbus.FbMbMasterSerial` belongs
behind the same `RS485Transport` interface, as a second implementation. Every RS485 device
function block in this project is independent of which one is in use.
