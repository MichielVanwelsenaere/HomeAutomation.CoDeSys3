---
name: test-plc-logic
description: Exercise the PLC's actual behaviour on real hardware - lights, pushbuttons, covers, dimmers and the HVAC chain - by commanding it over MQTT and asserting the result on the broker and in the running application. Use after a download, when asked whether some logic still works, when a refactor touched behaviour the compiler cannot check, or when a Home Assistant entity is not doing what it should.
---

# Test the PLC logic on hardware

The compiler is the only automated gate this project has. It cannot tell you
whether pressing a button turns on a light, or whether a thermostat opens a valve —
[CODESYS simulation cannot run this project at all](../../../CLAUDE.md), so *behaviour
is only observable on a real PFC*.

Two ways in, and the difference matters:

| | What it proves | Use it for |
|:--|:--|:--|
| **MQTT** — `mosquitto_pub` to `Devices/PLC/Lab/In/...` | The whole path a user or Home Assistant takes: broker → subscription → callback → logic → publish | Anything reachable from Home Assistant. **Prefer this.** |
| **Online writes** — `write` in a download spec | Only the logic. Bypasses MQTT entirely. | Inputs MQTT cannot reach: a hardware input, a sensor-health flag |

Prefer MQTT. A test that only writes variables will pass while the subscription is
broken, which is a failure mode this project has actually had.

## Before you start

```powershell
./tools/ai/codesys.ps1 doctor            # mosquitto_sub present?
(Test-NetConnection 10.101.1.232 -Port 11740).TcpTestSucceeded   # runtime up?
./tools/ai/Mqtt-Snapshot.ps1 -Topics 'Devices/PLC/Lab/availability' -Seconds 3
```

**`availability` must read `online`.** If it reads `offline`, or port 11740 is
closed while ping succeeds, the runtime is down — not your credentials, and not the
network. On the bench unit that usually means **the two-hour demo licence expired**;
it needs a restart, and a login failure mid-download is a symptom of it happening
during the download rather than a cause to go hunting for passwords.

Take a baseline before changing anything, so you can diff at the end:

```powershell
./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/before.txt
```

## Watching what happens

Retained snapshots show *state*; they cannot show an event that was published and
superseded. To watch live traffic while you command something:

```powershell
./tools/ai/Mqtt-Snapshot.ps1 -Watch -Seconds 30
```

Run that in one shell (or background it) and publish from another. Pushbutton
events in particular are only visible this way.

## Commanding it

Topic roots come from `GVL_MQTT` (`MqttMain` + `MqttType` + `MqttDevice`), so
everything below assumes `Devices/PLC/Lab/`. Change `MqttDevice` and it all shifts.

```powershell
$mp = 'C:\Program Files\mosquitto\mosquitto_pub.exe'
$B  = '10.101.1.11'
function Cmd($topic, $payload) { & $mp -h $B -t "Devices/PLC/Lab/In/$topic" -m $payload -q 2 }
```

| What | Command topic (under `In/`) | Payload | State topic (under `Out/`) |
|:--|:--|:--|:--|
| Binary light | `DigitalOutputs/fbDoBin001` | `TRUE` / `FALSE` | `DigitalOutputs/fbDoBin001` |
| Bistable light | `DigitalOutputs/fbDoBistable001` | `TRUE` / `FALSE` | `DigitalOutputs/fbDoBistable001` |
| Cover | `Covers/fbDoCover001` | `OPEN` / `STOP` / `CLOSE` | `Covers/fbDoCover001` |
| Cover with position | `Covers/fbDoCover002` | `OPEN` / `STOP` / `CLOSE` | `Covers/fbDoCover002` |
| ... its position | `Covers/fbDoCover002/POSITION` | `0`..`100` | `Covers/fbDoCover002/POSITION` |
| Dimmer | `Dimmers/fbAoDimmer001/...` | see the block's page | `Dimmers/fbAoDimmer001/OUT`, `/Q` |
| Thermostat mode | `HVAC/fbThermostat2/MODE` | `off` / `heat` / `auto` | `HVAC/fbThermostat2/MODE` |
| Thermostat setpoint | `HVAC/fbThermostat2/DESIRED_TEMP` | e.g. `22` | `HVAC/fbThermostat2/DESIRED_TEMP` |

Two things the thermostat does that will confuse you if you do not expect them:

