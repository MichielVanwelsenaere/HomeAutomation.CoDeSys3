## FB_INPUT_PULSE_COUNTER_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Counts pulses from a meter on a digital input — water, gas, electricity, heat, or anything else a
meter signals one pulse at a time — and publishes them to Home Assistant as a cumulative sensor
that Home Assistant keeps **long-term statistics** for. Consumption per hour, day, week, month and
year then comes from Home Assistant: in the energy dashboard, in a statistics graph, or through a
utility meter helper. See *[Home Assistant](#home-assistant)*.

**The statistics are the product; the PLC's count is not.** The block counts from zero every time
the PLC starts and keeps nothing across a restart. That is deliberate, and it is what keeps the
statistics right: Home Assistant reads a count that falls back to zero as a meter that started a
new cycle, and carries its own sum of consumption on from where it was. Nothing in the PLC has to
survive a power cut, a download or a renamed instance for the day, week and month figures to be
correct. See *[Why the count starts at zero](#why-the-count-starts-at-zero)*.

What one pulse is worth is a setting, not a property of the block. Settings are **constructor
arguments**: they go in the instance declaration, are read once when the application starts, and
the cyclic call carries only the input signal. Two of them describe a meter:

| | What it says | Example |
|:--|:--|:--|
| `MeterType` | **what** is measured, and the unit published | `WATER_M3` — water, in m³ |
| `PulseWeight` | how much of that unit **one pulse** is | `0.001` — one pulse per litre |

So the same block reads every common pulse meter:

| Meter | One pulse is | `MeterType` | `PulseWeight` |
|:--|:--|:--|:--|
| Water meter, reed contact, 1 L per pulse | 1 L | `WATER_M3` | `0.001` |
| Water meter, reed contact, 10 L per pulse | 10 L | `WATER_M3` | `0.01` |
| Same meter, counted in litres | 10 L | `WATER_L` | `10.0` |
| Gas meter, reed contact, 0.01 m³ per pulse | 0.01 m³ | `GAS_M3` | `0.01` |
| kWh meter, S0 output, 1000 imp/kWh | 1 Wh | `ENERGY_KWH` | `0.001` |
| kWh meter, S0 output, 800 imp/kWh | 1.25 Wh | `ENERGY_KWH` | `0.00125` |
| Heat meter, 1 pulse per 10 kWh | 10 kWh | `ENERGY_KWH` | `10.0` |
| Anything else | — | `GENERIC` + `GenericUnit` | per meter |

The impulse constant printed on a meter is pulses **per** unit; `PulseWeight` is its inverse,
units per pulse. It is resolved to a millionth of the published unit and counted in whole
millionths, which is exact for every impulse constant in the table and for any constant whose
inverse has six decimals or fewer — so the count never drifts by rounding, however long the PLC
runs.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌─────────────────────────────┐
       │ FB_INPUT_PULSE_COUNTER_MQTT │
       ├─────────────────────────────┤
BOOL ──┤ Pulse                 Total ├── LREAL
BOOL ──┤ ProcessImageValid     EVENT ├── BOOL
       └─────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `Pulse` | BOOL |  | The digital input the meter's pulse output is wired to. A pulse is counted on its **rising edge**, once it has been high for `MinPulseTime`. |
| `ProcessImageValid` | BOOL | `FALSE` | TRUE once the K-bus is exchanging process data. Wire it to `Pfc200Bus.xConfigFinished`. While FALSE nothing is counted, and the first scan after it rises **takes the input as it finds it** rather than counting it: a meter that stopped with its reed contact closed reads FALSE before the bus is up and TRUE after, and without this gate that is one phantom pulse per restart. Defaults to FALSE so a forgotten wire counts nothing — which is loud — rather than a pulse per restart, which is not. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Total` | LREAL | Consumption since the PLC started, in the unit `MeterType` names. Starts at 0 on every start and only ever rises. |
| `EVENT` | BOOL | High for one cycle on every counted pulse, after the `MinPulseTime` filter. For local logic, such as a leak alarm. |

### **Methods**

**`FB_init`** — CODESYS constructor. These parameters are supplied in the instance declaration, not by calling a method, and are applied once at startup. All four are required on every instance — CODESYS has no optional constructor arguments.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MeterType` | E_PULSE_METER_TYPE |  | What is measured and the unit `Total` is in. Sets the Home Assistant `device_class` and units — see *[Meter types](#meter-types)*. |
| `PulseWeight` | LREAL |  | Units of `Total` per pulse: the inverse of the impulse constant on the meter. Values below one millionth, and zero or negative values, count nothing. |
| `GenericUnit` | STRING(16) |  | The unit published for `MeterType := GENERIC`; pass `''` for every other type. **ASCII only** — see *[Meter types](#meter-types)*. |
| `MinPulseTime` | TIME |  | How long `Pulse` must stay high, and then low, before an edge counts. Filters the bounce of a reed contact. `T#20MS` is the value to use unless a meter needs otherwise: it sits under the 30 ms an S0 output guarantees (IEC 62053-31), so it suits both kinds of meter; see *[How fast it can count](#how-fast-it-can-count)*. `T#0ms` counts every clean edge the task sees. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup. Not needed when `FriendlyName` is set at the declaration: the block then wires itself.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MQTT_PUBLISH_QUEUE |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes the Home Assistant discovery config for the consumption sensor. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `GVL_MQTT.PLC_Device`. |
| `Name` | STRING(255) |  | Name of the entity in Home Assistant. The self-wiring prologue passes `FriendlyName`. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
<!-- fb-interface:end -->

### **Why the count starts at zero**

Home Assistant's statistics do not store the value the PLC publishes. They store a running **sum
of consumption**, built from the differences between consecutive values, and every day, week and
month figure is read from that sum. For a sensor with `state_class: total_increasing`, a value that
goes down is interpreted by how far it falls:

| Published value | Home Assistant reads it as | Effect on the sum |
|:--|:--|:--|
| rises | consumption | adds the difference |
| falls by 10 % or more | **a new meter cycle**, counting from zero | keeps the sum, then adds the new value as it rises |
| falls by less than 10 % | a dip in a meter that cannot dip, and logs a warning | subtracts the difference |

A PLC restart is the second row. So the block makes sure every restart lands there:

- **The first value published after a start is always `0`**, before any pulse is counted. That
  publish overwrites the retained value from before the restart, so the fall is the whole of the
  previous count — never a dip of a few percent, however long the PLC was running.
- While running, `Total` only ever rises. The third row never happens.

What a restart does lose is the pulses no one counted: those the meter sent while the PLC was off,
and those counted since the last publish before it went down — at most ten seconds' worth.

The value on the entity itself is consumption since the PLC last started, and means nothing on its
own. Read the statistics, never the state.

:bulb: **Changing `MeterType` or `GenericUnit` changes the unit of an entity Home Assistant already
keeps statistics for.** Home Assistant does not convert them silently; it raises a repair under
*Settings → Repairs*, and offers to convert or clear the history. `PulseWeight` is free to change:
it affects only the pulses that follow.

### **Meter types**

`MeterType` decides the unit and the Home Assistant `device_class` together, because Home Assistant **validates them as a set**, and drops an entity whose
unit is not one its device class allows. Choosing from a list makes that combination impossible
to get wrong.

| `MeterType` | `Total` unit | `device_class` | Energy dashboard |
|:--|:--|:--|:--|
| `WATER_L` | L | `water` | Water consumption |
| `WATER_M3` | m³ | `water` | Water consumption |
| `GAS_M3` | m³ | `gas` | Gas consumption |
| `ENERGY_WH` | Wh | `energy` | Electricity, or individual devices |
| `ENERGY_KWH` | kWh | `energy` | Electricity, or individual devices |
| `GENERIC` | `GenericUnit` | — | — |

:rotating_light: **`GenericUnit` must be plain ASCII.** A CODESYS `STRING` is bytes, and a
non-ASCII character typed into it reaches Home Assistant as two characters that look like one —
`m³` arrives as `mÂ³`. The meter types above carry their units inside the block, written correctly
once, which is the other reason to prefer them. A generic meter in cubic metres should say `m3`.

### **How fast it can count**

The block counts edges it sees on the PLC's scan, so a pulse has to be long enough to be seen,
and to get through `MinPulseTime`, both high and low. With the task's cycle time `t_cycle`:

```
shortest pulse it counts   = max(MinPulseTime, t_cycle) + t_cycle
highest pulse rate         ≈ 1 / (2 × that)
```

With `MinPulseTime := T#20MS`, on a 10 ms task, that is about **16 pulses per second**:

| Meter | At | Pulses per second | Counts at 20 ms? |
|:--|:--|:--|:--|
| Water, 1 L/pulse | 30 L/min, every tap open | 0.5 | yes |
| Gas, 0.01 m³/pulse | 4 m³/h, a large boiler | 0.1 | yes |
| kWh, 1000 imp/kWh | 25 kW, a whole house at full load | 7 | yes |
| kWh, 10000 imp/kWh | 25 kW | 70 | **no** — its pulses are shorter than 20 ms |

A meter beyond that needs a lower `MinPulseTime` or a faster task. The block reads an ordinary
digital input only. The digital input module's own input filter — 3 ms on most 750-4xx modules —
adds to the shortest pulse, and does nothing to remove reed bounce longer than it.

### **MQTT publish behavior**

Set `FriendlyName` at the declaration and the block wires itself; see the code example below.

| output | MQTT topic suffix | Payload | QoS | Retain flag | Published |
|:--|:--|:--|:--|:--|:--|
| `Total` | `/TOTAL` | decimal, in the `Total` unit | 2 | `TRUE` | `0` once at startup; then on a change, no more than once every 10 s; and every 5 minutes regardless |

`/TOTAL` is retained so a Home Assistant that restarts picks up where the count is, rather than
waiting for the next pulse.

The two intervals are constants inside the block, not settings. Ten seconds keeps a fast meter —
a 1000 imp/kWh meter under a 10 kW load pulses three times a second — from filling the publish
queue, and is far finer than the five minutes Home Assistant's statistics resolve to. The
five-minute republish lets a quiet meter be told from a stopped PLC.

It is formatted from an integer rather than through `LREAL_TO_STRING`, so `1234.567` is published
as `1234.567` and not `1234.5670000000001`, with as many decimals as `PulseWeight` has, up to
six — a 1 L meter in m³ shows three, a 10 L meter two.

The block takes no commands, and subscribes to nothing.

The publish topic is `GVL_MQTT.MqttPubCounterPrefix` plus the instance name, so the instance in the
code example publishes to `Devices/PLC/Lab/Out/Counters/fbDiPulse001/TOTAL`.

### **Code example**

The declaration is the whole configuration — what the meter is through `FB_init`, the Home
Assistant name through the initialiser:

```
fbDiPulse001 : FB_INPUT_PULSE_COUNTER_MQTT(
                   MeterType    := E_PULSE_METER_TYPE.WATER_M3,
                   PulseWeight  := 0.001,                         (* 1 L per pulse *)
                   GenericUnit  := '',
                   MinPulseTime := T#20MS)
               := (FriendlyName := 'Water meter');
```

A kWh meter with a fast S0 output, and a meter Home Assistant has no device class for:

```
fbDiPulse002 : FB_INPUT_PULSE_COUNTER_MQTT(
                   MeterType    := E_PULSE_METER_TYPE.ENERGY_KWH,
                   PulseWeight  := 0.0001,                        (* 10000 imp/kWh *)
                   GenericUnit  := '',
                   MinPulseTime := T#5MS)
               := (FriendlyName := 'Heat pump energy');

fbDiPulse003 : FB_INPUT_PULSE_COUNTER_MQTT(
                   MeterType    := E_PULSE_METER_TYPE.GENERIC,
                   PulseWeight  := 1.0,
                   GenericUnit  := 'bales',
                   MinPulseTime := T#20MS)
               := (FriendlyName := 'Hay baler');
```

Then call it cyclically with the input signal only:

```
fbDiPulse001(Pulse := DI_009, ProcessImageValid := Pfc200Bus.xConfigFinished);
```

:rotating_light: **Change a constructor argument in the CODESYS IDE.** CODESYS keeps an instance's
`FB_init` arguments in a store beside the declaration text, and compiles from the store. The IDE
updates both. A scripted edit of the declaration text updates only the text: it builds clean,
reads correctly, and the PLC goes on running the old value. Arguments written into a **new**
instance are not affected — there is no stored value yet for the text to lose to.

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from `GVL_MQTT` on its
first cyclic call. **A block wired this way must be called cyclically** — an instance whose body
never runs stays unwired and never appears in Home Assistant, and nothing warns about it.

### **Home Assistant**

The block announces one sensor on the PLC device, named *FriendlyName*, with `device_class` and
unit per `MeterType` and `state_class: total_increasing`. No YAML is needed.

#### Consumption per day, week and month

`state_class: total_increasing` is what makes Home Assistant keep **long-term statistics** for the
entity: a value for every hour, kept indefinitely — unlike the raw state history, which
the recorder purges after ten days. Every day, week and month figure below is built from those
hourly values, so nothing about periods is computed in the PLC, which has no reliable notion of the
local calendar to compute it with.

**The energy dashboard** (*Settings → Dashboards → Energy*). Add the entity under *Water
consumption*, *Gas consumption*, *Electricity grid* or *Individual devices*, according to
`MeterType`. The dashboard then shows consumption per day, week, month and year, and can attach a
price per unit. A `GENERIC` meter has no device class and does not appear there.

**A statistics graph card**, for any meter, `GENERIC` included — consumption per period, as bars:

```yaml
type: statistics-graph
title: Water per day
entities:
  - sensor.water_meter
period: day          # or week, month
stat_types:
  - change
chart_type: bar
days_to_show: 30
```

**A utility meter helper**, for a number to put on a card or use in an automation — *this month's
water*, resetting on the first (*Settings → Devices & services → Helpers → Utility Meter*, or):

```yaml
utility_meter:
  water_monthly:
    source: sensor.water_meter
    cycle: monthly
```

The helper counts from when it was created; the energy dashboard and the statistics card read the
history the recorder already has. A utility meter treats a falling source the same way the
statistics do, so it, too, carries on across a PLC restart.

**A live flow or power reading** is not something the block publishes: a pulse meter knows how
much has passed, not how fast. Where one is wanted, Home Assistant's *Derivative* helper computes
it from the entity, with a time window to smooth out the steps a pulse meter makes.
