## Using Modbus RTU with the é!COCKPIT runtime

### __Content__
This page describes adding a modbus RTU device using the é!COCKPIT runtime.

- [Assign the PLC serial port to the PLC runtime](#Assign-the-PLC-serial-port-to-the-PLC-runtime)
- [Adding a dummy slave device](#Adding-a-slave-device)
- [Using code to access the RS485 serial port](#Using-code-to-access-the-RS485-serial-port)

### __Assign the PLC serial port to the PLC runtime__


### __Adding a dummy slave device__
In order to enable Modbus RTU communcation a dummy Modbus RTU device needs to be added in the device overview:

<img src="../_img/RS485_éCOCKPIT_DummyDevice_1.png" width="550"> <br /> 

<img src="../_img/RS485_éCOCKPIT_DummyDevice_2.png" width="350">

### __Using code to access the RS485 serial port__
The device configurator overview can be used to add modbus RTU slave devices but it doesn't allow for troubleshooting. Therefore it's preferable to use code to read out the Modbus RTU devices.

A specific implementation example can be found inside the project:

<img src="../_img/RS485_éCOCKPIT_Codebase_1.png" width="350">