- **The setpoint is clamped** to `MIN_TEMP`..`MAX_TEMP` (17..24 on this project) and
  the clamped value is echoed back. Publishing `30` and reading back `24.0` is
  correct behaviour, not a bug.
- **The payload must be numeric**, checked with `IS_CC` against `0123456789.`. A
  payload of `22.0 C` is silently ignored — no error anywhere.

## Asserting the result

Reading the broker proves what the outside world sees. Reading the application
proves *why*. Do both: a download spec's `expect` fails the run on mismatch, which
is what makes this a test rather than a look around.

```powershell
./tools/ai/codesys.ps1 download -Force -Ip 10.101.1.232 -Spec .ai/edits/<name>.json
```

`download` re-downloads and restarts the application, so use it to *arrive* at a
known state. To assert against an application that is already running without
disturbing it, keep the spec to `read` and `expect` only — no `write` — and note
that the download still restarts it. There is no attach-only task; if you need one,
that is a `codesys_task.py` addition, not a workaround.

Spec shape (see `tools/ai/codesys_task.py` `run_steps`):

```json
{"steps": [
  {"label": "why this step exists",
   "write":    {"PRG_HVAC.fbThermostat2.DESIRED_TEMP": "22"},
   "delay_ms": 2000,
   "expect":   {"PRG_HVAC.fbPump2Collector.VALVE[1]": "TRUE"},
   "read":     ["PRG_HVAC.fbPump2Collector.PUMP"]}
]}
```

**`expect` compares typed literals.** `read_value` returns `UDINT#0`, `INT#8`,
`TIME#20s`, `BYTE#1`, `'a string'` — not `0`, `8`, `20s`, `16#01`. Write the
expectation the way the PLC spells it, or the step fails for the wrong reason.

Two that catch people: a `BYTE` comes back **decimal** (`BYTE#1`), not as the hex
you probably wrote it as in the declaration; and an enum comes back fully
qualified (`E_RS485_EASTRON_SDM_DEVICE.SDM220`). When in doubt put the variable in
`read` first, run once, and copy the spelling out of the report into `expect`.

Finish with a diff, which catches damage you were not looking for:

```powershell
./tools/ai/Mqtt-Snapshot.ps1 -Out .ai/mqtt/after.txt
./tools/ai/Mqtt-Snapshot.ps1 -Diff .ai/mqtt/before.txt,.ai/mqtt/after.txt
```

`IDENTICAL` after a pure refactor is the strongest result available here. After a
behavioural test, expect exactly the topics you touched to have changed and
**nothing else** — an unexpected entry in `GONE` means a Home Assistant entity just
lost its discovery config.

---

# The four suites

## 1. Lights — binary and bistable outputs

The straightforward one, and worth running first because it proves the whole MQTT
path end to end before you debug anything harder.

1. Command on: `Cmd 'DigitalOutputs/fbDoBin001' 'TRUE'`
2. Within a second or two, `Out/DigitalOutputs/fbDoBin001` should read `TRUE`.
3. Command off and confirm it returns to `FALSE`.
4. Repeat for `fbDoBistable001`.

Assert in the same run that the output really moved, not just the topic:

```json
{"expect": {"PRG_MAIN.fbDoBin001.OUT": "TRUE"}}
```

**If the state topic never changes:** the block is not subscribed. Check
`InitMqttDone` on the instance, and that its body is being called cyclically —
self-wired blocks wire themselves on their *first cyclic call*, so an instance whose
body never runs is silently absent from Home Assistant.

**`fbDoBistable001` will look broken on a bench and is not.** It drives an
impulse relay: `OUT` is a short pulse to the coil (`OUT := HoldTimer.Q`) and the
state it publishes is `FEEDBACK` — the relay's own contact, read back from an input.
With no relay wired, pulsing the coil changes nothing observable, so the state topic
stays `FALSE` however many commands you send. To prove the *subscription* works here
you have to read `MqttHighRequest` or the hold timer inside the block; the broker
cannot tell you. Do not record this as a failure without saying which half was
tested.

**Both of these announce as `light`, not `switch`.** If Home Assistant shows
`switch.` entities, `EntityType` was lost on the declaration; the retained
`homeassistant/light/..._fbDoBin001/config` will have been orphaned.

## 2. Pushbuttons — hardware in, MQTT out

