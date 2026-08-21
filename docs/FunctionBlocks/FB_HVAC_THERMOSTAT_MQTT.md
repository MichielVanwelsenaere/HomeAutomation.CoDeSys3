## FB_HVAC_THERMOSTAT_MQTT
<!-- fb-badge:start -->
![MQTT Discovery](https://img.shields.io/badge/MQTT%20Discovery-brightgreen)
<!-- fb-badge:end -->

### **General**

Designed to control the heat requirements in a room. Creates a thermostat entity in Home Assistant that allows control of the desired temperature.

<!-- fb-interface:start -->
### **Block diagram**

```text
       ┌─────────────────────────┐
       │ FB_HVAC_THERMOSTAT_MQTT │
       ├─────────────────────────┤
REAL ──┤ MEASURED_TEMP       OUT ├── BOOL
REAL ──┤ MEASURED_HUM            │
BOOL ──┤ ENABLED                 │
BOOL ──┤ SENSOR_VALID            │
       └─────────────────────────┘
```

### **Interface**

**Inputs**

| Pin | Type | Description |
|:--|:--|:--|
| `MEASURED_TEMP` | REAL | Measured temperature in the room. |
| `MEASURED_HUM` | REAL | Measured humidity in the room. |
| `ENABLED` | BOOL | Enables or disables the thermostat. |
| `SENSOR_VALID` | BOOL | Whether `MEASURED_TEMP` can be trusted — wire it to the sensor's own health, e.g. `DataAvailable AND NOT Error`. FALSE, or a reading outside -50..80 °C, raises `SensorFault`, forces `OUT` off and publishes `/FAULT`. Defaults TRUE so an existing call site keeps working, but a thermostat left on the default will act on a stale reading from a dead sensor. |

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `OUT` | BOOL | When high the room requires heating. |

### **Methods**

**`FB_init`** — Constructor, overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `MinAllowedTemp` | REAL |  | Minimum allowed temperature in the room. If the thermostat is on 'auto' mode the thermostat will heat up the room when the temperature drops below this value. Not possible to set the thermostat to a lower temperature value. |
| `MaxAllowedTemp` | REAL |  | Maximum allowed temperature in the room. Not possible to set the thermostat to a higher temperature value. |
| `Hysteresis` | REAL |  | Allowed temperature delta from the target temperature. If the measured temperature drops below the target temperature minus the hysteresis value the heating will be turned on. |

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
| `TempStep` | REAL |  | Step size for the target temperature in the Home Assistant thermostat card. |
| `overruleId` | STRING(255) | `''` | Overrides the generated entity id. Leave empty to derive it from the function block name. |
| `meta` | STRING(255) | `''` | Extra JSON merged into the discovery config. Leave empty for none. |

**`PublishReceived`** — Callback method called by the callback collector when a message is received on the subscribed topic by the callback collector.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `Data` | MQTT.CALLBACK_DATA |  | Received message, supplied by the callback collector. |
<!-- fb-interface:end -->

### **MQTT publish behavior**

Requires method call `InitMQTT` to enable MQTT capabilities.

| Event                 | Description                         | Topic suffix | MQTT payload | QoS | Retain flag | Published on startup |
| :-------------------- | :---------------------------------- | :----------- | :----------- | :-- | :---------- | :------------------- |
| **output changes: OUT** | A change is detected on output `OUT`. | _(none)_ | `TRUE/FALSE` | 2 | `TRUE` | yes |
| **input changes: MEASURED_TEMP** | A change is detected on input `MEASURED_TEMP`. | `/TEMP` | real value | 2 | `TRUE` | yes |
| **input changes: MEASURED_HUM** | A change is detected on input `MEASURED_HUM`. | `/HUM` | real value | 2 | `TRUE` | yes |
| **target temperature changes** | The desired temperature is changed, either locally or through MQTT. | `/DESIRED_TEMP` | real value | 2 | `TRUE` | yes |
| **thermostat mode changes** | The thermostat mode is changed. | `/MODE` | `auto`, `off` or `heat` | 2 | `TRUE` | yes |
| **allowed range is published** | The configured `MinAllowedTemp` / `MaxAllowedTemp` bounds. | `/MIN_TEMP`, `/MAX_TEMP` | real value | 2 | `TRUE` | yes |

MQTT publish topic is a concatenation of the publish prefix and the function block name, followed by the topic suffix listed above where applicable.

### **MQTT subscribe behavior**

Requires method call `InitMQTT` to enable MQTT capabilities. Commands are executed by the FB if the topic `MQTTSubscribeTopic` matches the MQTT topic and the payload exists in the table below.

| Command                     | Description                                          | expected payload | Additional notes                                                 |
| :-------------------------- | :--------------------------------------------------- | :--------------- | :--------------------------------------------------------------- |
| **Set desired temperature**  | Request to set a specific temperature value. Value expected on the `DESIRED_TEMP` subtopic.                   | any number          | Command executed when the value is between `MinAllowedTemp` and `MaxAllowedTemp`. |
| **Set desired thermostat mode**  | Request to set the thermostat to a specific mode. Value expected on the `MODE` subtopic.                   | `auto`, `off` or `heat`  |  |

MQTT subscription topic is a concatenation of the subscribe prefix variable and the function block name.
