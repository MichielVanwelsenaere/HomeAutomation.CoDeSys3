## MQTT Birth and Last will message

### __General__

The software supports so-called Birth and Last Will and Testament (LWT) messages. The former is used to send a message after the service has started, and the latter is used to notify other clients about an ungracefully disconnected client. In addtion to a Birth message on startup the Birth message is also published cyclic as a harbeat.

### __Examples__

<ins>Birth message:</ins></br>
Topic: `Devices/PLC/House/availability`</br>
Payload: `online`


<ins>LWT message:</ins></br>
Topic: `Devices/PLC/House/availability`</br>
Payload: `offline`

Note that the Topics and payloads can be changed in de code. The Birth message is by default published during startup and after that every 5 seconds (hartbeat). This can be changed as well in the code. 