Pushbuttons are **inputs**. There is nothing to command: the block publishes when
the physical button changes, and the events are not retained, so a snapshot will
never show them. This suite needs either a finger or a forced input.

**With hardware:** start `-Watch`, press the button on the 750-440 module, and
confirm events appear under
`Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/fbDiPb001`.

**Without:** force the digital input in a spec and read the block's outputs. The
pushbutton block distinguishes a short press from a long one, so hold the input
across a delay long enough to cross that threshold:

```json
{"steps": [
  {"write": {"DI_001": "TRUE"}, "delay_ms": 150,
   "read":  ["PRG_MAIN.fbDiPb001.P_SHORT", "PRG_MAIN.fbDiPb001.P_LONG"]},
  {"write": {"DI_001": "FALSE"}, "delay_ms": 200,
   "read":  ["PRG_MAIN.fbDiPb001.P_SHORT"]}
]}
```

Substitute the real input variable — check what `fbDiPb001` is actually wired to
in `READ_PUSHBUTTONS` rather than trusting `DI_001` here.

**A written input may be overwritten.** If the program assigns that variable every
cycle from the bus, a one-shot write lasts one cycle. If the value will not stick,
say so and press the button instead — do not report a pass you did not get.

Note that `fbDiPb001.P_LONG` drives the cover in `MOVE_COVERS`, so a long press
here is also a cover test.

### The position-capable cover

`specs/cover-position.json` is the whole test: nine steps, `OPEN` → `STOP` → `CLOSE`
→ end stop → 60%, asserting the **coils** as well as the block outputs at every step.

```powershell
./tools/ai/codesys.ps1 download -Force -Address 00E8 -Spec .claude/skills/test-plc-logic/specs/cover-position.json
```

`fbDoCover002.MU` and `MD` are wired to `DO_005` and `DO_006` on the second
750-540, so the LEDs on that module are the test you can watch from across the room.
Read both the coil and the block output, never just one: **the two disagreeing is the
failure worth catching** — a block that believes it is driving while nothing reaches
the module. That has happened here twice, once because two tasks were writing the
same coil and once because a library block was simulating a position without ever
energising an output.

The last four steps are the ones worth keeping: they **lie to the block** — write
`PositionReal := 80.0` while the cover sits at the bottom — and then assert that a
full `CLOSE` still drives for the whole travel time and finishes referenced at 0.
That is the drift case a time-based cover cannot detect for itself, and the reason
a full command must ignore the estimate: a run computed from a wrong estimate ends
in the wrong place and leaves the estimate wrong. Healing only `T_EndStop / T_Travel`
per command — 10% at the defaults — is what the block did before, and it looked
fine on every test that did not lie to it first.

Step one also asserts `PublishedPosition = BYTE#1` at rest, not 0: an unreferenced
0 makes Home Assistant disable the close button, which is the command that would
have re-referenced the cover.

Three specific traps in this block, all of which produced a *plausible* cover:

- **A restart must move nothing.** If the first read shows a coil on or a position
  climbing before anything was commanded, the block is treating its default target as
  a request. On a building that is every shutter moving after a power cut.
- **A full open must reach 100 and say `OPEN`.** Stopping at 98 with `PositionKnown`
  FALSE means the arrival tolerance is being applied to an end stop, so the estimate
  never recalibrates.
- **`STOP` must not be a pause.** Read the position twice, seconds apart, after a
  stop: if it resumes, the target was not dragged to where the cover stood.

The position path cannot be driven from a download spec - a spec writes variables,
not MQTT - so drive it from the broker and watch the cover's own topics:

```powershell
mosquitto_pub -h 10.101.1.11 -t Devices/PLC/Lab/In/Covers/fbDoCover002/POSITION -m 35 -q 2
mosquitto_sub -h 10.101.1.11 -v -t 'Devices/PLC/Lab/Out/Covers/fbDoCover002/#' -W 22
```

A healthy run steps in `PublishStep` increments while travelling and lands on the
exact value when movement ends:

```
58  CLOSING  53  48  43  38  STOPPED
```

:bulb: **The cover subscription is `MqttSubCoverPrefix` + `#`.** A `+` would deliver
the command topic and silently swallow `/POSITION`, one level below it - which looks
exactly like a block that ignores the slider.

## 3. HVAC — thermostat → valve → pump → burner

The chain, and the one worth understanding before testing:

