## FB_OUTPUT_COVER_PULSE_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

A cover whose motor controller takes **one** command input and steps through
**OPEN → STOP → CLOSE → STOP → OPEN …** on every contact closure, and reports its end
positions on two contacts of its own. Garage doors, gates and many self-contained cover
controllers work this way: they run the motor, count its travel and stop at the ends
themselves, so all the PLC ever gives them is a short pulse.

A pulse cannot say which way to go. This block therefore keeps a model of the controller -
moving or not, and the direction of its last travel - and works out how many pulses a
Home Assistant `OPEN`, `CLOSE` or `STOP` needs. The end contacts correct the model every time
they change, including when the cover was moved with the controller's own key switch or button.

It is the sibling of [`FB_OUTPUT_COVER_MQTT`](FB_OUTPUT_COVER_MQTT.md), which drives a motor
through two relays (up and down) and times the travel itself. Use this one when the motor has
its own controller with a single step input; use that one when the PLC switches the motor.

:rotating_light: **A cover that closes by remote control can close over somebody.** These
controllers usually come with a key switch so that whoever closes it can see the cover. Keep
automations from closing it unattended, or put a confirmation in front of the command.

:bulb: **Measure a full travel** and set `T_Travel` to about 1.2× that. It is the only way the
block learns that a cover stopped half-way without a command from it.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌────────────────────────────┐
       │ FB_OUTPUT_COVER_PULSE_MQTT │
       ├────────────────────────────┤
BOOL ──┤ IsOpen               PULSE ├── BOOL
BOOL ──┤ IsClosed            Moving ├── BOOL
BOOL ──┤ TOGGLE               Fault ├── BOOL
TIME ──┤ T_Pulse                    │
TIME ──┤ T_PulseGap                 │
TIME ──┤ T_Travel                   │
TIME ──┤ T_Confirm                  │
       └────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `IsOpen` | BOOL |  | The controller's "fully open" contact. |
