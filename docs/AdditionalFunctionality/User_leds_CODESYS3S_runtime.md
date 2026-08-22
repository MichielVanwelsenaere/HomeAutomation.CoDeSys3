## User LEDs (CODESYS 3S runtime)

### **General**

It's possible to control the *U* LEDs on a WAGO PFC controller, which makes the state of the PLC readable from the cabinet without a laptop. The project uses two of them.

### **Prerequisites**
The following libraries should be present:

- CmpPfcx00

### **U1: MQTT broker connection**

Live in the `MQTT_PUBLISH` action of `PRG_MQTT`. The LED turns green when the client connects to the broker and flashes red when it disconnects. Both are driven by edge triggers rather than by polling the connection flag, so the LED is only written when the state actually changes:

```
(* set user led green if connected to MQTT broker, flashing red if not *)
IF MQTTConnectTrigger.Q THEN
     PFC.SetLed(which:=PFC.LED.U1, how:=PFC.LedState.STATIC_GRN);
END_IF
IF MQTTDisconnectTrigger.Q THEN
     PFC.SetLed(which:=PFC.LED.U1, how:=PFC.LedState.BLINK_RED);
END_IF
```

### **U3: DMX / Art-Net node reachability**

Live in `PRG_PING_DMX`. The LED turns green when the Art-Net node answers a ping and flashes red when it stops responding or the send step reports an error:

```
PFC.SetLed(which:=PFC.LED.U3, how:=PFC.LedState.STATIC_GRN);
GVL_MQTT.PLC_Device.SendLogMessage('DMX ping OK');
```

### **Adding your own**

`PFC.SetLed` takes the LED (`PFC.LED.U1` … `U3`) and the state (`PFC.LedState.STATIC_GRN`, `BLINK_RED`, and the other members of that enum). Drive it from an edge trigger rather than calling it every cycle.
