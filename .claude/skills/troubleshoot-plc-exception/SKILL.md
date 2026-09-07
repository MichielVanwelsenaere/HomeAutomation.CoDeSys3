---
name: troubleshoot-plc-exception
description: Find out why a PFC200 stopped - an application that died, a building that went dead, an exception, a crash, or a restart nobody explained - by reading the runtime's own log and core dump on the controller. Use when a PLC is unresponsive or was just restarted, when Home Assistant lost a whole controller at once, when the lights and pushbuttons stopped working, or when someone asks what a red LED on a cabinet means.
---

# Why a PFC200 stopped

The runtime writes down exactly why it stopped, and the record survives a
restart. Almost all the time lost to a failure like this goes on not reading it:
the file is not where the CODESYS documentation implies, the controller's clock
is years wrong so its timestamps look irrelevant, and the LEDs on the front
invite a diagnosis they cannot support.

This page is the route to the evidence, in the order that gets there fastest.

## 1. Establish what was actually dead

Do this before touching the controller, because it decides which half of the
system to investigate and the answers are all free:

| Check | Command | What a positive proves |
|:--|:--|:--|
| Application publishing | `mosquitto_sub -h <broker> -R -t 'Devices/PLC/<site>/availability'` | The application is running **now** |
| Runtime process alive | `./tools/ai/codesys.ps1 scan` | The runtime answers the gateway, whatever the application is doing |
| Runtime's own view | PLC Shell `getprgstat` | `[Run]` vs stopped, and whether an exception flag is set |
| **Did the wall pushbuttons work during the outage?** | ask the person | **The single most useful question.** Dead buttons mean the application was gone; working buttons with no Home Assistant mean only the MQTT path failed |

`-R` is not optional. It suppresses retained messages, and the retained value of
an availability topic is the **last will from the previous disconnect** — it
reads `offline` however healthy the PLC is. A snapshot without `-R` will tell you
a running controller is dead.

Three shapes, three different investigations:

- **Everything dead, buttons included** → the application stopped or was stopped.
  Read the log (§4). This is the case this page is mostly about.
- **Buttons dead, MQTT fine** → the K-bus. Look for `bus is not communicating`
  in the log, and remember the DI process image reads *zero* while the bus is
  down, which through a normally-closed loop is the tripped state.
- **MQTT dead, buttons fine** → the client, the broker, or the network. Nothing
  in this page applies; start at `test-plc-logic`.

## 2. Get onto the controller

SSH, `root`. The vendor default password is `wago` on this generation; newer
WAGO firmware ships a per-device password printed on the label, and a
commissioned box may have had it changed — only WBM as `admin` can reset it.
Never factory-reset to recover a password: that wipes the runtime installation
and the boot application with it.

There is no `sshpass` or `plink` on the dev machine, so a password cannot be
piped in. Use OpenSSH's askpass instead:

```bash
printf '#!/bin/sh\necho "<password>"\n' > pw.sh && chmod +x pw.sh
SSH_ASKPASS="$PWD/pw.sh" SSH_ASKPASS_REQUIRE=force DISPLAY=:0 \
  ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no root@<ip> 'uptime'
rm -f pw.sh          # do not leave it lying around
```

`SSH_ASKPASS_REQUIRE=force` is the part that matters: without it OpenSSH only
consults askpass when it has no tty, which depends on how the shell was invoked.

**No password at all?** Two routes need none, because they go over the runtime
connection rather than Linux: the device editor's **Files** tab browses the
controller's filesystem and can download the log, and **PLC Shell** answers for
runtime state (§6).

## 3. Where the evidence lives

| What | Path | Survives reboot |
|:--|:--|:--|
| **Runtime log**, current and rotated | `/home/codesyscontrol/var/opt/codesys/codesyscontrol.log`, `codesyscontrol_0.log` | yes |
| **Core dump**, written on every exception | `/home/codesyscontrol/var/opt/codesys/PlcLogic/<app>/<app>.core` | yes |
| WAGO's event log | `/log/wagolog.log`, `.log.1` | yes |
| CODESYS audit log | `/var/opt/codesys/.Audit*.log` | yes |
| Logger and watchdog configuration | `/etc/codesyscontrol/CODESYSControl.cfg`, `CODESYSControl_User.cfg` | yes |
| Kernel, syslog, lighttpd | `/var/log/*` | **no** — tmpfs, 4 MB, cleared at boot |

Two traps here, both of which cost a run:

- **`/var/opt/codesys` is a decoy.** It holds the licence container, the object
  database and the audit logs, and it is where the configuration says the log
  goes — but the runtime's live state is under **`/home/codesyscontrol/`**, on a
  different mount. `find / -xdev -name 'codesyscontrol*.log*'` returns nothing
  and looks like a definitive answer. Search without `-xdev`.
