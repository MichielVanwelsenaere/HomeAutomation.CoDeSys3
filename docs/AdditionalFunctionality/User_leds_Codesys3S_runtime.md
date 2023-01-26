## User leds (Codesys 3S runtime)

### **General**

It's possible to control the *U* leds on a WAGO PFC controller. The example below illustrates how.

### **Prerequisites**
the following libaries should be present:

- CmpPfcx00

### **Implementation**
The project has a working implementation that controls the *U1* led, displaying it green when there is a working connection with the MQTT broker, flashing red if not.

- controlling the led depending on connection with the MQTT broker
```
IF MQTTClient.connected THEN
     PFC.SetLed(which:=PFC.LED.U1, how:=PFC.LedState.STATIC_GRN);
ELSE
     PFC.SetLed(which:=PFC.LED.U1, how:=PFC.LedState.BLINK_RED);
END_IF 
```
The code has been commented out to prevent interference with users that work with the é!COCKPIT runtime.
