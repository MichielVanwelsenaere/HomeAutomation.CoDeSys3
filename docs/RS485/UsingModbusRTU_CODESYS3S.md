## Using Modbus RTU with the CODESYS 3S runtime

### **Content**
This page describes adding a Modbus RTU device using the CODESYS 3S runtime.
In case a function block for your specific device is not present in this project yet, please consider reading the [RS485 tips and tricks](../FAQ/RS485_tips_and_tricks.md) page if this is your first time connecting an RS485 device.

### **Assign the PLC serial port to the PLC runtime**
In order to use the onboard PLC serial port from the PLC runtime this needs to be configured from the Web-Based Management tool, under *Ports and Services / Serial Interface*, by assigning the serial interface to the PLC runtime instead of the Linux console.

Note that it's necessary to reboot the controller after a change to this setting.

### **Required libraries**
Make sure the following libraries are present in the project:
```
IoDrvModbus
SysCom
SysTypes2 Interfaces
```

### **Setting the serial mode on the PLC**
Although the PLC serial port is already assigned to the PLC runtime it isn't configured yet in RS485 mode.
To do so:
1. Open CODESYS
1. Connect to your PLC
1. Use the PLC shell to set the serial mode to RS485:

<img src="../_img/RS485_CODESYS3S_PLCShell.png" width="550">

Note that even when the serial mode is already set to RS485 it is advised to explicitly set it again. This has proven to fix connectivity issues when first using RS485 on a controller.

### **Using code to access the RS485 serial port**
The device configurator overview can be used to add Modbus RTU slave devices but it doesn't allow for troubleshooting. Therefore it's preferable to use code to read out the Modbus RTU devices.

A specific implementation example can be found inside the project, in the RS485 actions of the main program.

This project uses a 'CODESYS first' approach: the CODESYS 3S implementation is the one that is active in the project. Any code specific to the WAGO e!COCKPIT runtime has been commented out.
There are minor differences between the e!COCKPIT and CODESYS 3S Modbus RTU implementations. The main reason for this is that both systems have different libraries containing different function blocks and types to work with Modbus RTU.
Nevertheless, any RS485 function block developed in this project can be used with both the e!COCKPIT and CODESYS 3S Modbus RTU approach.