```
thermostat OUT  →  collector THERMOSTAT[n]  →  VALVE[n]  →  PUMP  →  fbPump2  →  HEAT_REQUEST  →  burner
                                     ↑               (after ValveCycleTime)      (own min run / run-on)
                                     └── PUMP_MIN_ONTIME_ACTIVE ───── MIN_ONTIME_ACTIVE ─┘
```

That feedback arrow is the interlock: while the pump is running out its minimum
on-time the collector holds the circuits that were flowing open, so the pump is
never left turning against a shut manifold. It has its own spec below.

`fbThermostat2` drives circuit 1 (`Radiator 1`, `DO_006`), `fbThermostat3`
drives circuit 2 (`Radiator 2`, `DO_007`). Circuits 3-8 are unwired: their valves
stay closed and they announce no Home Assistant entity.

### Two things will stop you cold

**The sensor gate.** `SensorFault` is `NOT SENSOR_VALID OR MEASURED_TEMP <= -50 OR
>= 80`, and on a fault `OUT` is forced `FALSE` — deliberately, because the
alternative on a heating system is calling for heat forever. `SENSOR_VALID` comes
from the 1-Wire multisensor's `DataAvailable AND NOT Error`.

On the bench unit that sensor is not delivering, so **all three thermostats sit at
`/FAULT TRUE` and no MQTT command can make one call for heat.** Check first:

```
Devices/PLC/Lab/Out/HVAC/fbThermostat2/FAULT   → must be FALSE to proceed
```

If it is `TRUE`, either fix the sensor — the commented-out `RegisterDevice` in
`RS485_INIT` is the first place to look — or force it for the test:

```json
{"write": {"GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01.DataAvailable": "TRUE",
           "GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01.Error": "FALSE",
           "GVL_RS485.FB_RS485_1WIRE_MULTISENSOR_01.TEMPERATURE": "18.0"}}
```

Whether that sticks depends on whether the RS485 block writes those outputs every
cycle. **Verify it stuck** by reading `fbThermostat2.SENSOR_VALID` back before
concluding anything about the valve.

**The pump is slow on purpose.** `ValveCycleTime` is `T#3M`: the pump only starts
three minutes after heat is first requested, so a valve can open fully before there
is flow. `fbPump2` then has its own minimum run and run-on times (2 min / 1 min),
so it will not stop the moment demand goes away. A test that waits two seconds and
reports "pump did not start" is measuring the wrong thing.

That run-on is also why **a valve does not close the instant its thermostat is
satisfied.** While `fbPump2.MIN_ONTIME_ACTIVE` is set, the collector holds the
circuits that were flowing open — so a valve still reading `TRUE` seconds after you
commanded `MODE off` is the interlock working, not a stuck valve. Read
`fbPump2.PUMP` before calling it a fault.

**Setpoint and mode are PERSISTENT RETAIN, so another thermostat may already be
asking for heat.** On the first run here, forcing the sensor healthy immediately put
`fbThermostat3` into demand — it still held `MODE heat` and a setpoint of 18.5 from
a previous session, and 18.0 measured is below that. `HeatRequest TRUE` before you
have commanded anything is that, not a bug. Read every thermostat's `/MODE` and
`/DESIRED_TEMP` before concluding a valve opened on its own.

**Do not shorten these timings in the source to speed a test up.** It does not work:
an existing `FB_init` argument changed from a script updates the declaration text
while the compiler keeps reading the old `InputAssignments`, so the PLC runs the old
value with a clean build and a matching export
([CLAUDE.md](../../../CLAUDE.md) has the detail). It is also the wrong place — 5-second
valve travel in source can reach an installation with real pipes.

**Write the members at runtime instead**, which is what
`specs/hvac-fast-chain.json` does:

```json
{"write": {"PRG_HVAC.fbPump2Collector.ValveCycleTime": "TIME#5S",
           "PRG_HVAC.fbPump2.MIN_ONTIME": "TIME#10S"}}
```

They are plain `VAR` members that only `FB_init` assigns, so the write sticks for the
life of the session. Verified: the whole chain then runs in about 15 seconds — valve
open at t+3s, pump and burner by t+17s — against ten minutes at production timings.

Either way, **read `ValveCycleTime` off the PLC and time your waits by what it
actually says.** A 3-minute delay mistaken for 5 seconds looks exactly like a dead
pump.

