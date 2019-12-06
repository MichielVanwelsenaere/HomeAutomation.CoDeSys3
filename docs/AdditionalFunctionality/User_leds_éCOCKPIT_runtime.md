## User leds (é!COCKPIT runtime)

### __General__

It's possible to control the *U* leds on a WAGO PFC controller. The example below illustrates how.

### __Prerequisites__
the following libaries should be present:
    - WagoAppAppLED
    - WagoTypesAppLED

### __Implementation__
The project has a working implementation that controls the *U1* led, displaying it green when there is a working connection with the MQTT broker, flashing red if not.

- variables initiation (inside *PLC_PRG_MQTT*):
```
LED_1_BrokerStatus		:FbAppLED;
```

- controlling the led depending on connection with the MQTT broker
```
LED_1_BrokerStatus(eID:=eLedID.AppLED_1, xOpen:=TRUE );
IF(MQTTClient.connected) THEN
	LED_1_BrokerStatus.SetStatic(eLedColor.Green);
ELSE
	LED_1_BrokerStatus.SetFlash(T#1S,eLedColor.Red, eLedColor.Off);  
END_IF 
```
The code has been commented out to prevent interference with users that work with the CODESYS 3S runtime.
