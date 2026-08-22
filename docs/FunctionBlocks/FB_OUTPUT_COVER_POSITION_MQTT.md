## FB_OUTPUT_COVER_POSITION_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

A roller shutter or blind that Home Assistant can send **to a position**, not just open, closed
and stop. The entity gets a slider, and the cover reports back how far open it is as it travels.

This is the sibling of [`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md), and the two are
interchangeable for everything that block already did. Use the older one when a cover genuinely
has nothing but two relays and no idea where it is; use this one when the travel time is known,
which is nearly always.

**Where the position comes from.** There is no encoder on a shutter motor, so the position is
*integrated from run time* against `T_TravelUp` and `T_TravelDown`: every cycle, however long it
lasted is added to or subtracted from the estimate. An end stop is the only place the position is
ever *measured*, which is why **a full `OPEN` or `CLOSE` ignores the estimate entirely and runs the
whole travel time** — see [drift, and what heals it](#drift-and-what-heals-it). A journey computed
from the estimate could never correct the estimate.

Everything is in percent, and the only library types used are `TON` and `TIME()`. **The block
depends on nothing but the standard library**, which was not the first plan — see
*[why the position engine is ours](#why-the-position-engine-is-ours)*.

:bulb: **Measure both travel times.** A shutter usually falls faster than it climbs. Times that
are 10% out show up as a position that drifts from reality mid-travel and snaps back at the end
stops.

:rotating_light: **A cover that has not moved since power-up does not know where it is**, and says
so: `PositionKnown` is FALSE and the state is `STOPPED` rather than a confident `OPEN` or `CLOSED`.
The engine's simulated position starts at 0, which looks exactly like a shutter resting closed and
is in fact an assumption - so reaching an end stop is only counted as knowledge once a motor has
actually run. The first full travel in either direction settles it.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────┐
       │ FB_OUTPUT_COVER_POSITION_MQTT │
       ├───────────────────────────────┤
BOOL ──┤ UP                         MU ├── BOOL
BOOL ──┤ DN                         MD ├── BOOL
BOOL ──┤ PRIO_LOCK            Position ├── BYTE
TIME ──┤ T_TravelUp             Moving ├── BOOL
TIME ──┤ T_TravelDown    PositionKnown ├── BOOL
TIME ──┤ T_Lockout                     │
TIME ──┤ T_EndStop                     │
BYTE ──┤ Tolerance                     │
BYTE ──┤ PublishStep                   │
       └───────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `UP` | BOOL | Manual up, e.g. straight from a pushbutton's long-press output. **Held TRUE drives, releasing stops and holds** — a person watching the cover beats whatever position was asked for, and the abandoned setpoint is not resumed. |
| `DN` | BOOL | Manual down, same contract as `UP`. Both held together is not a command: that is what the engine underneath calls automatic mode, and this block enters it by itself when a position is requested. |
| `PRIO_LOCK` | BOOL | Nothing may drive the motor while this is TRUE — a wind alarm, a service switch, an open window contact. Commands are still accepted and still remembered; they simply do not move anything until it clears. |
| `T_TravelUp` | TIME | Time to travel from fully closed to fully open. Defaults to 20 s. This is how the position is known at all, so measure it. |
| `T_TravelDown` | TIME | Time to travel from fully open to fully closed. Defaults to 20 s, and is usually the shorter of the two. |
| `T_Lockout` | TIME | Dead time between a stop and starting the other direction, so a reversing contactor is never asked to change its mind while the motor is still turning. Defaults to 1 s. Every direction change passes through it; starting from standstill is not delayed. |
| `T_EndStop` | TIME | Margin added to the **full** travel time on a full `OPEN` or `CLOSE`. Defaults to 2 s. The run is `T_Travel + T_EndStop` from wherever the cover is believed to be, so the motor always finishes against the physical stop; this margin covers a travel time measured slightly short. |
| `Tolerance` | BYTE | How close to the requested position counts as arrived, in percent. Defaults to 2. Below about 2 the cover hunts, because a shutter cannot be positioned finer than its own start and stop time. |
| `PublishStep` | BYTE | Percent of travel between position publishes **while moving**. Defaults to 5, which gives a slider that visibly tracks the shutter without putting twenty messages per journey on the broker. The exact position is always published once movement ends, whatever this is set to. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `MU` | BOOL | Motor up contactor. Never TRUE at the same time as `MD` — the engine holds a one-second lockout across a direction change. |
| `MD` | BOOL | Motor down contactor. |
| `Position` | BYTE | How far open, **0 closed to 100 open**, the way Home Assistant counts a cover. Converted from the engine's 0..255 with rounding, so a cover sent to 50 reads back as 50. |
| `Moving` | BOOL | A motor is running. |
| `PositionKnown` | BOOL | An end stop has been reached at least once since power-up, so the position has been measured rather than assumed. FALSE means it is still the engine's opening guess. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`InitMqttDiscovery`** — Publishes a Home Assistant MQTT discovery config so the entity is created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `DeviceClass` | STRING(50) | `'shutter'` | Home Assistant device class for the entity. Leave empty for the default. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **Code example**

```
FB_DO_COVER_002 : FB_OUTPUT_COVER_POSITION_MQTT := (FriendlyName := 'Living room shutter');
```

```
FB_DO_COVER_002(
	T_TravelUp := T#20S,
	T_TravelDown := T#18S,
	MU => DO_005,
	MD => DO_006
);
```

That is the whole of it: the block wires itself from `GVL_MQTT` on its first cyclic call and
announces a cover **with a position slider** to Home Assistant. Add a pushbutton by handing its
long-press outputs to `UP` and `DN`.

:rotating_light: **The travel times are inputs, not `FB_init` arguments** — deliberately unlike
[`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md), which takes `(T_LOCKOUT, T_UD)` at the
declaration. A travel time is the one number on a cover that somebody always ends up tuning after
watching the thing move, and CODESYS stores an instance's `FB_init` arguments where no script can
revise them — see [CLAUDE.md](../../CLAUDE.md). An input can be corrected from `MAIN_INIT`, from
an online session, or by editing one line here.

