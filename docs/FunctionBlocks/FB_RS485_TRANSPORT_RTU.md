## FB_RS485_TRANSPORT_RTU
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
Speaks Modbus RTU over the PFC's onboard serial port, using `SysCom` directly. It implements
`RS485Transport`, so [`FB_RS485_BUSCONTROLLER`](FB_RS485_BUSCONTROLLER.md) drives it without
knowing anything about framing, and a different Modbus implementation could be substituted
without touching the controller or any device block.

Supported function codes:

| Code | |
|:--|:--|
| 3 | read holding registers |
| 4 | read input registers |
| 6 | write single register |
| 16 | write multiple registers, up to 8 |

Anything else is **refused** by `Start` rather than framed as a guess. That matters: the version
this replaces built every frame from the read fields, so an FC6 write went out as *"write
register 0 with the value 0"* and the echoed reply was then parsed as though byte 2 were a
length.

### **Why this exists rather than a driver block**

`IoDrvModbus.ModbusRequest2` does not work on this hardware. Every reply arrives wrapped in
glitch bytes — a `00` as the slave's driver enables onto the undriven pair, another as it
releases. Measured across 34 consecutive bench captures: 34 leading nulls, 34 trailing nulls,
34 CRC-valid frames once trimmed, 0 CRC failures. The data was always perfect; the framing is
what an off-the-shelf request block objects to.

So this block frames the way RTU actually specifies — read until the line has been quiet for
`GapTime`, then let the CRC judge what is left:

1. Trim leading nulls.
2. Try the CRC at full length; if it fails, shorten by one byte and try again, up to three
   times. **Asking the CRC rather than assuming a trailing `00` is noise** matters because a
   frame whose CRC high byte is genuinely `00` turns up about once in 256, and blindly trimming
   it turned a good reply into a CRC failure.
3. Check the slave address, then the function code, then decode per function code — reads carry
   a byte count, writes echo the request and have none.

The full account is in
[Using Modbus RTU with the CODESYS 3S runtime](../RS485/UsingModbusRTU_CODESYS3S.md).

### **Why it does not always wait out the silence**

A frame whose CRC already checks out is complete by definition, so the block stops collecting
the moment step 2 succeeds rather than waiting for `GapTime` to expire. The silence timer stays
as the fallback for everything that does not frame cleanly — a partial reply, a burst of noise,
a slave that answers with something unparseable.

This is not a micro-optimisation. Every timer handshake costs a whole task cycle, so waiting out
a 50 ms gap costs several cycles whatever the baud rate. Measured on the bench over the same
30-second window, five contending devices, one physical meter:

| | 200 ms task, waiting for silence | 200 ms task | **50 ms task** |
|:--|--:|--:|--:|
| per step | 1.87 s | 1.30 s | **0.42 s** |
| per transaction | 5.00 s | 3.75 s | **0.53 s** |
| steps completed | 16 | 23 | **71** |

Two levers, and they multiply: not waiting out the silence took roughly a third off, and the task
interval took two thirds off what was left.

**The cost is a fixed number of task cycles, not a fixed time.** Per step it is about 6.5 cycles
at 200 ms and 8.4 at 50 ms — near enough the same handful of cycles either way, which is what
identifies the task period rather than the wire as the thing to change. An SDM220 read is about
100 ms of actual wire time at 9600 baud, so even at 50 ms there is still headroom in principle;
the returns are just smaller in absolute terms from here.

One consequence worth expecting rather than diagnosing: `StepsExecuted / Transactions` **falls**
when the bus gets faster — 2.7 at 200 ms, 1.4 at 50 ms. That is not batching breaking. Batching
only has something to batch when several of a device's register blocks come due in the same
grant, and a bus that keeps up with demand serves each one as it falls due instead.

### **The counters are the instrument**

There is no scope on most benches. These outputs are the substitute, and every completed step
lands in exactly one of `Ok`, `CrcFail`, `NoReply`, `ShortFrame`, `BadAddress`, `BadFunction`,
`BadEcho` or `Exceptions` — so they sum to the number of steps attempted.

