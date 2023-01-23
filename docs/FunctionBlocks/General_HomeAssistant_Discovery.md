## **Home Assistant discovery**

To integrate with Home Assistant automatically, add the `InitMqttDiscovery` method in `MAIN_INIT`. 

Most function blocks have a `InitMqttDiscovery` method. They do need a `FB_HomeAssistant_DEVICE` instance to work, see [FB_HomeAssistant_DEVICE](FB_HomeAssistant_DEVICE.md).

- InitMqttDiscovery: Sets all config needed for letting Home Assistant discover the dimmer automatically.
	- `name `: The name show in Home Assistant frond-end
	- `MqttDiscoverPrefix`:  pointer to string prefix for the MQTT discover topic 
	- `Device `:The device show in Home Assistant 
	- `overruleId`: OPTIONAL. leave empty to set it to the device + instance name 'HOUSE_FB_AO_DIMMER_001' for instance name, or overule to e.g. 'MY_DIMMER_GND_HALL_01'. T
	- `icon `: OPTIONAL specify icon. Default changes per function block.
	- `meta `: OPTIONAL Free field for meta data. Only visible in MQTT 

Example config:
```ST
FB_AO_DIMMER_001.InitMqttDiscovery(
	name := 'Office strip cold',							(* The name show in Home Assistant frond-end*)
	overruleId:= 'Dimm_office_cw', 							(*  e.g. 'MY_DIMMER_GND_HALL_01'  *)
	icon := 'mdi:lightbulb',  								(* specify icon*)
	MqttHADiscoveryPrefix:= ADR(MqttHADiscoveryPrefix),  	(* pointer to string prefix for the MQTT discover topic *)
	Device := FB_HomeAssistant_DEVICE,						(* The device show in Home Assistant *)
	meta := 'GeoDev office',								(* Free field for meta data. Only visible in MQTT *)
);
```


