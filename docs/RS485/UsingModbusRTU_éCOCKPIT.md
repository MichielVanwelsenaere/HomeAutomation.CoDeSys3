## Using Modbus RTU with the é!COCKPIT runtime

### __Content__
This page describes adding a modbus RTU device using the é!COCKPIT runtime.
In case a function block for your specific device is not present yet in this project. Please consider reading the [RS485 tips and tricks](../FAQ/RS485_tips_and_tricks.md) page if this is your first time connecting a RS485 device.


- [Assign the PLC serial port to the PLC runtime](#Assign-the-PLC-serial-port-to-the-PLC-runtime)
- [Required libraries](#Required-libraries)
- [Adding a dummy slave device](#Adding-a-slave-device)
- [Using code to access the RS485 serial port](#Using-code-to-access-the-RS485-serial-port)

### __Assign the PLC serial port to the PLC runtime__
In order use the onboard PLC serial port from the PLC runtime this needs to be configured from the web based management tool:

<img src="../_img/RS485_éCOCKPIT_WBM.png" width="550">

Note that it's necessary to reboot the controller after a change to this setting.

### __Required libraries__
Make sure the following libraries are present in the project:
```
WagoAppPlcModbus
```

### __Using code to access the RS485 serial port__
A specific implementation example can be found inside the project in the 'PLC_PRG_RS485' program.