### **MQTT behaviour**

| direction | topic | payloads |
|:--|:--|:--|
| publish | `.../Out/Covers/<instance>` | `OPEN` / `OPENING` / `CLOSING` / `CLOSED` / `STOPPED`, on change and once at startup |
| publish | `.../Out/Covers/<instance>/POSITION` | `0`..`100`, every `PublishStep` while moving and exactly once movement ends |
| subscribe | `.../In/Covers/<instance>` | `OPEN`, `CLOSE`, `STOP` |
| subscribe | `.../In/Covers/<instance>/POSITION` | `0`..`100` |

:bulb: **The cover subscription is a `#` wildcard because of this block.** The position command
topic sits one level below the cover's own topic, and `MqttSubCoverTopic` used to end in `+`,
which would not have delivered it. The older cover block's topics still match, so nothing changed
for it.

### **Drift, and what heals it**

A position integrated from run time drifts: travel times measured slightly wrong, a motor that
slips, a shutter moved by hand, a PLC restart, or a scan longer than `MAX_TICK_MS` while the motor
was running. Nothing in the process image can detect any of that — which makes what happens next
the most important behaviour in this block.

**A full `OPEN` or `CLOSE` does not trust the estimate.** It runs for `T_Travel + T_EndStop` from
wherever the cover is thought to be, and finishes against the physical stop. Only then is the
estimate *set* — not nudged — and `PositionKnown` raised. So every full command re-references, and
one of them repairs any amount of drift.

The alternative was tried first and is worth naming, because it looks correct: drive only the
distance the estimate believes is left, then press the stop for `T_EndStop`. That heals
`T_EndStop / T_Travel` of error per command — **10% at the defaults** — and heals nothing at all in
the direction the estimate over-reads. A cover reporting 80 while sitting at 20 would answer `OPEN`
by running six seconds, stopping at a real 50, and reporting 100.