:bulb: **`LeadNulls` and `TrailNulls` climbing in step with `Ok` is the normal healthy picture
on this hardware, not a fault.**

| Symptom | Reading |
|:--|:--|
| `NoReply` climbing, everything else at zero | Nothing is listening: wrong address, A and B swapped, or `serialmode RS485` never set on this controller. |
| `CrcFail` non-zero while `Ok` also climbs | Marginal wiring or a noisy line. Not a code problem. |
| `Exceptions` climbing | The slave answered and refused. A register-map problem, not a wiring one; `LastException` says which. |
| `BadEcho` climbing | A write was acknowledged with the wrong address or value. Never reported as success — a read-after-write must not publish a confirmation for a write that did not take. |

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌────────────────────────┐
   │ FB_RS485_TRANSPORT_RTU │
   ├────────────────────────┤
   │               PortOpen ├── BOOL
   │              PortError ├── BOOL
   │                     Ok ├── UDINT
   │                CrcFail ├── UDINT
   │                NoReply ├── UDINT
   │             ShortFrame ├── UDINT
   │             BadAddress ├── UDINT
   │            BadFunction ├── UDINT
   │                BadEcho ├── UDINT
   │             Exceptions ├── UDINT
   │          LastException ├── BYTE
   │              LeadNulls ├── UDINT
   │             TrailNulls ├── UDINT
   │            LastFailLen ├── UDINT
   │           LastFailAddr ├── BYTE
   │           LastFailFunc ├── BYTE
   │          LastFailBytes ├── STRING(120)
   └────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PortOpen` | BOOL | The serial port is open and usable. |
| `PortError` | BOOL | `SysComOpen2` failed. Nothing will be sent until `Reopen` is called. |
| `Ok` | UDINT | Replies accepted. Should climb steadily. |
| `CrcFail` | UDINT | Bytes arrived but the CRC over the trimmed frame was not zero. Marginal wiring rather than a code fault. |
| `NoReply` | UDINT | Nothing at all before the reply timeout. Wrong address, swapped A/B, or `serialmode RS485` never set. |
| `ShortFrame` | UDINT | Too few bytes to be any valid reply for the function code that was sent. |
| `BadAddress` | UDINT | A well-formed, intact frame from a different slave. |
| `BadFunction` | UDINT | Right slave, but a function code that was not the one asked for. |
| `BadEcho` | UDINT | A write was acknowledged with the wrong address or value. Never counted as success. |
| `Exceptions` | UDINT | The slave answered and refused. A register-map problem, not a wiring one. |
| `LastException` | BYTE | Modbus exception code from the most recent exception reply. |
| `LeadNulls` | UDINT | Replies that arrived with leading glitch bytes. Tracks `Ok` on this hardware; not a fault. |
| `TrailNulls` | UDINT | Replies that arrived with trailing glitch bytes. Tracks `Ok` on this hardware; not a fault. |
| `LastFailLen` | UDINT | How many bytes were in the buffer of the most recent reply that would not frame. Zero here with `CrcFail` climbing would be a contradiction; a small number is a truncated reply, a large one is two replies collected together. |
| `LastFailAddr` | BYTE | Slave address the failed exchange was addressed to. Without it the captured bytes are unattributable — a frame that looks like another device's traffic is exactly the case worth telling apart from a mangled reply. |
| `LastFailFunc` | BYTE | Function code of that exchange, for the same reason. |
| `LastFailBytes` | STRING(120) | The first 24 bytes as decimal numbers. A counter can say a reply did not check out; only the bytes can say whether it was half a reply, two replies, an echo of the request, or a mangled address — and those want different fixes. Published to `.../RS485/BUS_COUNTERS` by `PLC_PRG_RS485`, because reading it over an online session means having a working online session. |

### **Methods**

**`Init`** — Opens the serial port with these settings. Call once at startup, before the bus controller’s `Init`. Calling it again re-opens the port.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Port` | SysCom.SYS_COM_PORTS |  | Which serial port. Only `SYS_COMPORT1` is exposed by the PFC200 runtime. |
| `Baudrate` | UDINT |  | Bits per second. 9600 for every device this project has met. |
| `Parity` | SysCom.SYS_COM_PARITY |  | Parity, as a `SysCom.SYS_COM_PARITY` value. |
| `StopBits` | SysCom.SYS_COM_STOPBITS |  | Modbus specifies two stop bits with no parity, but every device tested here answers on one. Ask the device, not the standard. |
| `ReplyTimeout` | TIME |  | Nothing at all by now means no reply. Zero keeps the default of one second. |
| `GapTime` | TIME |  | Line quiet for this long ends a frame. Zero keeps the default of 50 ms. |

