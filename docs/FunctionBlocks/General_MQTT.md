## **All MQTT topic**

The topics are predefined once in the `MqttVariables`.

Mqtt works with subscriptions and publications. An example for a dimmer publication is 
  `Devices/PLC/House/Out/Dimmers/FB_AO_DIMMER_001/OUT`

If you change any of these topic. Keep an eye on the **length of the topic and or STRING() size**
	
```Pascal
	(* Topics *)
	MqttMain						:STRING(16) := 'Devices/';
	MqttType						:STRING(16) := 'PLC/';
	MqttDevice						:STRING(16) := 'House/';
	// e.g. Devices/PLC/House
	MqttBaseTopic					:STRING(100) := CONCAT(CONCAT(MqttMain,MqttType),MqttDevice);							
	MqttAvailabilityTopic 			:STRING(100) := CONCAT(MqttBaseTopic,'availability');
	MqttPubLogPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'logger/');
	MqttHADiscoveryPrefix			:STRING(16) := 'homeassistant/';
	
	(* FB Topics *)
	MqttPushbuttonPrefix			:STRING(100) := CONCAT(MqttBaseTopic,'Out/DigitalInputs/Pushbuttons/');
	MqttPubSwitchPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'Out/DigitalOutputs/');
	MqttSubSwitchPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'In/DigitalOutputs/');
	MqttPubCoverPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'Out/Covers/');
	MqttSubCoverPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'In/Covers/');
	MqttPubDimmerPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'Out/Dimmers/');
	MqttSubDimmerPrefix				:STRING(100) := CONCAT(MqttBaseTopic,'In/Dimmers/');
	MqttPubVirtualPrefix			:STRING(100) := CONCAT(MqttBaseTopic,'Out/Virtuals/');
	MqttSubVirtualPrefix			:STRING(100) := CONCAT(MqttBaseTopic,'In/Virtuals/');
	
	(* Wildcard subscriptions *)
	MqttSubSwitchTopic				:STRING(100) := CONCAT(MqttSubSwitchPrefix,'+');
	MqttSubCoverTopic				:STRING(100) := CONCAT(MqttSubCoverPrefix,'+');
	MqttSubVirtualTopic				:STRING(100) := CONCAT(MqttSubVirtualPrefix,'+');
	MqttSubDimmerTopic				:STRING(100) := CONCAT(MqttSubDimmerPrefix,'#');
```
