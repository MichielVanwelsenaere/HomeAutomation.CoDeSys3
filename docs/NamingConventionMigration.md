# Migrating to the naming convention

Every object and every private variable in this project was renamed in one pass,
for [the coding style](CodingStyle.md) adopted in
[issue #179](https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/issues/179).
This page is the old-name-to-new-name list an installation owner works from.

## What this breaks, and what it does not

| | |
|:--|:--|
| Your call sites | **unchanged.** Function block pins and method parameters keep their names, so `fbDoBin001(TOGGLE := ..., Q => ...)` and `InitMqtt(MQTTPublishPrefix := ...)` still compile. |
| Your Home Assistant entities | **unchanged by the renames themselves.** Every MQTT subtopic is a string literal in the source, never derived from a variable name. |
| Types you name in a declaration | **renamed.** `MqttVariables` is `GVL_MQTT`, `RS485Device` is `I_RS485_DEVICE`, and so on - see the table below. |
| Your GVL | **has to follow.** Shared blocks declare `STRING(GVL_MQTT.MQTT_TOPIC_LEN)` and reach into `GVL_MQTT.fbMqttPublishQueue`, so an installation whose list is still called `MqttVariables` fails with `Identifier 'GVL_MQTT' not defined`. Rename it in the same window as the sync. |
| Retained state | **resets once.** Persistent variables are keyed by instance path, and both halves of that path moved. Setpoints, cover positions and dimmer levels come back at their defaults on the first download after the upgrade. |
| Entity ids, if you rename your instances too | **change.** The id is the device name plus the *instance* name, so `FB_DO_BIN_001` becoming `fbDoBin001` turns `plc_fb_do_bin_001` into `plc_fbdobin001`, and the retained discovery config under the old id keeps a stale entity alive until it is cleared from the broker. |

The reference project did rename its own instances, because the convention applies
to them: they are variables. Yours are your own - the sync never touches a program -
so that last row is a choice you make, not one that is made for you.

## How to do it

The harness can do the renaming, including in your project:

```powershell
./tools/ai/codesys.ps1 rename -Map <map.json> -Project <yours.project> -DryRun
./tools/ai/codesys.ps1 rename -Map <map.json> -Project <yours.project> -Force
```

It renames the object *and* rewrites every reference, which CODESYS's own
refactoring does not expose to scripting. `-DryRun` reports what it would touch
and writes nothing; a real run refuses to save unless the project still builds.
The maps used here are committed as `tools/ai/rename/179-objects.json` and
`tools/ai/rename/179-internals.json` - start from those.

Clearing the stale discovery configs, if you renamed instances:

```powershell
# see what is out there first
./tools/ai/Mqtt-Snapshot.ps1
# then, per orphaned id
mosquitto_pub -h <broker> -t 'homeassistant/light/plc_fb_do_bin_001/config' -r -n
```

## Objects

### Structure

| Old | New |
|:--|:--|
| `MQTT_MESSAGE` | `ST_MQTT_MESSAGE` |
| `RS485_CommissionRequest` | `ST_RS485_COMMISSION_REQUEST` |
| `RS485_Step` | `ST_RS485_STEP` |

### Enumeration

| Old | New |
|:--|:--|
| `DIMMER_CURVE` | `E_DIMMER_CURVE` |
| `Dimmer` | `E_DIMMER` |
| `HvacModes` | `E_HVAC_MODE` |
| `RS485_EASTRON_SDM_Devices` | `E_RS485_EASTRON_SDM_DEVICE` |
| `RS485_StepState` | `E_RS485_STEP_STATE` |
| `RS485_WorkLevel` | `E_RS485_WORK_LEVEL` |

### Array alias

| Old | New |
|:--|:--|
| `RS485_ReadBuffer` | `A_RS485_READ_BUFFER` |
| `RS485_StepList` | `A_RS485_STEP_LIST` |

### Interface

| Old | New |
|:--|:--|
| `RS485Device` | `I_RS485_DEVICE` |
| `RS485Transport` | `I_RS485_TRANSPORT` |

### Function

| Old | New |
|:--|:--|
| `FC_StripJsonRoot` | `F_STRIP_JSON_ROOT` |
| `SwapWordsToReal` | `F_SWAP_WORDS_TO_REAL` |

### Function block

| Old | New |
|:--|:--|
| `FB_MqttPublishQueue` | `FB_MQTT_PUBLISH_QUEUE` |
| `FB_MqttPublishWorker` | `FB_MQTT_PUBLISH_WORKER` |

### Global variable list

| Old | New |
|:--|:--|
| `DALIVariables` | `GVL_DALI` |
| `DMXVariables` | `GVL_DMX` |
| `MqttVariables` | `GVL_MQTT` |
| `PersistentVars` | `GVL_PERSISTENT` |
| `RS485Variables` | `GVL_RS485` |

### Program

| Old | New |
|:--|:--|
| `DMX_SEND` | `PRG_DMX_SEND` |
| `PLC_PRG_HVAC` | `PRG_HVAC` |
| `PLC_PRG_MAIN` | `PRG_MAIN` |
| `PLC_PRG_MQTT` | `PRG_MQTT` |
| `PLC_PRG_RS485` | `PRG_RS485` |

## Private variables

These are internal to their function block or program. You only need them if you
read or wrote one from your own code - which, being private, you should not have
been able to do - or if your test tooling addresses variables by path.

<details><summary><code>FB_1WIRE_MQTT_DISCOVERY_DEVICE</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `InstanceName` | `sInstanceName` |
| `mac` | `sMac` |
| `MqttDiscMsgBinSens` | `stMqttDiscMsgBinSens` |
| `MqttDiscMsgBinSensWCat` | `stMqttDiscMsgBinSensWCat` |
| `MqttDiscMsgClimate` | `stMqttDiscMsgClimate` |
| `MqttDiscMsgCover` | `stMqttDiscMsgCover` |
| `MqttDiscMsgCoverPos` | `stMqttDiscMsgCoverPos` |
| `MqttDiscMsgEvent` | `stMqttDiscMsgEvent` |
| `MqttDiscMsgFan` | `stMqttDiscMsgFan` |
| `MqttDiscMsgLight` | `stMqttDiscMsgLight` |
| `MqttDiscMsgLightDim` | `stMqttDiscMsgLightDim` |
| `MqttDiscMsgLock` | `stMqttDiscMsgLock` |
| `MqttDiscMsgSensor` | `stMqttDiscMsgSensor` |
| `MqttDiscMsgSensorDiagnostic` | `stMqttDiscMsgSensorDiagnostic` |
| `MqttDiscMsgSiren` | `stMqttDiscMsgSiren` |
| `MqttDiscMsgSwitch` | `stMqttDiscMsgSwitch` |
| `MqttDiscMsgValve` | `stMqttDiscMsgValve` |
| `MqttDiscMsgValveState` | `stMqttDiscMsgValveState` |
| `xInit` | `bInit` |

</details>

<details><summary><code>FB_BASE_MQTT_DISCOVERY_DEVICE</code> — 23 name(s)</summary>

| Old | New |
|:--|:--|
| `ComposeJSON` | `fbComposeJSON` |
| `FoundUpdate` | `bFoundUpdate` |
| `InstanceName` | `sInstanceName` |
| `mac` | `sMac` |
| `MqttDiscMsgBinSens` | `stMqttDiscMsgBinSens` |
| `MqttDiscMsgBinSensWCat` | `stMqttDiscMsgBinSensWCat` |
| `MqttDiscMsgClimate` | `stMqttDiscMsgClimate` |
| `MqttDiscMsgCover` | `stMqttDiscMsgCover` |
| `MqttDiscMsgCoverPos` | `stMqttDiscMsgCoverPos` |
| `MqttDiscMsgEvent` | `stMqttDiscMsgEvent` |
| `MqttDiscMsgFan` | `stMqttDiscMsgFan` |
| `MqttDiscMsgLight` | `stMqttDiscMsgLight` |
| `MqttDiscMsgLightDim` | `stMqttDiscMsgLightDim` |
| `MqttDiscMsgLock` | `stMqttDiscMsgLock` |
| `MqttDiscMsgSensor` | `stMqttDiscMsgSensor` |
| `MqttDiscMsgSensorDiagnostic` | `stMqttDiscMsgSensorDiagnostic` |
| `MqttDiscMsgSiren` | `stMqttDiscMsgSiren` |
| `MqttDiscMsgSwitch` | `stMqttDiscMsgSwitch` |
| `MqttDiscMsgValve` | `stMqttDiscMsgValve` |
| `MqttDiscMsgValveState` | `stMqttDiscMsgValveState` |
| `MqttJSON` | `sMqttJSON` |
| `MqttTopic` | `sMqttTopic` |
| `xInit` | `bInit` |

</details>

<details><summary><code>FB_DFROBOT_MQTT_DISCOVERY_DEVICE</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `InstanceName` | `sInstanceName` |
| `mac` | `sMac` |
| `MqttDiscMsgBinSens` | `stMqttDiscMsgBinSens` |
| `MqttDiscMsgBinSensWCat` | `stMqttDiscMsgBinSensWCat` |
| `MqttDiscMsgClimate` | `stMqttDiscMsgClimate` |
| `MqttDiscMsgCover` | `stMqttDiscMsgCover` |
| `MqttDiscMsgCoverPos` | `stMqttDiscMsgCoverPos` |
| `MqttDiscMsgEvent` | `stMqttDiscMsgEvent` |
| `MqttDiscMsgFan` | `stMqttDiscMsgFan` |
| `MqttDiscMsgLight` | `stMqttDiscMsgLight` |
| `MqttDiscMsgLightDim` | `stMqttDiscMsgLightDim` |
| `MqttDiscMsgLock` | `stMqttDiscMsgLock` |
| `MqttDiscMsgSensor` | `stMqttDiscMsgSensor` |
| `MqttDiscMsgSensorDiagnostic` | `stMqttDiscMsgSensorDiagnostic` |
| `MqttDiscMsgSiren` | `stMqttDiscMsgSiren` |
| `MqttDiscMsgSwitch` | `stMqttDiscMsgSwitch` |
| `MqttDiscMsgValve` | `stMqttDiscMsgValve` |
| `MqttDiscMsgValveState` | `stMqttDiscMsgValveState` |
| `xInit` | `bInit` |

</details>

<details><summary><code>FB_EASTRON_SDM_MQTT_DISCOVERY_DEVICE</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `InstanceName` | `sInstanceName` |
| `mac` | `sMac` |
| `MqttDiscMsgBinSens` | `stMqttDiscMsgBinSens` |
| `MqttDiscMsgBinSensWCat` | `stMqttDiscMsgBinSensWCat` |
| `MqttDiscMsgClimate` | `stMqttDiscMsgClimate` |
| `MqttDiscMsgCover` | `stMqttDiscMsgCover` |
| `MqttDiscMsgCoverPos` | `stMqttDiscMsgCoverPos` |
| `MqttDiscMsgEvent` | `stMqttDiscMsgEvent` |
| `MqttDiscMsgFan` | `stMqttDiscMsgFan` |
| `MqttDiscMsgLight` | `stMqttDiscMsgLight` |
| `MqttDiscMsgLightDim` | `stMqttDiscMsgLightDim` |
| `MqttDiscMsgLock` | `stMqttDiscMsgLock` |
| `MqttDiscMsgSensor` | `stMqttDiscMsgSensor` |
| `MqttDiscMsgSensorDiagnostic` | `stMqttDiscMsgSensorDiagnostic` |
| `MqttDiscMsgSiren` | `stMqttDiscMsgSiren` |
| `MqttDiscMsgSwitch` | `stMqttDiscMsgSwitch` |
| `MqttDiscMsgValve` | `stMqttDiscMsgValve` |
| `MqttDiscMsgValveState` | `stMqttDiscMsgValveState` |
| `xInit` | `bInit` |

</details>

<details><summary><code>FB_HVAC_BURNER_MQTT</code> — 17 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `FB_ACTUATOR` | `fbActuator` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PreviousState` | `bPreviousState` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_HVAC_COLLECTOR_MQTT</code> — 22 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `F_Trig_Valve` | `afbFTrigValve` |
| `HeatRequest` | `bHeatRequest` |
| `i` | `iI` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PumpDelay` | `fbPumpDelay` |
| `R_Trig_Valve` | `afbRTrigValve` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |
| `VALVE_COUNT` | `ciValveCount` |
| `VALVE_NAMES` | `casValveNames` |

</details>

<details><summary><code>FB_HVAC_PUMP_MQTT</code> — 18 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `FB_ACTUATOR` | `fbActuator` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MIN_ONTIME_TIMER` | `fbMinOntimeTimer` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PreviousState` | `bPreviousState` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_HVAC_THERMOSTAT_MQTT</code> — 22 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `DESIRED_TEMP` | `rDesiredTemp` |
| `HvacMode` | `eHvacMode` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PreviousFault` | `bPreviousFault` |
| `PreviousHum` | `rPreviousHum` |
| `PreviousState` | `bPreviousState` |
| `PreviousTemp` | `rPreviousTemp` |
| `SensorFault` | `bSensorFault` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_INPUT_BINARYSENSOR_MQTT</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `FB_DEBOUNCE` | `fbDebounce` |
| `FB_F_TRIG` | `fbFTrig` |
| `FB_R_TRIG` | `fbRTrig` |
| `FB_TurnOffDelayTimer` | `fbTurnOffDelayTimer` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_INPUT_PUSHBUTTON_DIMMER_MQTT</code> — 21 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `FB_DETECTPUSH` | `fbDetectpush` |
| `FB_DIMMER` | `fbDimmer` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `P_LONG_F_TRIG` | `fbPLongFTrig` |
| `P_LONG_R_TRIG` | `fbPLongRTrig` |
| `PreviousDBL` | `bPreviousDBL` |
| `PreviousDim` | `byPreviousDim` |
| `PreviousQ` | `bPreviousQ` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_INPUT_PUSHBUTTON_MQTT</code> — 17 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `FB_DETECTPUSH` | `fbDetectpush` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `P_LONG_F_TRIG` | `fbPLongFTrig` |
| `P_LONG_R_TRIG` | `fbPLongRTrig` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_MQTT_BASE</code> — 13 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_MQTT_LOG</code> — 14 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_MQTT_PUBLISH_QUEUE</code> — 4 name(s)</summary>

| Old | New |
|:--|:--|
| `fifo` | `astFifo` |
| `n` | `ciN` |
| `pr` | `iPr` |
| `pw` | `iPw` |

</details>

<details><summary><code>FB_MQTT_PUBLISH_WORKER</code> — 5 name(s)</summary>

| Old | New |
|:--|:--|
| `InitDone` | `bInitDone` |
| `LocalMqttMessage` | `stLocalMqttMessage` |
| `publish` | `fbPublish` |
| `RequestToSend` | `bRequestToSend` |
| `SendTimeout` | `fbSendTimeout` |

</details>

<details><summary><code>FB_OUTPUT_BINARY_MQTT</code> — 16 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PreviousState` | `bPreviousState` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_OUTPUT_BISTABLE_MQTT</code> — 18 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `HoldTimer` | `fbHoldTimer` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PreviousFeedback` | `bPreviousFeedback` |
| `PulseTrigger` | `bPulseTrigger` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_OUTPUT_COVER_MQTT</code> — 27 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `Cover_State_Timer` | `fbCoverStateTimer` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `internalDir` | `bInternalDir` |
| `internalDown` | `bInternalDown` |
| `internalUp` | `bInternalUp` |
| `lock` | `fbLock` |
| `MD_FTrigger` | `fbMdFTrigger` |
| `MD_RTrigger` | `fbMdRTrigger` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MqttRequestClose` | `bMqttRequestClose` |
| `MqttRequestOpen` | `bMqttRequestOpen` |
| `MqttRequestStop` | `bMqttRequestStop` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `MU_FTrigger` | `fbMuFTrigger` |
| `MU_RTrigger` | `fbMuRTrigger` |
| `Startup` | `bStartup` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_OUTPUT_COVER_POSITION_MQTT</code> — 46 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `Arrived` | `bArrived` |
| `AtEnd` | `bAtEnd` |
| `ComposeJSON` | `fbComposeJSON` |
| `Diff` | `iDiff` |
| `DRIVE_DOWN` | `ciDriveDown` |
| `DRIVE_STOP` | `ciDriveStop` |
| `DRIVE_UP` | `ciDriveUp` |
| `Driving` | `iDriving` |
| `DrivingLast` | `iDrivingLast` |
| `dtMs` | `udiDtMs` |
| `EndStop` | `fbEndStop` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `Lockout` | `fbLockout` |
| `ManualDrive` | `iManualDrive` |
| `MAX_TICK_MS` | `cudiMaxTickMs` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MqttRequestClose` | `bMqttRequestClose` |
| `MqttRequestOpen` | `bMqttRequestOpen` |
| `MqttRequestPosition` | `bMqttRequestPosition` |
| `MqttRequestPositionPct` | `byMqttRequestPositionPct` |
| `MqttRequestStop` | `bMqttRequestStop` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `PositionPublished` | `bPositionPublished` |
| `PositionReal` | `rPositionReal` |
| `PublishedPosition` | `byPublishedPosition` |
| `PublishedState` | `sPublishedState` |
| `Referencing` | `bReferencing` |
| `RefRun` | `fbRefRun` |
| `RefTime` | `tRefTime` |
| `Reported` | `byReported` |
| `Startup` | `bStartup` |
| `State` | `sState` |
| `Step` | `rStep` |
| `Target` | `rTarget` |
| `TopicTruncated` | `bTopicTruncated` |
| `TravelMs` | `udiTravelMs` |
| `tValid` | `bValid` |

</details>

<details><summary><code>FB_OUTPUT_DIMMER_DALI_MQTT</code> — 26 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `DaliConfigSyncSignalGenerator` | `fbDaliConfigSyncSignalGenerator` |
| `DaliSendDimValue` | `fbDaliSendDimValue` |
| `DaliSendFadeRate` | `fbDaliSendFadeRate` |
| `DaliSendFadeTime` | `fbDaliSendFadeTime` |
| `DaliSyncSignalGenerator` | `fbDaliSyncSignalGenerator` |
| `DimDirection` | `iDimDirection` |
| `DimValue` | `rDimValue` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MqttSendBrightnessUpdate` | `bMqttSendBrightnessUpdate` |
| `MqttSendOffUpdate` | `bMqttSendOffUpdate` |
| `MqttSendOnUpdate` | `bMqttSendOnUpdate` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `Startup` | `bStartup` |
| `Toggle_RTrigger` | `fbToggleRTrigger` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_OUTPUT_DIMMER_DMX_MQTT</code> — 20 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `InitDmxDone` | `bInitDmxDone` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `OUT_Internal` | `byOutInternal` |
| `PreviousOUT` | `byPreviousOUT` |
| `PreviousQ` | `bPreviousQ` |
| `Startup` | `bStartup` |
| `t3` | `fbT3` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_OUTPUT_DIMMER_MQTT</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `OUT_Internal` | `byOutInternal` |
| `PreviousOUT` | `byPreviousOUT` |
| `PreviousQ` | `bPreviousQ` |
| `Startup` | `bStartup` |
| `t3` | `fbT3` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_PLC_MQTT_DISCOVERY_DEVICE</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `InstanceName` | `sInstanceName` |
| `mac` | `sMac` |
| `MqttDiscMsgBinSens` | `stMqttDiscMsgBinSens` |
| `MqttDiscMsgBinSensWCat` | `stMqttDiscMsgBinSensWCat` |
| `MqttDiscMsgClimate` | `stMqttDiscMsgClimate` |
| `MqttDiscMsgCover` | `stMqttDiscMsgCover` |
| `MqttDiscMsgCoverPos` | `stMqttDiscMsgCoverPos` |
| `MqttDiscMsgEvent` | `stMqttDiscMsgEvent` |
| `MqttDiscMsgFan` | `stMqttDiscMsgFan` |
| `MqttDiscMsgLight` | `stMqttDiscMsgLight` |
| `MqttDiscMsgLightDim` | `stMqttDiscMsgLightDim` |
| `MqttDiscMsgLock` | `stMqttDiscMsgLock` |
| `MqttDiscMsgSensor` | `stMqttDiscMsgSensor` |
| `MqttDiscMsgSensorDiagnostic` | `stMqttDiscMsgSensorDiagnostic` |
| `MqttDiscMsgSiren` | `stMqttDiscMsgSiren` |
| `MqttDiscMsgSwitch` | `stMqttDiscMsgSwitch` |
| `MqttDiscMsgValve` | `stMqttDiscMsgValve` |
| `MqttDiscMsgValveState` | `stMqttDiscMsgValveState` |
| `xInit` | `bInit` |

</details>

<details><summary><code>FB_RS485_BUSCONTROLLER</code> — 16 name(s)</summary>

| Old | New |
|:--|:--|
| `chosen` | `iChosen` |
| `devices` | `aitfDevices` |
| `devicesCount` | `iDevicesCount` |
| `i` | `iI` |
| `Initialised` | `bInitialised` |
| `k` | `iK` |
| `restartSilence` | `bRestartSilence` |
| `restartWatchdog` | `bRestartWatchdog` |
| `silence` | `fbSilence` |
| `silenceRun` | `bSilenceRun` |
| `startupTimer` | `fbStartupTimer` |
| `State` | `iState` |
| `StepCount` | `iStepCount` |
| `Steps` | `eSteps` |
| `stepState` | `eStepState` |
| `watchdog` | `fbWatchdog` |

</details>

<details><summary><code>FB_RS485_COMMISSIONER</code> — 18 name(s)</summary>

| Old | New |
|:--|:--|
| `BaudIdx` | `iBaudIdx` |
| `Delay` | `fbDelay` |
| `DeviceIdx` | `iDeviceIdx` |
| `DeviceProbes` | `udiDeviceProbes` |
| `DeviceWritten` | `bDeviceWritten` |
| `FoundBaud` | `udiFoundBaud` |
| `FoundStop` | `byFoundStop` |
| `Initialised` | `bInitialised` |
| `MaxRx` | `udiMaxRx` |
| `MaxRxBaud` | `udiMaxRxBaud` |
| `MaxRxStop` | `byMaxRxStop` |
| `Outcome` | `eOutcome` |
| `pTopicPrefix` | `psTopicPrefix` |
| `Report` | `sReport` |
| `Request` | `stRequest` |
| `State` | `iState` |
| `Step` | `stStep` |
| `StopIdx` | `iStopIdx` |

</details>

<details><summary><code>FB_RS485_DFROBOT_SEN0492_MQTT</code> — 37 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `AvailFailures` | `iAvailFailures` |
| `AvailKnown` | `bAvailKnown` |
| `AvailOnline` | `bAvailOnline` |
| `BAUD_RATES` | `caudiBaudRates` |
| `code` | `iCode` |
| `ComposeJSON` | `fbComposeJSON` |
| `ConfigPending` | `bConfigPending` |
| `ConfigStep` | `stConfigStep` |
| `FACTORY_BAUD` | `cudiFactoryBaud` |
| `i` | `iI` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `isDataUpdated` | `bIsDataUpdated` |
| `isQualityUpdated` | `bIsQualityUpdated` |
| `isStateUpdated` | `bIsStateUpdated` |
| `MqttDiscoveryDevice` | `fbMqttDiscoveryDevice` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `n` | `iN` |
| `qualityI` | `iQualityI` |
| `QualityIdx` | `iQualityIdx` |
| `qualityOk` | `iQualityOk` |
| `QualitySeen` | `iQualitySeen` |
| `QualityWindow` | `abQualityWindow` |
| `REG_BAUDRATE` | `cuiRegBaudrate` |
| `SEN0492_MIN_POLL` | `ctSen0492MinPoll` |
| `Step` | `stStep` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_RS485_DUCO_DUCOBOX_MQTT</code> — 36 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `i` | `iI` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InitRS485Done` | `bInitRS485Done` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `isDataUpdated` | `bIsDataUpdated` |
| `k` | `iK` |
| `loopCounter` | `iLoopCounter` |
| `MasterStep` | `stMasterStep` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `n` | `iN` |
| `NodeCursor` | `iNodeCursor` |
| `NodePointer` | `uiNodePointer` |
| `NodeRegister` | `sNodeRegister` |
| `Nodes` | `afbNodes` |
| `ReadBackStep` | `stReadBackStep` |
| `Startup` | `bStartup` |
| `stepKind` | `iStepKind` |
| `StepMap` | `aiStepMap` |
| `SubTopic` | `sSubTopic` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |
| `writePos` | `iWritePos` |
| `WriteQueryPayload` | `sWriteQueryPayload` |
| `WriteQueryReady` | `bWriteQueryReady` |
| `WriteQuerySuffix` | `sWriteQuerySuffix` |
| `WriteStep` | `stWriteStep` |

</details>

<details><summary><code>FB_RS485_DUCO_DUCOBOX_NODE_MQTT</code> — 5 name(s)</summary>

| Old | New |
|:--|:--|
| `InitMqttDone` | `bInitMqttDone` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `NodeInitialized` | `bNodeInitialized` |
| `Step` | `stStep` |
| `timerData` | `fbTimerData` |

</details>

<details><summary><code>FB_RS485_EASTRON_SDM220_MQTT</code> — 22 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttDiscoveryDevice` | `fbMqttDiscoveryDevice` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `Startup` | `bStartup` |
| `StepMap` | `aiStepMap` |
| `Steps` | `astSteps` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |
| `Update1` | `bUpdate1` |
| `Update2` | `bUpdate2` |
| `Update3` | `bUpdate3` |

</details>

<details><summary><code>FB_RS485_EASTRON_SDM630_MQTT</code> — 19 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `isDataUpdated` | `bIsDataUpdated` |
| `MqttDiscoveryDevice` | `fbMqttDiscoveryDevice` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `n` | `iN` |
| `Step` | `stStep` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_RS485_EASTRON_SDM_POWER_MQTT</code> — 22 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `ComposeJSON` | `fbComposeJSON` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `isDataUpdated` | `bIsDataUpdated` |
| `MqttDiscoveryDevice` | `fbMqttDiscoveryDevice` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `n` | `iN` |
| `resolvedModel` | `sResolvedModel` |
| `Startup` | `bStartup` |
| `StepSDM630` | `stStepSDM630` |
| `StepSmallMeter` | `stStepSmallMeter` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_RS485_ESERA_OWD_MQTT</code> — 20 name(s)</summary>

| Old | New |
|:--|:--|
| `_InstancePath` | `_sInstancePath` |
| `AllowedErrorCount` | `uiAllowedErrorCount` |
| `ComposeJSON` | `fbComposeJSON` |
| `CurrentErrorCount` | `uiCurrentErrorCount` |
| `initMqttDiscoveryDone` | `bInitMqttDiscoveryDone` |
| `InitMqttDone` | `bInitMqttDone` |
| `InstanceNamePt` | `psInstanceNamePt` |
| `InstancePath` | `sInstancePath` |
| `MqttDiscoveryDevice` | `pMqttDiscoveryDevice` |
| `MqttHighRequest` | `bMqttHighRequest` |
| `MqttLowRequest` | `bMqttLowRequest` |
| `MQTTPublishTopic` | `sMQTTPublishTopic` |
| `MqttPublishTopicPrefix` | `psMqttPublishTopicPrefix` |
| `MQTTSubscribeTopic` | `sMQTTSubscribeTopic` |
| `MqttSubscribeTopicPrefix` | `psMqttSubscribeTopicPrefix` |
| `MqttSubscribeTopicSuffix` | `sMqttSubscribeTopicSuffix` |
| `n` | `iN` |
| `Step` | `stStep` |
| `timerData` | `fbTimerData` |
| `TopicTruncated` | `bTopicTruncated` |

</details>

<details><summary><code>FB_RS485_TRANSPORT_RTU</code> — 38 name(s)</summary>

| Old | New |
|:--|:--|
| `acc` | `wAcc` |
| `b` | `iB` |
| `bytecount` | `iBytecount` |
| `Configured` | `bConfigured` |
| `ConfiguredGapTime` | `tConfiguredGapTime` |
| `ConfiguredReplyTimeout` | `tConfiguredReplyTimeout` |
| `ConfiguredSettings` | `stConfiguredSettings` |
| `crc` | `wCrc` |
| `echoAddr` | `uiEchoAddr` |
| `echoValue` | `uiEchoValue` |
| `first` | `iFirst` |
| `Flush` | `abyFlush` |
| `frameLen` | `iFrameLen` |
| `gap` | `fbGap` |
| `gotFrame` | `bGotFrame` |
| `i` | `iI` |
| `k` | `iK` |
| `last` | `iLast` |
| `n` | `udiN` |
| `Outcome` | `eOutcome` |
| `p` | `pbyP` |
| `pRx` | `pbyRx` |
| `qty` | `iQty` |
| `RegCount` | `iRegCount` |
| `ReopenRequest` | `bReopenRequest` |
| `replyTimer` | `fbReplyTimer` |
| `restartGap` | `bRestartGap` |
| `restartReply` | `bRestartReply` |
| `rtsResult` | `eRtsResult` |
| `Rx` | `abyRx` |
| `RxCount` | `udiRxCount` |
| `Settings` | `stSettings` |
| `State` | `iState` |
| `Step` | `stStep` |
| `tries` | `iTries` |
| `Tx` | `abyTx` |
| `TxLen` | `iTxLen` |
| `valid` | `bDataValid` |

</details>

<details><summary><code>F_STRIP_JSON_ROOT</code> — 4 name(s)</summary>

| Old | New |
|:--|:--|
| `i` | `diI` |
| `iContentLen` | `diContentLen` |
| `iEnd` | `diEnd` |
| `iStart` | `diStart` |

</details>

<details><summary><code>F_SWAP_WORDS_TO_REAL</code> — 1 name(s)</summary>

| Old | New |
|:--|:--|
| `pt_REAL` | `prReal` |

</details>

<details><summary><code>PRG_DALI_VERIFY</code> — 1 name(s)</summary>

| Old | New |
|:--|:--|
| `DaliMaster` | `fbDaliMaster` |

</details>

<details><summary><code>PRG_DMX_SEND</code> — 7 name(s)</summary>

| Old | New |
|:--|:--|
| `error_send` | `bErrorSend` |
| `ErrorTrig` | `fbErrorTrig` |
| `i` | `iI` |
| `R_BUF1` | `stRBuf1` |
| `S_BUF1` | `stSBuf1` |
| `Step` | `iStep` |
| `Universe` | `iUniverse` |

</details>

<details><summary><code>PRG_HVAC</code> — 9 name(s)</summary>

| Old | New |
|:--|:--|
| `CollectorValveNames` | `asCollectorValveNames` |
| `FB_BURNER_GAS` | `fbBurnerGas` |
| `FB_PUMP_1` | `fbPump1` |
| `FB_PUMP_2` | `fbPump2` |
| `FB_PUMP_2_COLLECTOR` | `fbPump2Collector` |
| `FB_THERMOSTAT_1` | `fbThermostat1` |
| `FB_THERMOSTAT_2` | `fbThermostat2` |
| `FB_THERMOSTAT_3` | `fbThermostat3` |
| `InitHvacDone` | `bInitHvacDone` |

</details>

<details><summary><code>PRG_MAIN</code> — 8 name(s)</summary>

| Old | New |
|:--|:--|
| `FB_AO_DIMMER_001` | `fbAoDimmer001` |
| `FB_DI_PB_001` | `fbDiPb001` |
| `FB_DI_PB_002` | `fbDiPb002` |
| `FB_DO_BIN_001` | `fbDoBin001` |
| `FB_DO_BISTABLE_001` | `fbDoBistable001` |
| `FB_DO_COVER_001` | `fbDoCover001` |
| `FB_DO_COVER_002` | `fbDoCover002` |
| `TestOUT` | `wTestOUT` |

</details>

<details><summary><code>PRG_MQTT</code> — 16 name(s)</summary>

| Old | New |
|:--|:--|
| `i` | `udiI` |
| `icounter` | `udiIcounter` |
| `ipublishers` | `udiIpublishers` |
| `MQTTBirthHartbeat` | `fbMQTTBirthHartbeat` |
| `MQTTBirthMessage` | `stMQTTBirthMessage` |
| `MQTTBirthPublisher` | `fbMQTTBirthPublisher` |
| `MQTTConnectTrigger` | `fbMQTTConnectTrigger` |
| `MQTTDisconnectTrigger` | `fbMQTTDisconnectTrigger` |
| `MQTTInfo` | `stMQTTInfo` |
| `MQTTPublishBirth` | `bMQTTPublishBirth` |
| `publishers` | `afbPublishers` |
| `subscriber_FB_DIMMER_MQTT` | `fbSubscriberFbDimmerMqtt` |
| `subscriber_FB_HVAC_MQTT` | `fbSubscriberFbHvacMqtt` |
| `subscriber_FB_OUTPUT_COVER_MQTT` | `fbSubscriberFbOutputCoverMqtt` |
| `subscriber_FB_OUTPUT_SWITCH_MQTT` | `fbSubscriberFbOutputSwitchMqtt` |
| `subscriber_FB_RS485_MQTT` | `fbSubscriberFbRs485Mqtt` |

</details>

<details><summary><code>PRG_PING_DMX</code> — 3 name(s)</summary>

| Old | New |
|:--|:--|
| `DMXnodeReachable` | `udiDMXnodeReachable` |
| `PingTime` | `udiPingTime` |
| `PreviousReachable` | `udiPreviousReachable` |

</details>

<details><summary><code>PRG_RS485</code> — 5 name(s)</summary>

| Old | New |
|:--|:--|
| `BUS_BAUDRATE` | `cudiBusBaudrate` |
| `DiagReport` | `sDiagReport` |
| `DiagTimer` | `fbDiagTimer` |
| `RS485BusController` | `fbRS485BusController` |
| `RS485Commissioner` | `fbRS485Commissioner` |

</details>