**`ReadBuffer`** — Where a read step’s registers landed. Valid only in the cycle `Service` returns `OK`.

**`Registers`** — How many words of `ReadBuffer` the last `OK` step filled. Zero after a write.

**`Reopen`** — Closes and re-opens the port on the next `Service`, clearing `PortError` — so a port that failed to open at boot can be retried from an online session without a download.

**`Service`** — Call every cycle. Drives the port and the exchange in flight, and returns `IDLE` / `BUSY` / `OK` / `FAILED`. `OK` and `FAILED` are each returned for exactly one cycle. The bus controller does this for you.

**`SetStopBitsRaw`** — Forces the raw SysCom stop-bit code, for a device whose framing the `SYS_COM_STOPBITS` enumeration does not name conveniently on this runtime. `Init` takes the enumeration and is the right way in for anything normal; this exists because framing is one of exactly two things that silence a device on a working pair — the other being the baud rate — so a routine that hunts for a device has to be able to sweep it, and the numeric codes are portable where the enumerator names are not. Takes effect on the next `Reopen` or `Init`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Raw` | BYTE |  | The SysCom stop-bit code to force. Numeric rather than an enumerator so a sweep can try codes it cannot name. |

**`Start`** — Begins one exchange. Returns FALSE if the port is down, an exchange is already in flight, or the function code is not one this transport implements.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `pStep` | POINTER TO RS485_Step |  | The exchange to carry. Copied on entry, so the caller may reuse its buffer. |
<!-- fb-interface:end -->

### **Code example**

- variables initiation:
```
RS485Transport : FB_RS485_TRANSPORT_RTU;
```

- Init call (called once during startup, before the bus controller's `Init`):
```
RS485Transport.Init(
	Port			:= SysCom.SYS_COM_PORTS.SYS_COMPORT1,
	Baudrate		:= 9600,
	Parity			:= SysCom.SYS_COM_PARITY.SYS_NOPARITY,
	StopBits		:= SysCom.SYS_COM_STOPBITS.SYS_ONESTOPBIT,
	ReplyTimeout	:= T#1S,
	GapTime			:= T#50MS
);
```

- Handing it to the bus controller, which then calls `Service` every cycle. **The transport
  instance needs no cyclic call of its own:**
```
RS485BusController.Init(Transport := RS485Transport, ...);
```

### **Notes**

- **COM1 is the only port the PFC200 runtime exposes.** COM2, COM3 and COM4 were all tried and
  none of them opens.
- **Modbus specifies two stop bits with no parity**, but every device met so far answers on one.
  Ask the device, not the standard.
- `Reopen()` closes and re-opens the port on the next `Service`, and clears `PortError` — so a
  port that failed to open at boot can be retried from an online session without a download.
- Timings are plain members rather than `FB_init` arguments on purpose. An existing `FB_init`
  argument changed from a script updates the declaration text while the compiler keeps reading
  the stored `InputAssignments`, so the PLC runs the old value with a clean build and a matching
  export. [CLAUDE.md](../../CLAUDE.md) has the detail.
