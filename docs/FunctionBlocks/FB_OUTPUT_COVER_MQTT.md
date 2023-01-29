## FB_OUTPUT_COVER_MQTT
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)

### **General**

The cover function block allows you to control covers such as a roller shutter or a garage door. A time variable (`T_UD`) is required that specifies the time to close/open a cover completely. The cover can be controled via MQTT using 'OPEN/STOP/CLOSE' commands or via a digital 'TOGGLE' input that will switch between 'OPEN/STOP/CLOSE' states.
---

:rotating_light: Do not use this function block if the mechanical safety on your electric roller shutters hasn't been configured properly!

---

### **Block diagram**

<img src="../_img/FB_OUTPUT_COVER_MQTT.svg" width="350">

INPUT(S)

- TOGGLE: toggles the direction of the cover.
- PRIO_LOCK: bool input, when high the cover will be locked in its current position ignoring all other inputs. (\*)
- PRIO_UP: bool input, when high the cover will receive a constant signal to move up with a maximum time of twice `T_UD`. (\*)
- PRIO_DN: bool input, when low the cover will receive a constant signal to move down with a maximum time of twice `T_UD`. (\*)

(\*) When high, all incoming MQTT commands and the TOGGLE input will be ignored.

OUTPUT(S)

- MU: bool output, motor up signal.
- MD: bool output, motor down signal.

METHOD(S)

- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
  - `MQTTPublishPrefix`: datatype _POINTER TO STRING_, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. The suffix is automatically set to FB name.
  - `pMqttPublishQueue`: datatype _POINTER TO FB_MqttPublishQueue_, pointer to the MQTT queue to publish messages.

- ConfigureFunctionBlock: configures the behaviour of the cover using the parameters below:
  - `T_LOCKOUT`: delay between change of direction.
  - `T_UD`: run time to move the cover completely up/down.

- PublishReceived: callback method called by the callbackcollector when a message is received on the subscribed topic by the callbackcollector.

### **MQTT Event Behaviour**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                   | Description                           | MQTT payload | QoS                                  | Retain flag | Published on startup |
| :---------------------- | :------------------------------------ | :----------- | :----------------------------------- | :---------- | :------------------- |
| **Cover reaches position** | Cover reaches a open or closed position | `OPEN` or `CLOSED` | 2 | `TRUE`      | no                  |

MQTT publish topic is a concatination of the publish prefix and the function block name.

### **MQTT Subscription Behaviour**

Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command                    | Description                                                                 | expected payload | Additional notes                                                   |
| :------------------------- | :-------------------------------------------------------------------------- | :--------------- | :----------------------------------------------------------------- |
| **Open cover**             | Request to open the cover.                                                  | `OPEN`           | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low. |
| **Close cover**            | Request to close the cover.                                                 | `CLOSE`          | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low. |
| **Stop cover**             | Request to stop the cover from moving.                                      | `STOP`           | Command only executed when `PRIO_UP` and `PRIO_DN` inputs are low. |

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name.


### **Code example**

- variables initiation:

```
MqttPubCoverPrefix			:STRING(100) := 'Devices/PLC/House/Out/Covers/';
MqttSubCoverPrefix			:STRING(100) := 'Devices/PLC/House/In/Covers/';
FB_DO_COVER_001				:FB_OUTPUT_COVER_MQTT;
```

- Init MQTT method call (called once during startup):

```
FB_DO_COVER_001.InitMqtt(MQTTPublishPrefix:= ADR(MqttPubCoverPrefix),               (* pointer to string prefix for the mqtt publish topic *)
    MQTTSubscribePrefix:= ADR(MqttSubCoverPrefix),                                  (* pointer to string prefix for the mqtt subscribe topic *)
    pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue),                     (* pointer to MqttPublishQueue to send a new Mqtt event *)
    pMqttCallbackCollector := ADR(MqttVariables.collector_FB_OUTPUT_COVER_MQTT)     (* pointer to CallbackCollector to receive Mqtt subscription events *)
);
```

- Init configuration method call (called once during startup):

```
FB_DO_COVER_001.ConfigureFunctionBlock(T_LOCKOUT:=T#1S,                             (* delay between change of direction *)
    T_UD:=T#20S                                                                     (* run time to move the cover completely up/down *)
);
```

- checking for events to move the cover (cyclic):

```
FB_DO_COVER_001(
    TOGGLE:=DI_002,                                                                 (* digital input to receive signal to toggle cover direction *)
    MU=>DO_001,                                                                     (* digital output to couple to cover motor up wire *)
    MD=>DO_002                                                                      (* digital output to couple to cover motor down wire *)
    );
```

- integration with `FB_INPUT_PUSHBUTTON_MQTT`:

```
FB_DO_COVER_001(
    TOGGLE:=FB_DI_PB_001.P_LONG,                                                    (* move cover during a longpush on input pushbutton 1 *)
    MU=>DO_001,                                                                     (* digital output to couple to cover motor up wire *)
    MD=>DO_002                                                                      (* digital output to couple to cover motor down wire *)
    );
```

### **Wiring**

#### **Using SPDT relays**

Using two SPDT relays it's possible to wire an AC or DC motor so that shortciruiting the motor is impossible.

|                        AC Wiring                         |                        DC Wiring                         |
| :------------------------------------------------------: | :------------------------------------------------------: |
| ![AC Wiring](../_img/FB_OUTPUT_COVER_MQTT-Wiring_AC.png) | ![DC Wiring](../_img/FB_OUTPUT_COVER_MQTT-Wiring_DC.png) |

#### **Using ELTAKOs**

If two SPDT relays for each cover from the appraoch above consumes to much place in your electricity installation you can opt for (more costly) ELTAKOs.

|                       AC Wiring (uses MTR12-UC)                        |                       DC Wiring (uses DCM12-UC)                        |
| :--------------------------------------------------------------------: | :--------------------------------------------------------------------: |
| ![AC ELTAKO Wiring](../_img/FB_OUTPUT_COVER_MQTT-Wiring_ELTAKO_AC.png) | ![DC ELTAKO Wiring](../_img/FB_OUTPUT_COVER_MQTT-Wiring_ELTAKO_DC.png) |

### **Home Assistant YAML**

If [MQTT discovery](../AdditionalFunctionality/MQTT_Discovery.md) is not working for you, you can use the YAML code below in your [MQTT cover](https://www.home-assistant.io/components/cover.mqtt/) config:

```YAML
mqtt:
  cover:
  - name: "FB_DO_COVER_001"
    state_topic: "Devices/PLC/House/Out/Covers/FB_DO_COVER_001"
    state_open: "OPEN"
    state_closed: "CLOSED"
    command_topic: "Devices/PLC/House/In/Covers/FB_DO_COVER_001"
    payload_open: "OPEN"
    payload_close: "CLOSE"
    payload_stop: "STOP"
    qos: 2
    optimistic: false
    availability_topic: "Devices/PLC/House/availability"
    payload_available: "online"
    payload_not_available: "offline"
```