:rotating_light: **The cost is a motor that runs longer than strictly needed** — a full open from
90% still runs the whole travel. The shutter's own end stops and the motor's thermal cutout are
what make that safe, and it is exactly what [`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md) has
always done on every command. If a particular motor cannot take it, that motor should not be on a
time-based position block.

**An unreferenced cover never reports 0 or 100.** Home Assistant reads those as the limits and
disables the button in that direction — which is precisely the command that re-references. So while
`PositionKnown` is FALSE the published position is clamped to 1…99, both ends of the slider stay
reachable, and one full command settles the matter. The `Position` **output** is left alone: PLC
logic should see the estimate, not a number bent for a user interface.

What still does not heal, and should be understood before trusting the number:

- **A mid-range journey cannot re-reference.** Sent to 60%, the cover stops where the estimate says
  60% is. If the estimate was wrong, it stays wrong until the next full command.
- **The estimate is not persistent.** A restart starts from 0 with `PositionKnown` FALSE — nothing
  moves, nothing claims to be closed, and the first full command fixes it.
- **Only a real end-stop signal makes the position measured rather than inferred.** Limit switches
  or motor-current sensing are the honest fix; this block is what you use when you have neither.

### **What a stop means**

Three ways to interrupt a journey, and they are deliberately not the same:

| | effect |
|:--|:--|
| `STOP` over MQTT | motors off, and **the setpoint is dragged to the present position** so automatic mode has nothing left to resume. A stop that silently resumes later is not a stop. |
| releasing `UP` / `DN` | the same hold, reached the same way |
| `PRIO_LOCK` | motors off, but the setpoint is **kept**: whatever was asked for happens when the lock clears |

### **Home Assistant**

The block publishes its own discovery config, so no YAML is needed:

| Field | Value |
|:--|:--|
| `position_topic` / `set_position_topic` | the two `/POSITION` topics above |
| `position_open` / `position_closed` | 100 / 0 |
| `device_class` | from `DeviceClass`, `shutter` by default |

**Supplying `set_position_topic` is what puts a slider on the entity** rather than three buttons,
which is the whole difference from the older cover block on the Home Assistant side.
`CreateCoverEntity` therefore takes all four position fields as optional parameters and publishes
`null` for each when they are empty — so
[`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md)'s config gains four nulls and behaves exactly as
it did.

### **Why the position engine is ours**

The first version of this block wrapped `OSCAT_BUILDING.BLIND_CONTROL_S`, which looked ideal: a
documented blind controller, already referenced by this project, that integrates run time into a
simulated 0..255 position and handles the lockout. Its manual describes an automatic mode where
`UP` and `DN` held together make it regulate its position to the setpoint `PI`.

On hardware it did keep a position — and never energised a motor. Sampled every 3 s across a full
travel, `POS` climbed 0 → 23 → 80 → 138 → 195 → 254 → 255 with **`MU` and `MD` FALSE at every
single sample**, and `STATUS` stuck at 125.

125 is the default of `S_IN`, its "ESR compliant status input", and the manual explains the rest:

> When there are no messages available each module passes the input adjacent S_IN status messages
> on to the STATUS output. […] If a status message is present at the input it will overwrite the
> own status messages.

So the block, out of the box, believes an upstream module is in charge and stands down from
driving. Writing `S_IN := 0` — "no message" — fixed that immediately: the coil came on and stayed
on for the whole travel. But then `STATUS` settled at 128 and the next command was ignored, the
motor held at the top: with `UP` and `DN` held together the block had entered its own click and
scene logic rather than the automatic row the manual's table promises. Driving it standalone is
not the arrangement it was built for; it expects `BLIND_INPUT` upstream, generating the status and
mode transitions it reacts to.

That is a lot of undocumented behaviour to inherit for something a shutter needs to do reliably,
so the integration is done here instead: about seventy lines, every one of them inspectable, no
0..255 conversion, and no dependency beyond `TON` and `TIME()`. It cost three bugs of its own to
get right — all three listed above, all three caught on the bench — which is a fair trade for
code whose every branch can be read.

The lesson is recorded rather than the workaround: if a future block needs OSCAT's blind chain, it
should use the whole chain, `BLIND_INPUT` included.