### The test

1. **Establish the sensor is trusted.** `/FAULT` must be `FALSE`.
2. **Ask for heat.** With `MEASURED_TEMP` around 18:
   ```powershell
   Cmd 'HVAC/fbThermostat2/MODE' 'heat'
   Cmd 'HVAC/fbThermostat2/DESIRED_TEMP' '22'
   ```
   18 is below 22 − hysteresis, so the thermostat should call for heat.
3. **Thermostat picks it up** — within a cycle or two:
   `Out/HVAC/fbThermostat2` → `TRUE`, `/MODE` → `heat`, `/DESIRED_TEMP` → `22`.
4. **Valve opens immediately** — the collector assigns `VALVE[i] := THERMOSTAT[i]`
   with no delay: `Out/HVAC/fbPump2Collector/Valves/VALVE_1` → `TRUE`.
   `VALVE_2` must stay `FALSE`: circuit 2 has its own thermostat, and a valve
   opening on its own would be a real bug.
5. **Pump starts after `ValveCycleTime`.** Wait past three minutes, then
   `Out/HVAC/fbPump2` → `TRUE`. Read `fbPump2Collector.PUMP` and `PumpDelay.Q`
   too — they tell you whether you are early or actually broken.
6. **Burner follows the pump:** `fbPump2.HEAT_REQUEST` → `Out/HVAC/fbBurnerGas`.
7. **Reverse it.** `Cmd 'HVAC/fbThermostat2/MODE' 'off'` → thermostat `FALSE`.
   The pump lingers for its minimum cycle, and `VALVE_1` **stays `TRUE` while it
   does** — the interlock. Both then clear, valve after pump. Confirm they *do*
   rather than assuming, and see the interlock spec below for the version of this
   with assertions on it.

### The valve/pump interlock — `specs/hvac-valve-pump-interlock.json`

The one HVAC test that is a **regression test** rather than a walk through the
chain, and the only one that fails on purpose against older code.

```powershell
./tools/ai/codesys.ps1 download -Force -Address 00E8 `
    -Spec .claude/skills/test-plc-logic/specs/hvac-valve-pump-interlock.json