- **`/var/log` is RAM.** Anything you want from the previous run is not there.
  `dmesg` is equally gone, so an OOM kill cannot be confirmed after a reboot —
  which is a reason to read the CODESYS log rather than hunt for one.

Also: **`strings` is not on `PATH`** in this Git Bash. `strings f | grep x`
silently produces nothing, which reads exactly like "the file contains no such
text". Extract printable runs with Python instead.

## 4. Read the log — but fix the clock first

**Assume the controller's clock is wrong.** Neither site controller runs
NTP: on 7 Sep 2026 Bijbouw's clock read January 2023 and Stal's read June 2026.
Timestamps are internally consistent, so the log is perfectly usable once
anchored:

1. `date` on the controller, next to the real time, gives the offset.
2. Cross-check it against an event you can date independently — the mtime of
   `PlcLogic/<app>/<app>.app` against the download you remember making, or an
   `Application ... loaded via [Download]` line against a commit.

Anchored to about ±15 minutes, which is ample. Do not skip this: an unanchored
log makes a crash from an hour ago look like ancient history.

Then read it:

```bash
grep -inE "exception|fatal|abort|watchdog|out of memory" codesyscontrol.log
```

| What you find | What it means |
|:--|:--|
| `Processorload watchdog: plcload=NN, maxplcload=95` followed by `*EXCEPTION* [ProcessorLoadWatchdog] ... App=[all], Task=[all]` | The runtime stopped **everything** over CPU load. See §5 |
| `*EXCEPTION*` naming a task and an exception type | A real IEC fault. The core dump names the POU — load it in the IDE (**Debug → Load core dump**) against the matching project |
| `bus is not communicating: restarting` | K-bus dropout; the I/O driver restarted it. Real, and separate from any application fault |
| `task_signalhandler_exit [X] lost cycles: N` | **Usually not a fault.** It is emitted when a task is stopped, so it accompanies every download. Count these against `loaded via [Download]` lines before treating them as evidence of overload |
| `Create asymmetric key in progress` on a daily cadence | A certificate that is not persisting. Harmless in itself, but it is tens of seconds of CPU per day on a controller that may not have it to spare |

`Logger.0.Filter=0x0000000F` (info, warning, error, exception) is the default and
lives in `CODESYSControl_User.cfg` so `logsetfilter` can change it. Check it
before concluding that a silent log means a clean run — but note that at `0x0F`
exceptions **are** recorded, so a genuinely silent log means the application did
not fault.

## 5. ProcessorLoadWatchdog: the one that stops a whole building

WAGO arms this in the runtime configuration, and it is easy to be unaware of:

```
[CmpSchedule]
ProcessorLoad.Enable=1
ProcessorLoad.Maximum=95
ProcessorLoad.Interval=5000
```

Every 5 seconds it samples PLC load; one sample above 95% raises an exception
against `App=[all], Task=[all]`. It stops every task in every application and
leaves them stopped — lights, pushbuttons, covers, MQTT, all of it — until
someone restarts the PLC. There is no automatic recovery, and because it acts on
a 5-second average it needs only a burst, not a sustained overload.

It matters here because **a Freewheeling task consumes every spare cycle by
definition**, so a controller with one sits permanently near the ceiling.

### The measurement that settles it

CODESYS names its task threads after the IEC tasks, so per-task CPU is directly
attributable — no guessing which task is expensive:

```bash
top -H -b -n 2 -d 3 | awk '/PID USER/{n++} n==2'
```

Take the **second** sample. `top`'s first iteration computes %CPU since boot and
is meaningless. For an honest average, divide a thread's `TIME+` by the uptime
rather than trusting the instantaneous figure.

Measured 7 Sep 2026, as a baseline to compare a future reading against:

| Thread | Bijbouw | Stal |
|:--|--:|--:|
| `MqttCommunication` (Freewheeling, prio 5) | 27.8% inst., **~32% averaged** | ~13% averaged |
| `MainTask` (Cyclic 50 ms, prio 4) — the actual control logic | **1.5%** | — |
| `Schedule` (runtime) | 7.6% | 7.5% |
| CodeMeter comm (×2) | 7.5% | 5.2% |
| OPC UA server (×2) | 4.0% | — |
| Edge gateway (×2) | 4.4% | — |
| Load average (single core) | 2.87 / 3.64 / 3.29 | 2.00 / 1.79 / 1.86 |
| Watchdog trips in the log | **2** | 0 |

Note the shape of it: the house logic costs 1.5% and the MQTT task costs twenty
times that, purely because it never sleeps.

**`plcload` from the PLC Shell will not show you this.** It read 51% on Bijbouw
and 44% on Stal — an average that hides exactly the bursts the watchdog samples.
A comfortable `plcload` is not evidence of headroom.

## 6. Compare against the sibling controller

The strongest tool available: two controllers running the same runtime and the
same project structure with different loads. If one trips and the other never
has, the difference between them *is* the answer. Collect on both:

