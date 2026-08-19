## FB_INPUT_TEMPERATURE_RTD_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Publishes a temperature read by an **RTD input module** — a Pt1000 on a WAGO
[750-463](https://www.wago.com/global/i-o-systems/4-channel-analog-input/p/750-463) is what it
was written for — and announces it to Home Assistant as a temperature sensor with a diagnostic
fault flag beside it.

**There is no scaling to configure and no calibration to do.** The module puts *tenths of a
degree Celsius* in the process image, two's complement, so `213` is 21.3 °C and `-105` is
-10.5 °C. Wire the channel word straight to `Raw` and the block is configured:

```
FB_AI_RTD_001(Raw := RTD_001);
```

Everything else is a default that can be changed while the PLC runs, which is deliberate — none
of it lives in `FB_init`, so none of it is stuck behind the IDE (see
[CLAUDE.md](../../CLAUDE.md) for why that matters here).

:bulb: **This block reads a channel; it does not configure the module.** Which sensor type a
channel measures — Pt1000, Ni1000, KTY81, or a plain resistance range — is a setting inside the
module, not something IEC code can reach in this project's device configuration. See
[wiring an RTD sensor](../AnalogInputs/UsingRTDSensors.md).

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────────────────┐
       │   FB_INPUT_TEMPERATURE_RTD_MQTT   │
       ├───────────────────────────────────┤
 INT ──┤ Raw                   Temperature ├── REAL
REAL ──┤ PublishDeadband             Valid ├── BOOL
TIME ──┤ HeartbeatInterval           Fault ├── BOOL
       │                     DataAvailable ├── BOOL
       └───────────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Raw` | INT | The mapped channel word of the RTD module, in tenths of a degree Celsius. Wire it to the channel variable — `Raw := RTD_001` — and nothing else is needed to make the block work. |
| `PublishDeadband` | REAL | Degrees Celsius of change required before the value is published again. Defaults to 0.2. The last digit of an RTD channel jitters continuously, and nobody wants 0.1 °C of noise in their history; zero publishes every change. |
| `HeartbeatInterval` | TIME | Republish even when nothing changed, so a reader can tell a steady temperature from a PLC that has stopped. Defaults to 5 minutes, and the discovery config's `expire_after` is set to three of these — so changing it changes both, but only for entities announced after the change. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `Temperature` | REAL | Degrees Celsius. **Held** at the last trustworthy reading while `Fault` is set, rather than following the channel into whatever it reports for a broken wire. |
| `Valid` | BOOL | The channel is reading a real sensor, within the range this sensor type can measure. |
| `Fault` | BOOL | Open circuit, short, or a reading outside what a platinum RTD can produce. The usual cause is a wire that has come out of a terminal; the second most usual is a channel configured for a different sensor type than the one connected. |
| `DataAvailable` | BOOL | High once a plausible reading has been seen. Low only at startup — and it stays low on a channel that has never been wired. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup. Not needed when `FriendlyName` is set at the declaration: the block then wires itself.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |

**`InitMqttDiscovery`** — Publishes the Home Assistant MQTT discovery configs — a temperature sensor and a diagnostic fault flag — so both entities are created automatically. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. An RTD channel is part of the PLC rather than a device of its own. |
| `Name` | STRING(255) |  | Name of the entity in Home Assistant. The self-wiring prologue passes `FriendlyName`. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
<!-- fb-interface:end -->

### **Code example**

Declare the instance where the program's other input blocks live, and let it wire itself:

```
FB_AI_RTD_001 : FB_INPUT_TEMPERATURE_RTD_MQTT := (FriendlyName := 'Buffer tank top');
```

Then call it cyclically, handing it the module channel:

```
FB_AI_RTD_001(Raw := RTD_001);
```

`RTD_001` is the variable the module's channel 0 is mapped to in the device tree's I/O mapping —
map the channel first, or the name will not resolve.

No `InitMqtt` or `InitMqttDiscovery` call is needed: the block wires itself from `MqttVariables`
on its first cyclic call. **A block wired this way must be called cyclically** — an instance
whose body never runs stays unwired and never appears in Home Assistant, and nothing warns about
it.

### **MQTT publish behavior**

| output | MQTT topic suffix | Unit | Published |
|:--|:--|:--|:--|
| `Temperature` | `/TEMP` | °C | on a change beyond `PublishDeadband`, on the heartbeat, and once at startup — **never while `Fault` is set** |
| `Fault` | `/FAULT` | — | `ON` / `OFF`, **only when it changes**, plus once at startup so a retained value exists |

One decimal, always, formatted from the integer rather than through `REAL_TO_STRING` — which
would publish `21.299999` for a channel reading `213`. One decimal is all the module has, and
all anyone should be told it has.

### **A broken wire is not a temperature**

An RTD module reports a dead sensor by driving the channel to the end of its range, and both
which end and which exact value depend on the module and on how it was configured. This block
therefore does not look for a fault code. It asks the only question with a stable answer:
**could a platinum RTD produce this reading at all?** Anything outside -200 °C to +850 °C — the
range IEC 60751 defines for the type — is the module talking about the wiring rather than the
temperature.

What follows from that:

- `Temperature` **holds** its last trustworthy value, so a chart shows the reading stopping
  rather than a plunge to some sentinel.
- Nothing is published to `/TEMP` while the fault lasts. The discovery config carries
  `expire_after` at three heartbeats, so Home Assistant retires the entity on its own if the
  silence lasts — which is a truer signal than a made-up number, or a fault code dressed up as
  a temperature.
- `/FAULT` goes `ON` immediately, as a **diagnostic** `problem` entity. A wire out of a terminal
  is a maintenance fact, not something for a dashboard.

:bulb: **A channel that reads a plausible but wrong temperature is the one case this cannot
catch.** Configure a channel for Pt100 and connect a Pt1000 and the reading is not out of range,
it is simply wrong — roughly 2.6 times the true value in the middle of the scale. Compare
against a second thermometer once, at commissioning; after that the fault flag covers what can
be covered automatically.

### **Home Assistant**

The block publishes its own discovery configs, so no YAML is needed. Both entities appear under
the PLC's own device:

| Entity | Category | `device_class` | `state_class` | Unit |
|:--|:--|:--|:--|:--|
| *FriendlyName* | — | `temperature` | `measurement` | °C |
| *FriendlyName* sensor fault | diagnostic | `problem` | — | — |

`state_class: measurement` is set on purpose, unlike on the rangefinder: a temperature is
exactly the kind of quantity whose mean, minimum and maximum are worth keeping, so Home
Assistant's long-term statistics earn their place here.
