## How-to: Adding a new MQTT subscription
This page describes the steps required to add a new MQTT subscription in the reference project. 

1. Add a new subscriber function block in the *PLC_PRG_MQTT* program variable declaration. Example below:
```
(* variables for MQTT subscribing *)
subscriber_FB_OUTPUT_SWITCH_MQTT:MQTT.MQTTSubscribe;
subscriber_FB_OUTPUT_COVER_MQTT:MQTT.MQTTSubscribe;	
subscriber_FB_DIMMER_MQTT:MQTT.MQTTSubscribe;
```

2. Add a new callback function block in the *MqttVariables* global variables. Example below:
```
(* Shared Variables for MQTT subscribe communication *)
collector_FB_OUTPUT_SWITCH_MQTT		:MQTT.CallbackCollector;		
collector_FB_OUTPUT_COVER_MQTT		:MQTT.CallbackCollector;	
collector_FB_DIMMER_MQTT			:MQTT.CallbackCollector;
```
These function blocks are created in a global variable list so they are accessible from all PRGs. This is necessary because function blocks require access to the callback collector in order to register themselves for an MQTT subscription.

3. Initialize the subscriber function block in the *MQTT_INIT* action in the *PLC_PRG_MQTT* program. Example below:
```
(* INIT MQTT SUBSCRIBE STUFF *)
subscriber_FB_OUTPUT_SWITCH_MQTT.SetMqttInOut(MQTT_IN_OUT:= ADR(MQTT_IN_OUT));	
subscriber_FB_OUTPUT_COVER_MQTT.SetMqttInOut(MQTT_IN_OUT:= ADR(MQTT_IN_OUT));
subscriber_FB_DIMMER_MQTT.SetMqttInOut(MQTT_IN_OUT:= ADR(MQTT_IN_OUT));
```
The *MQTT_IN_OUT* is the object that links the subscribers to the MQTT Client.

4. Call the subscriber function block in the *MQTT_SUBSCRIBE* action in the *PLC_PRG_MQTT* program. Example below:
```
subscriber_FB_OUTPUT_SWITCH_MQTT(
	Subscribe:= TRUE, 
	Topic:= ADR('Devices/PLC/Lab/In/DigitalOutputs/+'), 
	QoSSubscribe:= MQTT.QoS.ExactlyOnce, 
	ExpectingString:= TRUE, 
	Callback:= MqttVariables.collector_FB_OUTPUT_SWITCH_MQTT,
);
	
subscriber_FB_OUTPUT_COVER_MQTT(
	Subscribe:= TRUE, 
	Topic:= ADR('Devices/PLC/Lab/In/Covers/+'), 
	QoSSubscribe:= MQTT.QoS.ExactlyOnce, 
	ExpectingString:= TRUE, 
	Callback:= MqttVariables.collector_FB_OUTPUT_COVER_MQTT,
);
```

5. Register the required function blocks against the callback function block to trigger the callback method when a new message arrives on the subscribed topic. Example below:
```
pMqttCallbackCollector^.put(instance:= THIS^);
```
A more in-depth implementation can be found in the *InitMqtt* method of every MQTT function block in the reference project.

6. Implement the callback method triggered by the callback function block. More details below:
    - Add the *IMPLEMENTS* statement:
        ```
        FUNCTION_BLOCK FB_OUTPUT_DIMMER_MQTT EXTENDS FB_MQTT_BASE IMPLEMENTS MQTT.MQTT_SUBSCRIBE_CALLBACK
        ```
    - Add the *PublishReceived* callback method:
        ```
        METHOD PublishReceived : bool
        VAR_INPUT
	        (*Collection of received Data*)
	        Data	: MQTT.CALLBACK_DATA;
        END_VAR
        ```
    - Add logic to process the received MQTT message: in this reference project a check is executed to see whether the subscription that triggered the callback method matches the subscription configured in the *MqttInit* method. In that method the subscription topic is automatically concatenated with the function block name. For more in-depth details, study the *PublishReceived* and *MqttInit* methods of every MQTT function block in the reference project.


