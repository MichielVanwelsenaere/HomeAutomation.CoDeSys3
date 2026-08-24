## User LEDs (CODESYS 3S runtime)

### **General**

It's possible to control the *U* LEDs on a WAGO PFC controller, which makes the state of the PLC readable from the cabinet without a laptop. The project uses two of them.

### **Prerequisites**
The following libraries should be present:

- CmpPfcx00

### **U1: MQTT broker health**

Steady green while the PLC can talk to the broker, blinking red while it cannot.
Two programs are involved, because one measurement is not enough:

| Where | What it contributes |
|:--|:--|
| `PRG_PING_DMX` (Ping task, 10 s) | Pings the broker and writes `GVL_MQTT.bBrokerReachable`. |
| `PRG_MQTT` (MqttCommunication task) | Owns the LED. `bBrokerHealthy := MQTT_CONNECTED AND bBrokerReachable`. |

```
(* PRG_MQTT: the client reports its own state on an output, so copy it in first *)
stMQTTInfo := MQTT_IN_OUT.clientFB.MQTT_INFO;

bBrokerHealthy := stMQTTInfo.MQTT_CONNECTED AND GVL_MQTT.bBrokerReachable;

IF bBrokerHealthy <> bLedShowsHealthy THEN
     IF bBrokerHealthy THEN
          PFC.SetLed(which := PFC.LED.U1, how := PFC.LedState.STATIC_GRN);
     ELSE
          PFC.SetLed(which := PFC.LED.U1, how := PFC.LedState.BLINK_RED);
     END_IF
     bLedShowsHealthy := bBrokerHealthy;
END_IF
```

#### Why the reachability half is not redundant

**`MQTT_CONNECTED` does not notice a pulled network cable.** TCP has nothing to
report when a cable comes out — no FIN, no RST — so the socket stays open until a
retransmit finally gives up, which is minutes rather than seconds. The client goes on
claiming a session the whole time. Measured on the lab PFC200: cable out,
`MQTT_CONNECTED` still `TRUE`, U1 still green.

ICMP notices in one task cycle, so the ping is what covers that case. The two
measurements cover each other:

| | ping | `MQTT_CONNECTED` | U1 |
|:--|:--|:--|:--|
| all well | answers | TRUE | green |
| cable out, switch dead, broker host down | fails | stays TRUE for minutes | **red, from the ping** |
| host up, broker process stopped | answers | goes FALSE (clean TCP close) | **red, from the client** |

Detection is within about 20 s of a cable coming out, and within 10 s of it going
back in. Shorten the Ping task period if that is not quick enough.

#### Three things about the implementation

- **`stMQTTInfo` has to be populated.** `MQTT.MQTT_INFO` is an *output* of the
  library's `MqttClient` — not a struct that fills itself in. Declaring one and
  reading `MQTT_CONNECTED` off it compiles perfectly and reads `FALSE` for ever,
  which is what it did here for the whole history of the project.
- **One code path, not two edge detectors.** U1 is written when
  `bBrokerHealthy` differs from `bLedShowsHealthy`, so `SetLed` is still called only
  on a change but there is no second branch that can be left uncalled. Two detectors
  is how this was broken before: the falling-edge one was called once, from
  `MQTT_INIT`, so its `Q` could never become `TRUE` and the LED could never go red,
  while the rising-edge half looked perfectly fine. `bLedShowsHealthy` also reports
  what the LED is showing, which a one-cycle `Q` cannot.
- **The LED needs a starting value.** A change detector writes nothing when nothing
  has changed, so `MQTT_INIT` sets U1 red and `bLedShowsHealthy := FALSE` once. A PLC
  that never reaches the broker at all then says so, rather than showing whatever the
  runtime left on it.

The MQTT session's own rising edge still drives the availability birth message, so a
reconnect is announced immediately rather than waiting for the next heartbeat.

`MQTT_INFO` carries an `MQTT_ERROR` string alongside the flag, empty while the
connection is healthy. Nothing reads it yet; it is the obvious input for a
diagnostic log message.

### **U3: DMX / Art-Net node reachability**

Lives in `PRG_PING_DMX`. The LED turns green when the Art-Net node answers a ping and flashes red when it stops responding or the send step reports an error:

```
PFC.SetLed(which:=PFC.LED.U3, how:=PFC.LedState.STATIC_GRN);
GVL_MQTT.PLC_Device.SendLogMessage('DMX ping OK');
```

### **`SysSockPing` returns more than two things**

`0` is success and `5` is unreachable — both confirmed on this hardware, the second by
pointing the broker ping at `192.0.2.1`. But **it also returns `1` occasionally
against a host that is answering perfectly well**, which is why the U3 code has always
ignored any return that is neither `0` nor `5`, and why the broker ping counts
consecutive failures rather than acting on one:

```
IF udiBrokerReachable = 0 THEN
     uiBrokerPingFails := 0;
ELSIF uiBrokerPingFails < cuiBrokerPingFailsForRed THEN
     uiBrokerPingFails := uiBrokerPingFails + 1;
END_IF
GVL_MQTT.bBrokerReachable := (uiBrokerPingFails < cuiBrokerPingFailsForRed);
```

Counting is better than enumerating the codes: an unknown return still counts as a
failure, but no single one of them can flip the light. A success clears the count
immediately, so recovery stays as fast as the task.

### **Adding your own**

`PFC.SetLed` takes the LED (`PFC.LED.U1` … `U3`) and the state (`PFC.LedState.STATIC_GRN`, `BLINK_RED`, and the other members of that enum). Write it only when the state changes — but from a remembered state rather than a pair of edge detectors, and set an initial value somewhere that runs once, because a state machine that only writes on transitions says nothing about where it started.

### **Testing one**

An LED is a runtime call, so no variable holds its colour and no test can read it
back: the only witness for the light itself is a person looking at the controller.
Say which half you tested.

What *is* assertable is everything that decides the colour, including the last value
written — `bLedShowsHealthy`. And the input can be driven for real rather than forced:
pointing `GVL_MQTT.broker` at `192.0.2.1`, which RFC 5737 reserves and which can
therefore never be a host, makes the ping genuinely fail while leaving the MQTT
session up — the pulled-cable case exactly.
`.claude/skills/test-plc-logic/specs/mqtt-broker-led.json` does that, and the
[`test-plc-logic`](../../.claude/skills/test-plc-logic/SKILL.md) skill has the rest.
