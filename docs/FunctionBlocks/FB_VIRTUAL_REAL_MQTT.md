## FB_VIRTUAL_REAL_MQTT
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
A virtual function block can be used in one of two modes:
- input: inputs a value in the PLC processing logic through MQTT.
- output: outputs a value from the PLC processing logic through MQTT.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌──────────────────────┐
       │ FB_VIRTUAL_REAL_MQTT │
       ├──────────────────────┤
REAL ──┤ IN               OUT ├── REAL
       └──────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `IN` | REAL | Input for the value that should be published through MQTT, provision this input when using the virtual function block in output mode. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `OUT` | REAL | Output for the value that is received through the MQTT subscription. provision this output in other processing logic when using the virtual function block in input mode. |

### **Methods**

**`ConfigureFunctionBlockAsVirtualInput`** — Configures the behavior of the function block as a virtual input using the parameters below:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `DefaultValue` | REAL |  | Value to set at startup if default value at startup behavior is configured. |
| `SetDefaultValueStartup` | BOOL |  | Set to TRUE to set the DefaultValue at PLC startup. |
| `PublishAtStartup` | BOOL |  | Set to TRUE to get an MQTT publish message of the virtual input value at PLC startup. |
| `UsePersistentAtStartup` | BOOL |  | Set to TRUE to use persistence to maintain the virtual input value through power cycles. |
| `ConfirmReceival` | BOOL |  | Set to TRUE to get an MQTT publish message when the value is updated. |

**`ConfigureFunctionBlockAsVirtualOutput`** — Configures the behavior of the function block as a virtual output using the parameters below:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `PublishAtStartup` | BOOL |  | Set to TRUE to get an MQTT publish message of the virtual output value at PLC startup. |

**`InitMqtt`** — Enables MQTT on the function block. Call once at startup.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MQTTPublishPrefix` | POINTER TO STRING |  | Pointer to the MQTT publish prefix used for this block. The function block name is appended automatically. |
| `MQTTSubscribePrefix` | POINTER TO STRING |  | Pointer to the MQTT subscribe prefix used for this block. The function block name is appended automatically. |
| `pMqttPublishQueue` | POINTER TO FB_MqttPublishQueue |  | Pointer to the shared MQTT queue that carries messages to the broker. |
| `pMqttCallbackCollector` | POINTER TO MQTT.CallbackCollector |  | Pointer to the callback collector this block registers with to receive subscription messages. |
| `MqttQos` | MQTT.QoS |  | MQTT QoS used for messages published by this block. |
| `MqttRetain` | BOOL |  | MQTT retain flag used for messages published by this block. |

**`PublishReceived`** — Callback method called by the callback collector when a message is received on the subscribed topic by the callback collector.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |

**`SetValue`** — Method to set the function block virtual value, only works if the function block is in output mode.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Value` | REAL |  | Value to publish. Only effective in output mode. |
<!-- fb-interface:end -->

### **MQTT publish behavior**
Requires method call `InitMQTT` to enable MQTT capabilities. Only applicable if the function block is configured in output mode, outputting the value on input `IN` or set using the SetValue method through MQTT.  

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **input changes: IN**   | A change is detected on input `IN`. | `TRUE/FALSE` | configured in method call `InitMQTT` | configured in method call `InitMQTT` | configured in method call `InitMQTT`

MQTT publish topic is a concatenation of the publish prefix and the function block name. 

### **MQTT subscribe behavior**
Requires method call `InitMQTT` to enable MQTT capabilities. Only applicable if the function block is configured in input mode which will allow the input of a value to the PLC through MQTT which will be exposed on the function block `OUT` output.
Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command | Description | expected payload | Additional notes | 
|:-------------|:------------------|:------------------|:------------------|
| **Change output to float value** | Request to change output to a specific float value. | a float value | 

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name. 

### **Code example**

- variables initiation:
```
MqttPubVirtualPrefix            :STRING(100) := 'Devices/PLC/Lab/Out/Virtuals/';
MqttSubVirtualPrefix            :STRING(100) := 'Devices/PLC/Lab/In/Virtuals/';
FB_VIRTUAL_REAL_001             :FB_VIRTUAL_REAL_MQTT;
```

- Init MQTT method call (called once during startup):
```
FB_VIRTUAL_REAL_001.InitMqtt(MQTTPublishPrefix:= ADR(MqttPubVirtualPrefix),				
	MQTTSubscribePrefix:= ADR(MqttSubVirtualPrefix),									
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue),						
	pMqttCallbackCollector := ADR(MqttVariables.collector_FB_VIRTUAL_MQTT),
	MqttQos:=MQTT.QoS.ExactlyOnce, 
	MqttRetain:=FALSE											
);
```
The MQTT publish topic in this code example will be `Devices/PLC/Lab/Out/Virtuals/FB_VIRTUAL_REAL_001` (MQTTPubSwitchPrefix variable + function block name). The subscription topic will be `Devices/PLC/Lab/In/Virtuals/FB_VIRTUAL_REAL_001` (MQTTSubSwitchPrefix variable + function block name).

- Configuring the function block as a virtual input (called once during startup):
```
FB_VIRTUAL_REAL_001.ConfigureFunctionBlockAsVirtualInput(DefaultValue:=12.234,
    SetDefaultValueStartup:=TRUE,
    PublishAtStartup:=TRUE,
    UsePersistentAtStartup:=FALSE,
    ConfirmReceival:=TRUE
);
```

- Calling the virtual function block to allow processing (cyclic):
```
FB_VIRTUAL_REAL_001();
```

- Using the virtual function block value when using input mode (cyclic):
```
X:=FB_VIRTUAL_REAL_001.OUT;
```
A value X in the PLC is set to the OUT value of the virtual function block, the OUT value being controlled through MQTT.

- Using the virtual function block value when using output mode (cyclic):
```
FB_VIRTUAL_REAL_001.IN:=X;
```
A value X in the PLC is set to the IN value of the virtual function block, the IN value being published through MQTT.

### **Home Assistant YAML**
When using the function block as a virtual output use the YAML code below in your [MQTT Sensor](https://www.home-assistant.io/integrations/sensor.mqtt/) config to integrate with Home Assistant:

```YAML
mqtt:
  sensor:
  - name: "FB_VIRTUAL_REAL_001"
    state_topic: "Devices/PLC/Lab/Out/Virtuals/FB_VIRTUAL_REAL_001"
    qos: 2  
    availability_topic: "Devices/PLC/Lab/availability"
    payload_available: "online"
    payload_not_available: "offline"
```

When using the function block as a virtual input use the YAML code below in your [Input Number](https://www.home-assistant.io/integrations/input_number/) config to integrate with Home Assistant: 

```YAML
input_number:
  fb_virtual_real_001:
    name: friendly name
    min: 1
    max: 30
    step: 0.1
    unit_of_measurement: degrees
    icon: mdi:target
```

Configure the automation below in your automations.yaml file to publish any changes on the Input Number slider on an MQTT topic:

```YAML
- id: fb_virtual_real_001-to-mqtt
  alias: FB_VIRTUAL_REAL_001 slider moved
  trigger:
    platform: state
    entity_id: input_number.fb_virtual_real_001
  action:
    service: mqtt.publish
    data_template:
      topic: 'Devices/PLC/Lab/In/Virtuals/FB_VIRTUAL_REAL_001'
      retain: true
      payload: "{{ states('input_number.fb_virtual_real_001') | float }}"
```
