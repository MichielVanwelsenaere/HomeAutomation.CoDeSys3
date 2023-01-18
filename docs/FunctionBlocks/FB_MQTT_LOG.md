## FB_MQTT_DEVICE


![](../_img/mqtt_log_in_ha.png)

INPUT(S)


OUTPUT(S)


METHOD(S)
- InitMQTT: enables MQTT events on the FB, an overview of the parameters:
    - `MQTTPublishPrefix`: datatype *POINTER TO STRING*, pointer to the MQTT publish prefix that should be used for publishing any messages/events for this FB. Suffix is automatically set to FB name. 
    - `pMqttPublishQueue`: datatype *POINTER TO FB_MqttPublishQueue*, pointer to the MQTT queue to publish messages.
    - `MqttQos`: datatype *SD_MQTT.QoS*, configures the MQTT Qos for the function block published messages.  
    - `MqttRetain`: datatype *BOOL*, configures the MQTT retain flag for the function block published messages.
- send: allows logging to MQTT. 
    - `payload`: datatype *STRING*, the payload to be sent to MQTT. String(128)

### __Code example__
- variables initiation: (inside MqttVariables)
```
	MQTT_logger							:FB_MQTT_LOG;
```

- Init MQTT method call (called once during startup):
```
MqttVariables.MQTT_logger.InitMqtt(
	MQTTPublishPrefix:= ADR(MqttPubLogPrefix),											
	pMqttPublishQueue := ADR(MqttVariables.fbMqttPublishQueue),				
	MqttQos:=MQTT.QoS.ExactlyOnce, 
	MqttRetain:=FALSE											
);
```

To send a message to MQTT:
```
MqttVariables.MQTT_logger.send('Init finished');
```

##  Home Assistant

To show the MQTT messages in Home Assistant, you need to go through three steps:
1. Add the following to your `configuration.yaml`:
    ```yaml
    - name: "plc_log"
      object_id: "plc_log"
      unique_id: "plc_log"
      state_topic: "Devices/PLC/House/debug"
      qos: 0
      device: *device # write or link your device here
      availability: *availability # write or link your availability here
    ```
1. Install the add-on `variables`, [see here](https://github.com/Wibias/hass-variables)
2. Add the following to your `configuration.yaml`:
    ```yaml
    variable:
      plc_log_history:
        value: 'undefined'
        restore: true
        attributes:
          history_1: "emty"
          icon: mdi:file-document
          name: 'PLC logs'
    ```

3. Add the following to your `automations.yaml`:
    ```yaml
    - id: 'automation_plc_log'
      alias: 'Update log history'
      trigger:
      - platform: state
        entity_id:
          - sensor.plc_log
      action:
        - service: variable.set_variable
          data:
            variable: plc_log_history
            replace_attributes: true
            attributes:
                r1: "{{now().strftime('%Y-%m-%d %H:%M')}} {{states('sensor.plc_log')}}"
                r2: "{{state_attr('variable.plc_log_history','r1')}}"
                r3: "{{state_attr('variable.plc_log_history','r2')}}"
                r4: "{{state_attr('variable.plc_log_history','r3')}}"
                r5: "{{state_attr('variable.plc_log_history','r4')}}"
                r6: "{{state_attr('variable.plc_log_history','r5')}}"
                r7: "{{state_attr('variable.plc_log_history','r6')}}"
                r8: "{{state_attr('variable.plc_log_history','r7')}}"
                r9: "{{state_attr('variable.plc_log_history','r8')}}"
                r10: "{{state_attr('variable.plc_log_history','r9')}}"
    ```
    
1. Install the custom `entity-attributes-card`, [see here](https://github.com/custom-cards/entity-attributes-card)
4. Add the following to your lovelace dashboard:
    ```yaml
    type: custom:entity-attributes-card
    entity: sensor.plc_log
    heading_name: Name
    heading_state: State
    filter:
      include:
        - variable.plc_log_history.r1
        - variable.plc_log_history.r2
        - variable.plc_log_history.r3
        - variable.plc_log_history.r4
        - variable.plc_log_history.r5
        - variable.plc_log_history.r6
        - variable.plc_log_history.r7
        - variable.plc_log_history.r8
        - variable.plc_log_history.r9
        - variable.plc_log_history.r10
    ```	
    7. Bonus, add styling to the card by [card-mod](https://github.com/thomasloven/lovelace-card-mod):
    ```yaml
    card_mod:
      style: |
        th,
        td:nth-child(1)  {
          display:none;
        }
        tr{
          background:none !important;
        }
    ```
