---
name: test-plc-logic
description: Exercise the PLC's actual behaviour on real hardware - lights, pushbuttons, covers, dimmers and the HVAC chain - by commanding it over MQTT and asserting the result on the broker and in the running application. Use after a download, when asked whether some logic still works, when a refactor touched behaviour the compiler cannot check, or when a Home Assistant entity is not doing what it should.
---

# Test the PLC logic on hardware

The compiler is the only automated gate this project has. It cannot tell you
whether pressing a button turns on a light, or whether a thermostat opens a valve —
[CODESYS simulation cannot run this project at all](../../CLAUDE.md), so *behaviour
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

Topic roots come from `MqttVariables` (`MqttMain` + `MqttType` + `MqttDevice`), so
everything below assumes `Devices/PLC/Lab/`. Change `MqttDevice` and it all shifts.

```powershell
$mp = 'C:\Program Files\mosquitto\mosquitto_pub.exe'
$B  = '10.101.1.11'
function Cmd($topic, $payload) { & $mp -h $B -t "Devices/PLC/Lab/In/$topic" -m $payload -q 2 }
```

| What | Command topic (under `In/`) | Payload | State topic (under `Out/`) |
|:--|:--|:--|:--|
| Binary light | `DigitalOutputs/FB_DO_BIN_001` | `TRUE` / `FALSE` | `DigitalOutputs/FB_DO_BIN_001` |
| Bistable light | `DigitalOutputs/FB_DO_BISTABLE_001` | `TRUE` / `FALSE` | `DigitalOutputs/FB_DO_BISTABLE_001` |
| Cover | `Covers/FB_DO_COVER_001` | `OPEN` / `STOP` / `CLOSE` | `Covers/FB_DO_COVER_001` |
| Dimmer | `Dimmers/FB_AO_DIMMER_001/...` | see the block's page | `Dimmers/FB_AO_DIMMER_001/OUT`, `/Q` |
| Thermostat mode | `HVAC/FB_THERMOSTAT_2/MODE` | `off` / `heat` / `auto` | `HVAC/FB_THERMOSTAT_2/MODE` |
| Thermostat setpoint | `HVAC/FB_THERMOSTAT_2/DESIRED_TEMP` | e.g. `22` | `HVAC/FB_THERMOSTAT_2/DESIRED_TEMP` |

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
   "write":    {"PLC_PRG_HVAC.FB_THERMOSTAT_2.DESIRED_TEMP": "22"},
   "delay_ms": 2000,
   "expect":   {"PLC_PRG_HVAC.FB_PUMP_2_COLLECTOR.VALVE[1]": "TRUE"},
   "read":     ["PLC_PRG_HVAC.FB_PUMP_2_COLLECTOR.PUMP"]}
]}
```

**`expect` compares typed literals.** `read_value` returns `UDINT#0`, `INT#8`,
`TIME#20s`, `'a string'` — not `0`, `8`, `20s`. Write the expectation the way the
PLC spells it, or the step fails for the wrong reason.

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

# The three suites

## 1. Lights — binary and bistable outputs

The straightforward one, and worth running first because it proves the whole MQTT
path end to end before you debug anything harder.

1. Command on: `Cmd 'DigitalOutputs/FB_DO_BIN_001' 'TRUE'`
2. Within a second or two, `Out/DigitalOutputs/FB_DO_BIN_001` should read `TRUE`.
3. Command off and confirm it returns to `FALSE`.
4. Repeat for `FB_DO_BISTABLE_001`.

Assert in the same run that the output really moved, not just the topic:

```json
{"expect": {"PLC_PRG_MAIN.FB_DO_BIN_001.OUT": "TRUE"}}
```

**If the state topic never changes:** the block is not subscribed. Check
`InitMqttDone` on the instance, and that its body is being called cyclically —
self-wired blocks wire themselves on their *first cyclic call*, so an instance whose
body never runs is silently absent from Home Assistant.

**Both of these announce as `light`, not `switch`.** If Home Assistant shows
`switch.` entities, `EntityType` was lost on the declaration; the retained
`homeassistant/light/..._FB_DO_BIN_001/config` will have been orphaned.

## 2. Pushbuttons — hardware in, MQTT out

Pushbuttons are **inputs**. There is nothing to command: the block publishes when
the physical button changes, and the events are not retained, so a snapshot will
never show them. This suite needs either a finger or a forced input.

**With hardware:** start `-Watch`, press the button on the 750-440 module, and
confirm events appear under
`Devices/PLC/Lab/Out/DigitalInputs/Pushbuttons/FB_DI_PB_001`.

**Without:** force the digital input in a spec and read the block's outputs. The
pushbutton block distinguishes a short press from a long one, so hold the input
across a delay long enough to cross that threshold:

