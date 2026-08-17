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
