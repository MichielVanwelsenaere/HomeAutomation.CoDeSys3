## FB_RS485_ESERA_OWD_MQTT

### __General__
Represents a single One Wire Device (OWD) on the 1-Wire bus network.

### __Block diagram__

<img src="../_img/FB_RS485_ESERA_OWD_MQTT.svg" width="350">

### __MQTT Event Behaviour__
Requires method call `InitMQTT` to enable MQTT capabilities.

| Event | Description | MQTT payload | QoS | Retain flag | Published on startup |
|:-------------|:------------------|:------------------|:------------------|:--------------------------|:--------------------------|
| **sensor data is received**   | temperature, humidity, etc readings received. | real value | 2 | `FALSE` | no

MQTT publish topic is a concatination of the publish prefix and the function block name, the OWD numer and a unique sensor value. For example:

`Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/TEMP`

Naturally `/TEMP` will only be ommited by the OWD is the physical sensor exposes it.

| output       | MQTT topc suffic | Unit         | 
|:-------------|:------------------|:------------------|
| TEMPERATURE | `/TEMP` | °C 
| HUMIDITY | `/HUM` | % 
| OWD_VOLTAGE |  `/OWDV` | V 
| AIR_QUALITY | `/AIRQ` | ppm 
| DEW_POINT | `/DEWP` | °C 
| BRIGHTNESS | `/BNESS` | Lux

### __Code example__

- Enabling the OWD & configuring the OWD polling interval (called once during startup using the managing gateway function block):
```
FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME.EnableOwd(
	OwdNumber := 1,
	DataPollingInterval := T#2M
);
```

### __Home Assistant YAML__
To integrate with Home Assistant use the YAML code below in your [MQTT sensors](https://www.home-assistant.io/components/sensor.mqtt/) config. Adopt where necessary depending on the exposed values of your OWD.

```YAML

mqtt:
  sensor:
  - name: "temperature kitchen"
    object_id: "kitchen_temp"
    state_topic: "Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/TEMP"
    unit_of_measurement: "°C"
    qos: 2
    availability:
      - topic: "Devices/PLC/House/Out/RS485/FB_RS485_ESERA_1WIRE_GATEWAY_MQTT_HOME/OWD/1/availability"
      - topic: "Devices/PLC/House/availability"
    availability_mode : "all"
    payload_available: "online"
    payload_not_available: "offline"
```