`uptime` · `cat /proc/loadavg` · `top -H` per-thread · trip count in the log ·
whether a `.core` file exists · `rtsinfo` · clock offset

That comparison is what turned "Bijbouw crashed twice" into "Bijbouw carries the
Ducobox and runs hot, Stal carries less and has never tripped in 7 days".

## 7. Ruling out a memory leak

It is the first thing everyone suspects, and in this project it is almost always
wrong, because **nothing in the IEC layer allocates**:

```bash
grep -cE "__NEW|__DELETE|SysMemAllocData|SysMemFreeData|MemAlloc|MemFree|MALLOC" \
  src/Exports/PLCopen.xml
```

Zero in this project's own code, and zero in `PRO_JSON 1.0.21.0` — whose only
`VAR_GLOBAL` is `VAR_GLOBAL CONSTANT`, so it holds no accumulating state either.
A `.library` is a **ZIP**, and its `__shared_data_storage_string_table__`
carries the ST source, so a vendored library can be audited this way without
opening the IDE.

If a leak is still worth measuring, measure the slope rather than waiting for a
recurrence: sample `VmRSS` from `/proc/$(pidof codesyscontrol)/status` an hour
apart. Exhausting ~200 MB over three days is ~2.7 MB/h, which is visible within
the hour.

What IEC code *can* do is consume stack: an FB instance declared in a **method's**
`VAR` block is stack-allocated and its `FB_init` runs per call, so a
`STRUCT_TO_JSON` local costs `GPL_JSON.MAX_JSON_STRING` bytes of stack every
call — 20 001 as configured here. Check the task stack size in
`CODESYSControl.cfg` before deciding whether that is merely wasteful.

## 8. PLC Shell: what is safe on a running building

| Safe, read-only | |
|:--|:--|
| `rtsinfo` | runtime version |
| `applist`, `getprgstat` | applications and their state |
| `plcload` | PLC load average (see the caveat in §5) |
| `pinf` | project info of the running boot application — empty unless the project fills in a Project Information object, which is worth doing |
| `getsramlayout` | retain/persistent segments |
| `loggetfilter`, `channelinfo`, `sessinfo-list` | logging and comms |

**Never on a running house:** `stopprg`, `startprg`, `reload`, `resetprg`,
`resetprgcold`, `clearsram`, `restoresram`, `restoreretains` — they stop the
application or destroy retained state. `logsetfilter` and `logdelfilter` write
runtime configuration; leave them until the diagnosis is finished.

## 9. Watching for the next one

Don't poll on a timer. **Use the sibling controller's availability heartbeat as
the clock**: both publish about every 5 seconds, so counting the sibling's ticks
while the suspect is silent measures the outage *and* gives a built-in control —
if both go quiet, it is the broker or the network, not the PLC. Two processes,
no timers, and it runs for days:

```bash
mosquitto_sub -h <broker> -v -R \
  -t 'Devices/PLC/<suspect>/availability' \
  -t 'Devices/PLC/<sibling>/availability' \
  -t 'Devices/PLC/<suspect>/Out/RS485/BUS_COUNTERS' | awk '...'
```

A first version of this spawned two `mosquitto_sub` per 30 s and was killed for
memory. One long-lived subscription is both cheaper and more responsive.

`BUS_COUNTERS` is a free time series while you wait, published every 30 s:
`ok`/`steps` rate falls when a task is being starved, `drop=` leaves zero when
the publish queue cannot keep up, `exc=` tracks the Modbus side.

## 10. What the LEDs can and cannot tell you

**Do not diagnose from the RUN LED.** On 7 Sep 2026 Bijbouw showed a steady red
RUN while its application was verifiably in `Run` and driving the house, and
Stal — same runtime, same project — showed green. Whatever drives it is not the
application state. The only difference found between the two boxes was that
Bijbouw had a `.core` file present and Stal did not.

The one LED this project *does* drive is **U1**: steady green while the broker is
reachable and the MQTT session is up, blinking red otherwise
(`docs/AdditionalFunctionality/User_leds_CODESYS3S_runtime.md`). That one is
trustworthy because it is in the code.

## 11. Fixing what you find

A task's kind, period and priority are `scaffold` fields, so this class of fix
is a spec file rather than a GUI session:

```powershell
./tools/ai/codesys.ps1 scaffold -Project .ai/sync/<Site>/<Site>.project \
    -Scaffold tools/ai/scaffold/mqtt-task-cyclic.json -Force
```

`tools/ai/scaffold/mqtt-task-cyclic.json` is the worked example — Freewheeling to
Cyclic 20 ms on both controllers — and `tools/ai/scaffold/g1-ping-priority.json`
is the priority equivalent. Both run against a **working copy** made by
`sync-implementation-project`'s `Working-Copy.ps1`, never against the building's
project directly, and `scaffold` builds before it saves.

Nothing here reaches a PLC. A download to a building is a deliberate, separate
act and needs the owner's go-ahead.
