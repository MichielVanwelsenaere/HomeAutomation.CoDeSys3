## FB_OUTPUT_DIMMER_DALI_MQTT
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)

### **General**

Can be controlled using pulses from [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md), maintains output state through power cycles. Sets the driver fade time and fade rate setting. Allows dimming via a long persistent push on a pushbutton. Performs periodic writes to the DALI address to avoid state issues. 

DALI configuration via the Wago DALI tool and creation of the `typBallast` is explained pretty well in [this video](https://www.youtube.com/watch?v=FaoOY2-VFVk).

----------------------------

:rotating_light: **Not part of the reference project.** This function block needs the WAGO DALI module and the WAGO DALI libraries, which are only available on **G2** PFC devices (see [Choosing and preparing your WAGO PFC device](../WagoPfcPrep.md)). The CODESYS conversion was done on G1 hardware, so the block could not be built or tested and has been removed from `HomeAutomation.project`; the call sites in `PLC_PRG_MAIN` are commented out.

It is kept as a standalone PLCopen export so it can be imported into a G2 project: **[src/Exports/archive/FB_OUTPUT_DIMMER_DALI_MQTT.xml](../../src/Exports/archive/FB_OUTPUT_DIMMER_DALI_MQTT.xml)**. See [Restoring it into a project](#restoring-it-into-a-project) below. It is unverified on CODESYS — please report back if you get it running.

----------------------------

### **Restoring it into a project**

1. In CODESYS, select the POUs top level item and choose *Project* &rarr; *Import PLCopenXML*.
2. Browse to [src/Exports/archive/FB_OUTPUT_DIMMER_DALI_MQTT.xml](../../src/Exports/archive/FB_OUTPUT_DIMMER_DALI_MQTT.xml) and import it.
3. Resolve the dependencies it expects:
   - `FB_MQTT_BASE` and `FB_MqttPublishQueue` — already in the reference project.
   - `MQTT.MQTT_SUBSCRIBE_CALLBACK`, `MQTT.CallbackCollector`, `MQTT.CALLBACK_DATA` — the CODESYS MQTT library.
   - `typBallast`, `FbDaliSendDimValue`, `FbDaliSendFadeRate`, `FbDaliSendFadeTime` — the WAGO DALI library, **G2 only**.
4. Uncomment the DALI blocks in the `MAIN_INIT` and `DALI` actions of `PLC_PRG_MAIN`.

### **Block diagram**

```text
             ┌────────────────────────────┐
             │ FB_OUTPUT_DIMMER_DALI_MQTT │
             ├────────────────────────────┤
TYPBALLAST ──┤ BALLAST         STATUS_LED ├── BOOL
      BOOL ──┤ TOGGLE                     │
      BOOL ──┤ P_LONG                     │
      BOOL ──┤ PRIO_HIGH                  │
      BOOL ──┤ PRIO_LOW                   │
             └────────────────────────────┘
```

> This diagram is a frozen snapshot of the archived export, not generated from `PLCopen.xml` like the other function blocks — the block is no longer in the project to generate it from.

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `BALLAST` | typBallast | The `typBallast` this function block drives. |
| `TOGGLE` | BOOL | Connect to one or more `SINGLE` outputs of [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `P_LONG` | BOOL | Connect to one or more `P_LONG` outputs of [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `PRIO_HIGH` | BOOL | When high the light is set to maximum brightness, overriding the other inputs. |
| `PRIO_LOW` | BOOL | When high the light is switched off, overriding the other inputs. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `STATUS_LED` | BOOL | High when the light intensity is greater than 0, low otherwise. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`ConfigureFunctionBlock`** — Overrides the default behaviour characteristics. Only needed when the defaults do not suit.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `FadeTime` | BYTE |  | Driver fade time, see the table below. |
| `FadeRate` | BYTE |  | Driver fade rate, see the table below. |

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

### Fade Time and Fade Rate 

Can be configured using `ConfigureFunctionBlock` method call.

| Value    | Fade time [s]  | Fade rate [fades/s] | 
| :--------| :--------------| :-------------------|
| 0 | Extended fade | not applicable
| 1 | 0.707 | 357.796
| 2 | 1.0 | 253.0
| 3 | 1.414 | 178.898
| 4 | 2.0 | 126.5
| 5 | 2.828 | 89.449
| 6 | 4.0 | 63.25
| 7 | 5.657 | 44.725
| 8 | 8.0 | 31.625
| 9 | 11.314 | 22.362
| 10 | 16.0 | 15.813
| 11 | 22.627 | 11.181
| 12 | 32.0 | 7.906
| 13 | 45.255 | 5.591
| 14 | 64.0 | 3.953
| 15 | 90.51 | 2.795

Note: table has been extracted from WagoAppDALI library documentation.

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                   | Description                                | MQTT payload | QoS                                  | Retain flag | Published on startup |
| :---------------------- | :----------------------------------------- | :----------- | :----------------------------------- | :---------- | :------------------- |
| **Light intensity value changes**   | Light intensity value changes | `0-100` | 2                                    | `TRUE`      | yes                   |
| **Light intensity value changes to 0 or 100** | Light intensity value changes to minimum or maximum value, published on `BRIGHTNESS` subtopic. | `ON/OFF`      | 2 | `TRUE`      | yes, if light intensity value > 0                   |

(\*): MQTT publish topic is a concatenation of the publish prefix variable, the function block name and the name of the output.

### **MQTT subscribe behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command                     | Description                                          | expected payload | Additional notes                                                 |
| :-------------------------- | :--------------------------------------------------- | :--------------- | :--------------------------------------------------------------- |
| **Turn on** | Turns the dimmer on to maximum brightness   | `ON`           | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low. |
| **Turn off** | Turns the dimmer off                | `OFF`           | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low. |
| **Set brightness value**  | Request to set specific brightness value. value expected on  `BRIGHTNESS` subtopic.                   | `0-100`          | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low. |

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name.
Note that the function block also accepts float values for setting the dimmer output value, the float value will get rounded to the nearest integer value.

### **Code example**

- DALI global variable initiation:
```
VAR_GLOBAL
	M1_Light1: typBallast:=(bAddress:=0,xIsGroup:=FALSE,bPortDALI:=1);
END_VAR
```

- variables initiation:
```
MqttPubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/Out/Dimmers/';
MqttSubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/In/Dimmers/';
M1_DALIMASTER				    :FbDaliMaster;
FB_DALI_1_ADR0				  :FB_OUTPUT_DIMMER_DALI_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DALI_1_ADR0.InitMqtt(MQTTPublishPrefix:= ADR(MqttVariables.MqttPubDimmerPrefix),				
	MQTTSubscribePrefix:= ADR(MqttVariables.MqttSubDimmerPrefix),									
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue),						
	pMqttCallbackCollector := ADR(MqttVariables.collector_FB_DIMMER_MQTT)						
);
```

The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/Dimmers/FB_DALI_1_ADR0` (MQTTPubSwitchPrefix variable + function block name). The subscription topic will be `Devices/PLC/Lab/In/Dimmers/FB_DALI_1_ADR0` (MQTTSubSwitchPrefix variable + function block name).

- checking for events to switch the DALI output (cyclic):
```
// Run the master before anything else
M1_DALIMASTER(
	bPortDALI:=1,
	I_Port:=IoConfig_Globals.DALI_MULTI_MASTER_MODULE);
	
// Run individual DALI FB
FB_DALI_1_ADR0(
	BALLAST := DALIVariables.M1_Light1,
	TOGGLE := FB_DI_PB_002.SINGLE,
	P_LONG := FB_DI_PB_002.P_LONG,
	STATUS_LED => DO_002);
```

The above illustrates an integration with [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md).

- MQTT discovery:
```
FB_DALI_1_ADR0.InitMqttDiscovery(
    name := '001. Office strip cold',				(* The name shown in the Home Assistant front-end *)
    Device := ADR(PLC_Device),							(* The device shown in Home Assistant *)
);
```

### **Home Assistant YAML**
If [MQTT discovery](../AdditionalFunctionality/MQTT_Discovery.md) is not working for you, you can use the YAML code below in your [MQTT lights](https://www.home-assistant.io/components/light.mqtt/) config:

```YAML
mqtt:
  light:
  - name: "Kitchen"
    state_topic: "Devices/PLC/Lab/Out/Dimmers/FB_DALI_1_ADR0"
    command_topic: "Devices/PLC/Lab/In/Dimmers/FB_DALI_1_ADR0"
    brightness_command_topic: "Devices/PLC/Lab/In/Dimmers/FB_DALI_1_ADR0/BRIGHTNESS"
    brightness_state_topic: "Devices/PLC/Lab/Out/Dimmers/FB_DALI_1_ADR0/BRIGHTNESS"
    on_command_type: "brightness"
    payload_on: "ON"
    payload_off: "OFF"
    optimistic: false
    brightness_scale: 100
    qos: 2
    availability: "Devices/PLC/Lab/availability"
    payload_not_available: "offline"
    payload_available: "online"
```