```

What it pins down: `fbPump2` holds its output for `MIN_ONTIME` after `IN` drops, so
withdrawing demand does not stop the pump. The collector used to close every valve
in that same cycle, leaving the pump turning against a shut manifold. Step 5 is the
assertion — pump `TRUE`, `bHeatRequest` `FALSE`, and `VALVE[1]` **still `TRUE`** —
and it reads `FALSE` on the code before `PUMP_MIN_ONTIME_ACTIVE` was wired.

Three things about it are deliberate and easy to undo by accident:

- **`MIN_ONTIME` (20 s) is set longer than `ValveCycleTime` (5 s).** That is the
  configuration where the fault appears. At the production values — 2 min against
  3 min — the pump stops before the valves finish closing anyway, so the same test
  passes on broken code. **A test at production timings proves nothing here.**
- **Thermostats 1 and 3 are forced off first.** Their mode and setpoint are
  PERSISTENT and they share the sensor, so either may already be demanding from a
  previous session. An open `VALVE[2]` gives the pump a real path and masks
  precisely what step 5 looks for.
- **Step 7 matters as much as step 5.** The interlock re-opens valves, so a latch —
  valves held open for ever, pump never permitted to stop — is the failure the fix
  itself could introduce. Step 7 waits the minimum on-time out and asserts the pump
  stops *and* the valve then closes. It cannot latch, because `bHeatRequest` is
  built from `THERMOSTAT` and not from `VALVE`, but the test proves that rather than
  trusting it.

The commanded valve state is what this asserts, which is the honest limit: a bench
has no manifold, so nothing here measures real valve travel. `ValveCycleTime`
describes a valve **opening** and no block models how long one takes to shut, so on
real hardware wire the interlock *and* fit a differential bypass.

### Also worth asserting

- **Fail-safe.** Set `SENSOR_VALID` false mid-demand and confirm `OUT` drops and
  `/FAULT` goes `TRUE`. This is the branch that matters most on a heating system
  and the easiest to break silently in a refactor.
- **The clamp.** Publish `30` to `DESIRED_TEMP`; expect `24.0` echoed back.
- **The eight valve topics all exist**, even for unwired circuits — the collector
  publishes all eight on startup. Losing `VALVE_3..8` from the broker would mean the
  startup publish loop broke.

## 4. RS485 — the Modbus bus

The only suite where the *bus* is the thing under test rather than a device on it.
It needs no MQTT at all for the interesting parts, because the bus controller and
the transport both publish their state as ordinary outputs.

### The counters are the instrument

There is no scope on this bench. `FB_RS485_TRANSPORT_RTU`'s outputs are what you
have instead, and every completed step lands in exactly one of them, so they sum
to the number of steps attempted:

| Counter | Reading it |
|:--|:--|
| `Ok` | Climbing steadily is the whole point. |
| `LeadNulls`, `TrailNulls` | **Should track `Ok` almost exactly.** This hardware wraps every reply in glitch bytes; that is normal, not a fault. See `docs/RS485/UsingModbusRTU_CODESYS3S.md`. |
| `CrcFail` | Should be 0. Non-zero with `Ok` also climbing means marginal wiring, not a code bug. |
| `NoReply` | The slave is absent, at the wrong address, or A/B are swapped. |
| `BadAddress` | A well-formed frame from somebody else, or a mis-framed reply. |
| `BadEcho` | A write was acknowledged with the wrong address or value. Never treated as success. |
| `Exceptions` + `LastException` | The slave answered and refused. That is a register-map problem, not a wiring one. |

And on `FB_RS485_BUSCONTROLLER`:

| Output | Reading it |
|:--|:--|
| `Transactions` | Completed transactions. |
| `StepsExecuted` / `Transactions` | **The batching ratio.** Above 1 when a multi-block device like the SDM220 is registered. Exactly 1.0 means batching is not happening — but a *falling* ratio on a faster bus is normal, not a regression: batching only has something to batch when several of a device's blocks come due in the same grant. Measured 2.7 with a 200 ms task, 1.4 with a 50 ms one. |
| `Cursor` | Must move. Frozen means selection is not advancing. |
| `Watchdogs` | Should stay 0. Non-zero means the transport stopped answering. |
| `ActiveDevice` | `-1` when the bus is free. Stuck on one index means a transaction never completed. |

### The contention fixture — proving fairness with one meter

Fairness cannot be seen on a bench with a single slave, because nothing ever
competes. Register the **same physical meter several times as different logical
devices with different polling intervals**:

```
FB_RS485_EASTRON_SDM220_BUSTEST_A : FB_RS485_EASTRON_SDM220_MQTT;   // 2s
FB_RS485_EASTRON_SDM220_BUSTEST_B : FB_RS485_EASTRON_SDM220_MQTT;   // 7s
FB_RS485_EASTRON_SDM220_BUSTEST_C : FB_RS485_EASTRON_SDM220_MQTT;   // 11s
```

all with `DeviceAddress := 1`, registered **after** the real devices, called
cyclically in `RS485_RUN`, and given **no `FriendlyName` and no `InitMqtt` call**
— so they load the bus and publish nothing, which keeps Home Assistant out of it.

Total demand then lands close to the bus's capacity, which is the condition under
which unfairness actually shows. The assertion that matters:

> **every instance has `DataAvailable1/2/3` TRUE and a plausible `VOLTAGE`.**

The one registered *last* is the one the pre-cursor `FOR 0 TO count-1` loop
starved, so `BUSTEST_C` is the interesting row.

`.ai/rs485tx/bench-edits.json` and `bench-spec.json` in the branch that introduced
this are the worked example, with `cleanup-edits.json` as its exact inverse.
**Strip the fixture before shipping** — it is a test harness, not project content.

The same fixture plus `bench-throughput.json` is how bus throughput gets measured:
sample the counters at two known times and divide. Watch the *difference* between
two windows rather than the totals, because the first window includes the startup
delay. What it has shown so far, five contending devices over the same 30 s:

| | 200 ms task, waiting for silence | 200 ms task | 50 ms task |
|:--|--:|--:|--:|
| per step | 1.87 s | 1.30 s | 0.42 s |
| per transaction | 5.00 s | 3.75 s | 0.53 s |

The cost is a fixed number of task cycles per exchange - about 6.5 to 8.5 - so the
task period, not the baud rate, is what moves it.

### Read-after-write

Only testable against a device with a writable register; the Ducobox is the one
this project has, and it is not on the bench. The shape of the assertion:

1. Publish a command to `Devices/PLC/Lab/In/RS485/<device>/<node>/write/<reg>`.
2. `StepsExecuted` rises by **2**, not 1 — the write and its read-back.
3. The value published back is read from the device, so setting a register to a
   value the device clamps or rejects must publish the *clamped* value.
4. With the slave disconnected, the write fails, `AbortOnError` skips the
   read-back, and **nothing is published**. That is the case worth proving: the
   old code published the payload it had sent as though sending were proof.

### MQTT discovery on a self-wiring block

A discovery change is one of the few things where the broker is a better witness
than the PLC. Assert both halves, because they fail independently:

**The block thinks it announced.** In a download spec:

```json
{"expect": {
  "GVL_RS485.FB_RS485_EASTRON_SDM220_1.InitMqttDone": "TRUE",
  "GVL_RS485.FB_RS485_EASTRON_SDM220_1.initMqttDiscoveryDone": "TRUE",
  "GVL_RS485.FB_RS485_EASTRON_SDM220_1.TopicTruncated": "FALSE"}}
