## FB_RS485_COMMISSIONER
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**

Puts devices **onto** the bus before anything tries to poll them. One bus has one baud rate,
and not every device agrees to it out of the box — a device that disagrees is not slow to
answer, it is inaudible.

**It knows nothing about what is on the bus.** Before the bus controller is allowed to start,
this block asks every registered device one question —
[`RS485Device.GetCommissioning`](#the-device-answers-for-itself) — and the device answers with
the address to probe, the register to write, the value that puts it on this bus, and the rates
worth trying. A device that answers `FALSE`, which is nearly all of them, costs one method call
at startup.

That division is the whole point. The rate a register wants, the code it wants it in, whether the
setting survives a power cycle — all of that is device knowledge and lives in the device's block.
What is left here is the part that is the same for every device: sweep, probe, write, put the bus
back, publish what happened.

:bulb: **It holds the bus off while it runs.** A device being hunted for at some other baud rate
makes the whole pair unusable for as long as that takes, so the scheduler must not run until
`Done`. With nothing to commission, `Done` is TRUE on the first cycle.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌───────────────────────┐
   │ FB_RS485_COMMISSIONER │
   ├───────────────────────┤
   │                  Done ├── BOOL
   │                 Asked ├── INT
   │             Requested ├── INT
   │               Written ├── INT
   │                Probes ├── UDINT
   │            LastReport ├── STRING(255)
   └───────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Done` | BOOL | Nothing left to commission, and the bus is back on the settings `Init` gave the transport. **The scheduler must not be called until this is TRUE.** TRUE on the first cycle when no device asked for anything, and TRUE immediately if the block was never initialised — a commissioner nobody configured must not be able to silence a working bus. |
| `Asked` | INT | Devices asked whether they need commissioning. Should equal the bus controller's registered count once `Done`; anything less means the sweep stopped early. |
| `Requested` | INT | How many of them said yes. Normally 0 on a bus of ordinary devices. |
| `Written` | INT | How many were actually changed. A device found already on the bus rate is *not* counted — that is the normal outcome on every boot after the first. |
| `Probes` | UDINT | Modbus exchanges spent hunting, across all devices. One means the first device answered at the first setting tried; a large number means something was swept and not found. |
| `LastReport` | STRING(255) | The last result published, kept where an online session can read it without waiting for the broker. Same text as the retained topic. |

### **Methods**

**`Init`** — Wires the commissioner to the bus it is to look after. Call once at startup, **after** every device has been registered with the bus controller — the device list is read back through the controller, so there is only ever one of it.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Transport` | RS485Transport |  | The bus. Re-tuned during a sweep and restored afterwards, which is why this is the transport interface rather than a port number: nothing here has to know the port, parity or buffer size. |
| `pController` | POINTER TO FB_RS485_BUSCONTROLLER |  | Bus controller holding the registered devices. Reading the same list the scheduler serves is what stops a device being commissioned but not polled, or polled but never commissioned. |
| `BusBaudrate` | UDINT |  | What this bus runs at. Passed to each device so it can encode that rate the way its own register expects, and so a device already on it is left alone. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `MqttPublishPrefix` | POINTER TO STRING |  | Topic prefix the device's own `ReportTopic` is appended to. |
| `Enable` | BOOL |  | FALSE skips commissioning entirely and releases the bus on the first cycle. The switch to reach for if a sweep ever misbehaves on a bus that was working. |
<!-- fb-interface:end -->

### **Code example**

One instance per bus, in the program that owns the bus. Registration first, commissioning
second, and the scheduler only once commissioning has finished:

```
(* in RS485_INIT, after every RegisterDevice call *)
RS485Commissioner.Init(
	Transport			:= RS485Transport,
	pController			:= ADR(RS485BusController),
	BusBaudrate			:= BUS_BAUDRATE,
	pMqttPublishQueue	:= ADR(MqttVariables.fbMqttPublishQueue),
	MqttPublishPrefix	:= ADR(MqttVariables.MqttPubRS485Prefix),
	Enable				:= RS485Variables.RS485_COMMISSION_ON_BOOT
);
```

```
(* in RS485_RUN *)
IF NOT RS485Commissioner.Done THEN
	RS485Commissioner();
ELSE
	RS485BusController();
END_IF
```

### **The device answers for itself**

`RS485Device.GetCommissioning` is the whole interface between the two halves. It is asked once,
at startup, and never by the scheduler:

```
METHOD GetCommissioning : BOOL
VAR_INPUT
	BusBaudrate	: UDINT;
	pRequest	: POINTER TO RS485_CommissionRequest;
END_VAR
```

Return FALSE and nothing happens. Return TRUE and fill `pRequest^`:

| Field | What it is for |
|:--|:--|
| `DeviceId` | Address the device answers on. Its own — a device that has to be hunted for is found by rate and framing, never by walking addresses. |
| `ProbeFunction` / `ProbeAddress` / `ProbeQuantity` | A read that always answers. The reply is never decoded; it only has to arrive. |
| `WriteFunction` / `WriteAddress` / `WriteValue` | The correction. **The device encodes the value**, because only the device knows whether its register takes a rate, a code or an index. |
| `Bauds` / `BaudCount` | Rates to try, in the order worth trying them. Put the bus rate first and an already-commissioned device costs one exchange. |
| `StopBits` / `StopCount` | Framing codes to try. `255` leaves the port's own framing — the ordinary case; `1..3` force the raw SysCom code. |
| `ReportTopic` | Topic suffix for the retained result. Empty publishes nothing. |

A device that cannot be told to use this bus rate at all should return FALSE. Moving it to a
setting it can express but the bus does not use leaves it just as inaudible, at a setting nobody
will go looking for.

The worked example is
[`FB_RS485_DFROBOT_SEN0492_MQTT`](FB_RS485_DFROBOT_SEN0492_MQTT.md), which ships at 115200 with
no switch on it. Its baud register takes a *code*, and the code is the index into its own table
of rates — so one table in that block answers both "which rates can it use" and "what do I write
for this one".

### **What it publishes**

One retained message per device that asked for commissioning, to
`<MqttPubRS485Prefix><ReportTopic>`:

```
probes=1 found=9600/255 maxrx=9 at=9600/255 written=FALSE
```

| Field | Reads as |
|:--|:--|
| `probes` | Modbus exchanges spent on this device. 1 means it answered at the first setting tried. |
| `found` | Rate and framing where it answered, `0/0` if it never did. |
| `maxrx` | Most bytes seen in any one reply window, and `at` where. |
| `written` | Whether the register was actually written. FALSE is the normal steady state. |

:bulb: **`maxrx` is the field to read when nothing was found.** A bus with nothing on it returns
zero bytes at every setting. A device that is present but unreadable returns *something* —
noise, partial characters, the leading null this hardware produces as a driver enables. Bytes
arriving that never frame mean the device is powered and talking, and something below Modbus is
wrong: **suspect the wiring, and check A and B before any Modbus setting.** That is exactly how
the SEN0492 was diagnosed — silent through a sweep of every rate its own register can select,
with `LeadNulls` climbing, because the pair was reversed.

Retained, and deliberately so. The obvious place to read a commissioning result is an online
debug session, and on this hardware that is the least reliable thing in the chain — the runtime
drops the session long before it drops MQTT. A result nobody can read is not a result.

### **Why the write is never retried**

:rotating_light: **The acknowledgement comes back at the new setting, and this end cannot hear
it.** A device changes speed the moment it accepts the write, so a failed write is the *expected*
result of a successful one. A retry loop here spins forever on a device that has already obeyed.

The same reasoning is why a device is probed before anything is written to it. An earlier version
wrote the new rate blind at the documented factory speed; when the device stayed silent
afterwards there was no way to tell whether the write had missed or had landed and moved the
device somewhere unexpected — which is a worse position than before it ran. Nothing is written
now into a bus whose contents have not been confirmed.
