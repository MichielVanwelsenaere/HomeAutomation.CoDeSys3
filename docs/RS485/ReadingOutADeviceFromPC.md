## Reading out a device from a PC

### __Content__
This page describes reading out a modbus RTU device from PC to gain some more insights in the structure of the modbus registers or your device and/or troubleshooting purposes.

- [Required Hardware](#Required-Hardware)
- [Performing modbus RTU scans](#Performing-modbus-RTU-scans)
- [Performing modbus RTU commands](#Performing-modbus-RTU-commands)

### __Required Hardware__
To be able to communicate with modbus RTU devices from a PC you'll need a USB to RS485 convertor. Example: [link](https://www.aliexpress.com/item/32638090708.html?spm=a2g0s.9042311.0.0.27424c4dWhWZOx).
Consider acquiring two convertors to simultaneously send modbus commands and sniff the traffic. 

### __Performing modbus RTU scans__


### __Performing modbus RTU commands__
Using [QModMaster](https://sourceforge.net/projects/qmodmaster/) specific modbus RTU commands can be executed. For example:

<img src="../_img/RS485_PC_QModMaster_Commands.png" width="550">

Note: use 'Device Manager' to establish on what COM port the USB to RS485 convertor is located.