| `IsClosed` | BOOL |  | The controller's "fully closed" contact. |
| `TOGGLE` | BOOL |  | A rising edge sends one pulse, exactly as the controller's own button would. Drops any command still being worked through. |
| `T_Pulse` | TIME | `TIME#800ms` | How long the contact is closed per pulse: long enough for the controller to see it, short enough not to read as a held button. |
| `T_PulseGap` | TIME | `TIME#1s0ms` | Contact open between two pulses of one command, e.g. a stop and the start the other way. |
| `T_Travel` | TIME | `TIME#3m0s0ms` | Longer than the slowest full travel. A cover believed to be moving for this long without reaching an end contact is taken to have stopped half-way. |
| `T_Confirm` | TIME | `TIME#5s0ms` | How long an end contact may take to drop once the cover starts away from it. Still made after this, the controller took the pulse as a stop. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PULSE` | BOOL | The command contact. Drive it through a potential-free relay contact: these controllers supply their own control voltage on that input. |
| `Moving` | BOOL | The cover is believed to be moving. |
| `Fault` | BOOL | The last command could not be carried out, or both end contacts are made at once. Details on the diagnostic log. |

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
| `DeviceClass` | STRING(50) | `''` | Home Assistant device class for the entity. Leave empty for the default. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **How a command becomes pulses**

A pulse on a moving cover stops it; a pulse on a cover at rest starts it the other way from its
last travel. So:

| Cover is | `OPEN` sends | `CLOSE` sends | `STOP` sends |
|:--|:--|:--|:--|
| fully closed | 1 pulse (opens) | nothing | nothing |
| fully open | nothing | 1 pulse (closes) | nothing |
| opening | nothing | 2 pulses (stop, close) | 1 pulse |
| closing | 2 pulses (stop, open) | nothing | 1 pulse |
| stopped half-way, last went up | 3 pulses (close, stop, open) | 1 pulse | nothing |
| stopped half-way, last went down | 1 pulse | 3 pulses (open, stop, close) | nothing |

Three pulses means the cover moves the wrong way for about `T_Pulse` + `T_PulseGap` before it
turns round. A single step input cannot do better. Pulses are `T_PulseGap` apart, and a command
is done once the model has the cover where it was asked or on its way there: the controller
finishes the travel by itself.

### **What the end contacts correct**

| Contact | Means |
|:--|:--|
| `IsOpen` or `IsClosed` made | The travel is over and went that way. Also how the block learns its first direction at power-up. |
| `IsOpen` drops | The cover is closing, whoever started it. |
| `IsClosed` drops | The cover is opening, whoever started it. |
| both made | A wiring fault, not a position: `Fault`, state `STOPPED`, and nothing is sent while it lasts. |

**Whether reaching an end counts as the STOP step is up to the controller.** If it does not, the
first pulse at an end is taken as a stop and the cover does not move. The block checks that the
end contact drops within `T_Confirm` of a pulse that should have left it; if it did not, it
corrects the model and sends one more. A second miss in a row means the controller is not moving
at all (locked out, in error, key switch off): the command is dropped, `Fault` goes TRUE and the
reason goes to the diagnostic log.

**What it cannot see** is a stop made half-way at the controller's own key switch or button.
The block then believes the cover is still moving until `T_Travel` runs out, shows `OPENING` or
`CLOSING` meanwhile, and a `STOP` sent in that window would start the cover instead. A travel
started at the key switch *from an end* is seen, because the end contact drops.

### **Persistent variables**

`iDir`, the direction of the last travel, is `VAR PERSISTENT`: the controller keeps that state
across a PLC restart, and a cover resting half-way gives no other clue to it. Add the instance
path to the application's persistent variable list - in the IDE, *Add all instance paths* - or
the compiler warns and the direction is lost on every restart:

```
PRG_MAIN.fbDoCover001.iDir: INT;
```

Without it, a cover resting half-way after a restart is assumed to open on the next pulse; the
next end contact puts the model right.

### **MQTT publish behavior**

Requires method call `InitMqtt` to enable MQTT capabilities, or `FriendlyName` set at the
declaration.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
| :-- | :-- | :-- | :-- | :-- | :-- |
| **State change** | The cover reaches an end, starts moving or stops half-way | `OPEN`, `CLOSED`, `OPENING`, `CLOSING` or `STOPPED` | 2 | `TRUE` | yes |
| **Fault** | Both end contacts made, the cover did not leave an end after two pulses, or a command was given up | text, on the PLC's diagnostic `Log` topic | 1 | `TRUE` | no |

`STOPPED` covers both "stopped half-way" and "position unknown": with neither end contact made
there is nothing else to say. MQTT publish topic is a concatenation of the publish prefix and the
function block name.

### **MQTT subscribe behavior**

| Command | Description | expected payload |
| :-- | :-- | :-- |
| **Open cover** | Pulse until the cover is opening or open. | `OPEN` |
| **Close cover** | Pulse until the cover is closing or closed. | `CLOSE` |
| **Stop cover** | One pulse if the cover is believed to be moving. | `STOP` |

A new command replaces the one being worked through. MQTT subscription topic is a concatenation
of the subscribe prefix and the function block name. The block shares the cover prefix and the
cover callback collector with `FB_OUTPUT_COVER_MQTT`.

### **Code example**

- declaration - `FriendlyName` makes the block wire itself to MQTT and announce itself to Home
  Assistant on its first cycle:
```
fbDoCover001	: FB_OUTPUT_COVER_PULSE_MQTT := (FriendlyName := 'Garage door');
```

- cyclic call:
```
fbDoCover001(
	IsOpen		:= DI_001,		(* controller's "fully open" relay *)
	IsClosed	:= DI_002,		(* controller's "fully closed" relay *)
	TOGGLE		:= fbDiPb001.SINGLE,	(* optional local pushbutton: one step *)
	T_Travel	:= T#90S,		(* about 1.2x a measured full travel *)
	PULSE		=> DO_001		(* coupling relay whose dry contact is the step input *)
);
```

### **Wiring**

- **`PULSE`** drives a coupling relay; its **potential-free** contact goes to the controller's
  step input. These inputs carry the controller's own control voltage - never wire a PLC output
  straight into them.
- **`IsOpen` / `IsClosed`** come from the controller's end-position relays, NO and COM, switching
  whatever the PLC's input terminal expects (24 VDC or 230 VAC, within the relay's rating).
- The controller has to be in its **pulse** (automatic) mode, not hold-to-run: in hold-to-run a
  pulse moves the cover for `T_Pulse` and no further.
