## FB_OUTPUT_DIMMER_DALI_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Can be controlled using pulses from [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md), maintains output state through power cycles. Sets the driver fade time and fade rate setting. Allows dimming via a long persistent push on a pushbutton. Performs periodic writes to the DALI address to avoid state issues. 

DALI configuration via the Wago DALI tool and creation of the `typBallast` is explained pretty well in [this video](https://www.youtube.com/watch?v=FaoOY2-VFVk).

----------------------------

:rotating_light: **Needs the `WagoAppDALI` library, which is not vendored in this
repository.** WAGO's software licence forbids redistributing it, so it has to be
installed once per engineering PC from WAGO's own package — see
[Installing the WAGO libraries](../WagoPfcPrep.md#installing-the-wago-libraries-dali).
Without it the project does not build at all.

----------------------------

:rotating_light: **Untested on hardware.** Everything here is compile-verified
only. No ballast has been addressed, no group configured and no fade timing
measured on a real `753-647` — so treat the runtime behaviour as unproven, and
please report back if you get it running. What *is* checked, on every build, is
that the whole chain compiles: see the verification device below.

----------------------------

:warning: **Only a G2 WAGO device can drive the DALI module under the CODESYS
runtime.** Not a licensing detail and not a firmware version to work around — it
follows from where the port instance comes from:

| | G1 (750-8202, *CODESYS Control for PFC200 SL*) | G2 (750-821x, e!RUNTIME FW30+) |
|:--|:--|:--|
| `753-647` can be put on the bus | yes, it is in the SL K-bus catalogue | yes, from WAGO's device description |
| What the bus node gives you | 24 raw input + 24 raw output bytes, no driver function block | a `FbModule_753_647` instance |
| `FbDaliMaster.I_Port` can be bound | **no** — nothing implements `WagoTypesModule_753_647.I_Port_753_647` | yes |
| Result | ballast blocks compile, nothing reaches the DALI line | works |

`I_Port` wants a `WagoTypesModule_753_647.I_Port_753_647`, and only WAGO's own
device description creates one — which needs e!RUNTIME firmware, so a G2 device.
The interface is a stateful mailbox abstraction (level cache, sensor events,
command tokens, sequence IDs), not a byte port, so implementing it over the SL
runtime's 24 raw bytes would mean re-implementing WAGO's module protocol. That
was considered and rejected.

That is why the project carries a **second controller**, `Wago_PFC200_G2_Virtual`: a
750-8212 with a `753-647` on its K-bus, which is never downloaded and exists only
so `PRG_DALI_VERIFY` can instantiate the master, bind `I_Port` to the real module
and have the compiler check the whole chain on every build. A project can hold
several devices, and an application that is never downloaded is still compiled —
which is what keeps this block from drifting when `FB_MQTT_BASE` or the discovery
structs change. `tools/ai/scaffold/g2-dali-verify.json` is how that application
was built and how to rebuild it.

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
                         ┌────────────────────────────┐
                         │ FB_OUTPUT_DIMMER_DALI_MQTT │
                         ├────────────────────────────┤
WagoAppDALI.typBallast ──┤ BALLAST         STATUS_LED ├── BOOL
                  BOOL ──┤ TOGGLE                     │
                  BOOL ──┤ P_LONG                     │
                  BOOL ──┤ PRIO_HIGH                  │
                  BOOL ──┤ PRIO_LOW                   │
                         └────────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Default | Description |
|:--|:--|:--|:--|
| `BALLAST` | WagoAppDALI.typBallast |  | The `typBallast` this function block drives. |
| `TOGGLE` | BOOL |  | Connect to one or more `SINGLE` outputs of [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `P_LONG` | BOOL |  | Connect to one or more `P_LONG` outputs of [FB_INPUT_PUSHBUTTON_MQTT](./FB_INPUT_PUSHBUTTON_MQTT.md). |
| `PRIO_HIGH` | BOOL | `FALSE` | When high the light is set to maximum brightness, overriding the other inputs. |
| `PRIO_LOW` | BOOL | `FALSE` | When high the light is switched off, overriding the other inputs. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `STATUS_LED` | BOOL | High when the light intensity is greater than 0, low otherwise. |

### **Methods**

**`ConfigureFunctionBlock`** — Overrides the default behaviour characteristics. Only needed when the defaults do not suit.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `FadeTime` | BYTE |  | Driver fade time, see the table below. |
| `FadeRate` | BYTE |  | Driver fade rate, see the table below. |

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

**`PublishReceived`** — Callback invoked by the callback collector when a message arrives on the subscribed topic. Not called directly.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

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
	M1_Light1: WagoAppDALI.typBallast:=(bAddress:=0,xIsGroup:=FALSE,bPortDALI:=1);
END_VAR
```

- variables initiation:
```
MqttPubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/Out/Dimmers/';
MqttSubDimmerPrefix			:STRING(100) := 'Devices/PLC/Lab/In/Dimmers/';
M1_DALIMASTER				    :WagoAppDALI.FbDaliMaster;
FB_DALI_1_ADR0				  :FB_OUTPUT_DIMMER_DALI_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DALI_1_ADR0.InitMqtt(MQTTPublishPrefix:= ADR(GVL_MQTT.MqttPubDimmerPrefix),				
	MQTTSubscribePrefix:= ADR(GVL_MQTT.MqttSubDimmerPrefix),									
	pMqttPublishQueue := ADR(GVL_MQTT.fbMqttPublishQueue),						
	pMqttCallbackCollector := ADR(GVL_MQTT.collector_FB_DIMMER_MQTT)						
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
	BALLAST := GVL_DALI.M1_Light1,
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
