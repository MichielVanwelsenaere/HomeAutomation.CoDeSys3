## Using Modbus RTU with the CODESYS 3S runtime

### __Content__
This page describes adding a modbus RTU device using the CODESYS 3S runtime.

- [Configuring the PLC master](#Configuring-the-PLC-master)
- [Adding a slave device](#Adding-a-slave-device)

### __Configuring the PLC master__
From the 'device' tab select the plc and add a new device. To start the com port needs to be added:

<img src="../_img/RS485_CODESYS3S_AddingMaster_1.png" width="550">
<img src="../_img/RS485_CODESYS3S_AddingMaster_2.png" width="550">

After adding the com port to the device tree it's possible to add the modbus master device:

<img src="../_img/RS485_CODESYS3S_AddingMaster_3.png" width="550">
<img src="../_img/RS485_CODESYS3S_AddingMaster_4.png" width="550">

With both present the modbus settings can be configured, to configure specific RS485 protocol settings use the configuration tab on the com port:

<img src="../_img/RS485_CODESYS3S_AddingMaster_5.png" width="550">

To configure specific modbus master settings use the configuration tab on the Modbus master:

<img src="../_img/RS485_CODESYS3S_AddingMaster_6.png" width="550">

Enable the 'Auto-communication restart' checkbox to prevent transient startup issues (for example) on slave devices to block modbus communication.

### __Adding a slave device__
From the 'device' tab select the modbus master added in previous step and add a new modbus slave device:

<img src="../_img/RS485_CODESYS3S_AddingSlave_1.png" width="550">
<img src="../_img/RS485_CODESYS3S_AddingSlave_2.png" width="550">
