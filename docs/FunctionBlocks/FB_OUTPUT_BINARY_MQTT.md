## FB_OUTPUT_BINARY_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**
Can be switched using pulses that are high for one clock cycle (for example from `FB_INPUT_PUSHBUTTON_MQTT`), and maintains output state through power cycles.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌───────────────────────┐
       │ FB_OUTPUT_BINARY_MQTT │
       ├───────────────────────┤
BOOL ──┤ PRIO_HIGH         OUT ├── BOOL
BOOL ──┤ PRIO_LOW              │
BOOL ──┤ TOGGLE                │
       └───────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `PRIO_HIGH` | BOOL | When high the output `OUT` is set to high, has priority over the `TOGGLE` and `PRIO_LOW` input. |
| `PRIO_LOW` | BOOL | When high the output `OUT` is set to low, has priority over the `TOGGLE` input. |
| `TOGGLE` | BOOL | When high the output `OUT` gets toggled. The input should only be high for one clock cycle. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `OUT` | BOOL | Output to switch digital output on and off. Can be connected to a relay for example. |

### **Methods**

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |

**`InitMqttDiscoveryAsFan`** — Publishes a Home Assistant MQTT discovery config for this block as a **fan** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`InitMqttDiscoveryAsLight`** — Publishes a Home Assistant MQTT discovery config for this block as a **light** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`InitMqttDiscoveryAsLock`** — Publishes a Home Assistant MQTT discovery config for this block as a **lock** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`InitMqttDiscoveryAsSiren`** — Publishes a Home Assistant MQTT discovery config for this block as a **siren** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`InitMqttDiscoveryAsSwitch`** — Publishes a Home Assistant MQTT discovery config for this block as a **switch** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `DeviceClass` | STRING(100) | `'outlet'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`InitMqttDiscoveryAsValve`** — Publishes a Home Assistant MQTT discovery config for this block as a **valve** entity. Call once at startup, after `InitMqtt`.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Device` | POINTER TO FB_PLC_MQTT_DISCOVERY_DEVICE |  | Pointer to the discovery device this entity belongs to, normally `MqttVariables.PLC_Device`. |
| `Name` | STRING(255) |  | Name shown in the Home Assistant front-end. |
| `DeviceClass` | STRING(100) | `'water'` | Home Assistant device class for the entity. Leave empty for the default. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |
| `Invert` | BOOL | `FALSE` | Set TRUE for a normally-closed (NC) contact. FALSE, the default, assumes normally-open (NO). |

**`PublishReceived`** — Callback method called by the callback collector when a message is received on the subscribed topic by the callback collector.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **Output changes: OUT**   | A change is detected on output `OUT`. | `TRUE/FALSE` | 2 | `TRUE` | yes

MQTT publish topic is a concatenation of the publish prefix and the function block name. 

### **MQTT subscribe behavior**
Requires method call `InitMQTT` to enable MQTT capabilities.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **Change output to high** | Request to change output to high. | `TRUE` | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low.
| **Change output to low** | Request to change output to low. | `FALSE` | Command executed when `PRIO_HIGH` and `PRIO_LOW` inputs are low.

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name. 

### **Code example**

- variables initiation:
```
MQTTPubSwitchPrefix     :STRING(100) := 'Devices/PLC/Lab/Out/DigitalOutputs/';
MQTTSubSwitchPrefix     :STRING(100) := 'Devices/PLC/Lab/In/DigitalOutputs/';
FB_DO_SW_001            :FB_OUTPUT_BINARY_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_DO_SW_001.InitMQTT(MQTTPublishPrefix:= ADR(MQTTPubSwitchPrefix),                 (* pointer to string prefix for the MQTT publish topic *)
    MQTTSubscribePrefix:= ADR(MQTTSubSwitchPrefix),                                 (* pointer to string prefix for the MQTT subscribe topic *)
    pMQTTPublishQueue := ADR(MQTTVariables.fbMQTTPublishQueue),                     (* pointer to MQTTPublishQueue to send a new MQTT event *)
    pMQTTCallbackCollector := ADR(MQTTVariables.collector_FB_OUTPUT_SWITCH_MQTT)    (* pointer to CallbackCollector to receive MQTT subscription events *)
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/DigitalOutputs/FB_DO_SW_001` (MQTTPubSwitchPrefix variable + function block name). The subscription topic will be `Devices/PLC/Lab/In/DigitalOutputs/FB_DO_SW_001` (MQTTSubSwitchPrefix variable + function block name).

- checking for events to switch the digital output (cyclic):
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIO_HIGH:=     FALSE,                  (* brings the output high regardless of other input values *)
    PRIO_LOW:=      FALSE                   (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_PB_009.SINGLE     (* for toggling the output *)	
);
```

- integration with `FB_INPUT_PUSHBUTTON_MQTT`:
```
FB_DO_SW_001(OUT=>  DO_001,                 (* couple the function block to the physical output *)
    PRIO_HIGH:=     FALSE,                  (* brings the output high regardless of other input values *)
    PRIO_LOW:=      FALSE,                  (* brings the output low regardless of other input values. NOTE: Priohigh overrules Priolow input *)
    TOGGLE:=        FB_DI_PB_001.SINGLE     (* for toggling the output *)	
);
```

- MQTT discovery (choose one):
```
(* switch entity *)
FB_DO_SW_001.InitMqttDiscoveryAsSwitch(
	Name := 'switch 001',			        (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);

(* light entity *)
FB_DO_SW_001.InitMqttDiscoveryAsLight(
	Name := 'light 001',			        (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);

(* siren entity *)
FB_DO_SW_001.InitMqttDiscoveryAsSiren(
	Name := 'siren 001',			        (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);

(* lock entity *)
FB_DO_SW_001.InitMqttDiscoveryAsLock(
	Name := 'lock 001',			            (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);

(* valve entity *)
FB_DO_SW_001.InitMqttDiscoveryAsValve(
	Name := 'valve 001',			        (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
);
```

By default a 'NO' (Normally Open) contact is assumed for MQTT discovery yet this can be inverted to a 'NC' (Normally Closed) contact by leveraging the 'Invert' parameter:

```
FB_DO_SW_001.InitMqttDiscoveryAsLock(
	Name := 'lock 001',			            (* The name shown in the Home Assistant front-end *)
	Device := ADR(PLC_DEVICE),				(* The device shown in Home Assistant *)
    Invert := TRUE                          (* FALSE by default = NO, TRUE = NC *)
);
```