```

`TopicTruncated` is the one people forget. IEC cuts an over-long `CONCAT` short
with no error at all, so a long prefix plus a long instance name yields an entity
that simply never appears — and `initMqttDiscoveryDone` is still TRUE.

**The broker actually has it.** A `-Diff` around the download counts the configs:

```
NEW (19):
  + homeassistant/sensor/..._FB_RS485_EASTRON_SDM220_1_VOLT/config
  ...
```

Count them against what the block should publish — 14 measurements plus
`diag_availability` and `diag_log` is 16 for the SDM220 — and read one payload to
check `stat_t` against a topic the block really publishes to. **A discovery config
pointing at a topic nothing writes is the failure this catches**, and it looks
perfect from inside the PLC. The cheapest way to make the two agree is to publish
through `PubMqttMessage`, which uses the same `MQTTPublishTopic` the discovery
config advertises, rather than concatenating the prefix and suffix by hand at
every call site.

Read the **GONE** section before the NEW one. A discovery config that was retained
before and is absent now is an entity Home Assistant still shows and nothing
publishes to any more.

### Two blocks on one meter — a cross-check that is already wired

To check that a device block decodes a register correctly, point a *second* block
at the same register of the same meter and compare readings.

**This one is permanent, not a fixture you have to build.**
`GVL_RS485.FB_RS485_EASTRON_SDM_POWER_1` is registered on the bus against the
lab SDM220 at address 1, declared as an `SDM220`, alongside
`FB_RS485_EASTRON_SDM220_1` reading the same meter. Both publish `/ACTP` from
register `30013`, so the comparison is available on the broker at any time without
touching the project:

```powershell
./tools/ai/Mqtt-Snapshot.ps1 -Watch -Seconds 60 `
  -Topics 'Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM220_1/ACTP',
          'Devices/PLC/Lab/Out/RS485/FB_RS485_EASTRON_SDM_POWER_1/ACTP'
```

:bulb: **A near-idle meter publishes exact zeros, and it is not your decode.** On
this bench both blocks intermittently reported `0.0` W against ~4.5 W otherwise.
What settles it is watching a *different value from the same frame*: the SDM220
block reads current, power factor and active power out of one 40-register reply,
and `CURR` stayed at 0.037 A and `POWF` at 1.0 on the very cycles where `ACTP`
read 0. Same frame, same CRC, same decode path — so the zero came from the meter.
Do not chase a decode bug without that control.

### Bench gotchas, both of which look like your bug and are not

- **Port 11740 closed while ping succeeds** — the runtime is down, which on this
  unit almost always means the two-hour demo licence expired. It needs a restart.
  Not credentials, not the network.
- **`serialmode RS485` is per controller.** Set from the CODESYS PLC shell, it
  reboots the device and survives reboots. Until it is done the bus is silent with
  nothing in any counter to show for it — `NoReply` climbing and everything else
  at zero. Set it explicitly even if it already reports RS485.

---

## Reporting

Say which mechanism proved each result. "The light responded to MQTT" and "the
light's output variable was written" are different claims, and only the first says
the subscription works.

If something could not be tested — sensor faulted, no hardware to press, licence
expired mid-run — say that plainly instead of narrowing the claim to whatever did
pass. An untested path reported as working is worse than no test.