```json
{"steps": [
  {"write": {"DI_001": "TRUE"}, "delay_ms": 150,
   "read":  ["PLC_PRG_MAIN.FB_DI_PB_001.P_SHORT", "PLC_PRG_MAIN.FB_DI_PB_001.P_LONG"]},
  {"write": {"DI_001": "FALSE"}, "delay_ms": 200,
   "read":  ["PLC_PRG_MAIN.FB_DI_PB_001.P_SHORT"]}
]}
```

Substitute the real input variable — check what `FB_DI_PB_001` is actually wired to
in `READ_PUSHBUTTONS` rather than trusting `DI_001` here.

**A written input may be overwritten.** If the program assigns that variable every
cycle from the bus, a one-shot write lasts one cycle. If the value will not stick,
say so and press the button instead — do not report a pass you did not get.

Note that `FB_DI_PB_001.P_LONG` drives the cover in `MOVE_COVERS`, so a long press
here is also a cover test.

## 3. HVAC — thermostat → valve → pump → burner

The chain, and the one worth understanding before testing:

```
thermostat OUT  →  collector THERMOSTAT[n]  →  VALVE[n]  →  PUMP  →  FB_PUMP_2  →  HEAT_REQUEST  →  burner
                                                     (after ValveCycleTime)      (own min run / run-on)
```

`FB_THERMOSTAT_2` drives circuit 1 (`Radiator 1`, `DO_006`), `FB_THERMOSTAT_3`
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
Devices/PLC/Lab/Out/HVAC/FB_THERMOSTAT_2/FAULT   → must be FALSE to proceed
```

If it is `TRUE`, either fix the sensor — the commented-out `RegisterDevice` in
`RS485_INIT` is the first place to look — or force it for the test:

```json
{"write": {"RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01.DataAvailable": "TRUE",
           "RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01.Error": "FALSE",
           "RS485Variables.FB_RS485_1WIRE_MULTISENSOR_01.TEMPERATURE": "18.0"}}
```

Whether that sticks depends on whether the RS485 block writes those outputs every
cycle. **Verify it stuck** by reading `FB_THERMOSTAT_2.SENSOR_VALID` back before
concluding anything about the valve.

**The pump is slow on purpose.** `ValveCycleTime` is `T#3M`: the pump only starts
three minutes after heat is first requested, so a valve can open fully before there
is flow. `FB_PUMP_2` then has its own minimum run and run-on times (2 min / 1 min),
so it will not stop the moment demand goes away. A test that waits two seconds and
reports "pump did not start" is measuring the wrong thing.

### The test

1. **Establish the sensor is trusted.** `/FAULT` must be `FALSE`.
2. **Ask for heat.** With `MEASURED_TEMP` around 18:
   ```powershell
   Cmd 'HVAC/FB_THERMOSTAT_2/MODE' 'heat'
   Cmd 'HVAC/FB_THERMOSTAT_2/DESIRED_TEMP' '22'
   ```
   18 is below 22 − hysteresis, so the thermostat should call for heat.
3. **Thermostat picks it up** — within a cycle or two:
   `Out/HVAC/FB_THERMOSTAT_2` → `TRUE`, `/MODE` → `heat`, `/DESIRED_TEMP` → `22`.
4. **Valve opens immediately** — the collector assigns `VALVE[i] := THERMOSTAT[i]`
   with no delay: `Out/HVAC/FB_PUMP_2_COLLECTOR/Valves/VALVE_1` → `TRUE`.
   `VALVE_2` must stay `FALSE`: circuit 2 has its own thermostat, and a valve
   opening on its own would be a real bug.
5. **Pump starts after `ValveCycleTime`.** Wait past three minutes, then
   `Out/HVAC/FB_PUMP_2` → `TRUE`. Read `FB_PUMP_2_COLLECTOR.PUMP` and `PumpDelay.Q`
   too — they tell you whether you are early or actually broken.
6. **Burner follows the pump:** `FB_PUMP_2.HEAT_REQUEST` → `Out/HVAC/FB_BURNER_GAS`.
7. **Reverse it.** `Cmd 'HVAC/FB_THERMOSTAT_2/MODE' 'off'` → thermostat `FALSE`,
   `VALVE_1` `FALSE` promptly; the pump lingers for its minimum cycle. Confirm it
   *does* stop rather than assuming.

### Also worth asserting

- **Fail-safe.** Set `SENSOR_VALID` false mid-demand and confirm `OUT` drops and
  `/FAULT` goes `TRUE`. This is the branch that matters most on a heating system
  and the easiest to break silently in a refactor.
- **The clamp.** Publish `30` to `DESIRED_TEMP`; expect `24.0` echoed back.
- **The eight valve topics all exist**, even for unwired circuits — the collector
  publishes all eight on startup. Losing `VALVE_3..8` from the broker would mean the
  startup publish loop broke.

---

## Reporting

Say which mechanism proved each result. "The light responded to MQTT" and "the
light's output variable was written" are different claims, and only the first says
the subscription works.

If something could not be tested — sensor faulted, no hardware to press, licence
expired mid-run — say that plainly instead of narrowing the claim to whatever did
pass. An untested path reported as working is worse than no test.
