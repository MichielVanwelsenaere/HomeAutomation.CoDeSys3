# MQTT enabled CoDeSys 3 Home Automation
<a href="https://github.com/MichielVanwelsenaere/HomeAutomation.CoDeSys3/releases" rel="nofollow"><img src="https://img.shields.io/github/release/MichielVanwelsenaere/HomeAutomation.CoDeSys3.svg" alt="Releases"></a>
<a href="https://gitter.im/MichielVanwelsenaere/HomeAutomation.CoDeSys3" rel="nofollow"><img src="https://img.shields.io/gitter/room/HomeAutomation-CoDeSys3/community" alt="Gitter" ></a>
<a href="./LICENSE" rel="nofollow"><img src="https://img.shields.io/github/license/MichielVanwelsenaere/HomeAutomation.CoDeSys3.svg" alt="License"></a>

This CoDeSys 3.5 project is built for home automation purposes. The goal of the approach is to perform any critical operations like reading inputs, switching light, controlling sunscreens, etc. Inside the PLC itself and make use of MQTT events to send events to an MQTT broker. Using MQTT subscriptions it's possible to send commands to the PLC to control -for example- outputs. 

The purpose? Redundancy on a software level but also on a hardware level!
- PLCs are very (very) robust controllers: no PC, SoC, etc. is more robust and failure resistant. 
- Hardware continuity: Home automation providers often renew their modules every X years, modules aren't sold anymore or a full upgrade is required when something brakes. PLCs models and their modules are sold decades after their initial release date. Don't believe me? Check out the Wago 750 series controllers and modules. 
- Avoid performing critical operations that should work 24/7 inside a less redundant controller (it will fail sooner or later).
- Keep your wive/girlfriend happy when you're not at home and your Rpi, Odroid, Banana Pi, Pc crashes (running your MQTT broker, OpenHab, Home Assistant, etc.).

# Supported Runtimes
The project is developed using the IEC 61131-3 standard, there are multiple development environments with their own runtime that support the standard:

- [CODESYS V3 by 3S-Smart Software Solutions](https://www.codesys.com/)
- [é!COCKPIT by WAGO](https://www.wago.com/global/automation-technology/discover-software/ecockpit-engineering-software) (WAGO PLCs only)

# Architecture
Core processing logic is executed in the (robust) PLC. Meaning that events like reading pushbuttons/switches, updating outputs are executed in the PLC software. To enable integration with external software the PLC sends out events to an MQTT broker when events occur (like pushbutton events, outputs that change state). MQTT subscriptions are enabled as well to allow control from the external software to control -for example- outputs.

![GeneralArchitecture](./docs/_img/HomeAutomation.GeneralArchitecture.jpg)

# Software Architecture

More information on the software architecture [here](./docs/SoftwareArchitecture.md).

# Function blocks

## Basic function blocks
Basic function blocks for basic IO events and operations.

- [FB_INPUT_PUSHBUTTON_MQTT](./docs/FunctionBlocks/FB_INPUT_PUSHBUTTON_MQTT.md)
- [FB_INPUT_PUSHBUTTON_DIMMER_MQTT](./docs/FunctionBlocks/FB_INPUT_PUSHBUTTON_DIMMER_MQTT.md)
- [FB_INPUT_BINARYSENSOR_MQTT](./docs/FunctionBlocks/FB_INPUT_BINARYSENSOR_MQTT.md)
- [FB_OUTPUT_SWITCH_MQTT](./docs/FunctionBlocks/FB_OUTPUT_SWITCH_MQTT.md)
- [FB_OUTPUT_DIMMER_MQTT](./docs/FunctionBlocks/FB_OUTPUT_DIMMER_MQTT.md)
- [FB_OUTPUT_COVER_MQTT](./docs/FunctionBlocks/FB_OUTPUT_COVER_MQTT.md)

## Virtual function blocks
Function blocks developed to easily set and get values from the processing logic through MQTT.

- [FB_VIRTUAL_BOOL_MQTT](./docs/FunctionBlocks/FB_VIRTUAL_BOOL_MQTT.md)
- [FB_VIRTUAL_INT_MQTT](./docs/FunctionBlocks/FB_VIRTUAL_INT_MQTT.md)
- [FB_VIRTUAL_STRING_MQTT](./docs/FunctionBlocks/FB_VIRTUAL_STRING_MQTT.md)
- [FB_VIRTUAL_REAL_MQTT](./docs/FunctionBlocks/FB_VIRTUAL_REAL_MQTT.md)

## RS485
With many PLCs having a onboard RS485 serial port it is a popular protocol to create a robust Modbus RTU sensor network.

### Adding a Modbus device
Adding a Modbus device differs depending on the PLC/development environment used. The topics belows address the creation of a Modbus device in several development environments:
    - [Creating a Modbus RTU device using CODESYS 3S runtime](./docs/RS485/CreatingModbusRTUDevice_CODESYS3S.md)
    - [Creating a Modbus RTU device using é!COCKPIT runtime](./docs/RS485/CreatingModbusRTUDevice_éCOCKPIT.md)

### RS485 function blocks

- [FB_RS485_Eastron_SMD220_MQTT](./docs/FunctionBlocks/FB_RS485_Eastron_SMD220_MQTT.md)

# Additional functionality

- [MQTT Birth and Last will message](./docs/AdditionalFunctionality/MQTT_Birth_and_Last_will_message.md)
- [Controlling user leds](./docs/AdditionalFunctionality/User_leds_éCOCKPIT_runtime.md) (é!COCKPIT runtime)

# FAQ

- [Contributing guidelines](./docs/CONTRIBUTING.md)
- [Getting started guide](./docs/FAQ/Getting_started_guide_CODESYS_3S.md) (CODESYS 3S runtime)
- [Getting started guide](./docs/FAQ/Getting_started_guide_éCOCKPIT.md) (é!COCKPIT runtime)
- [How-to: adding a new MQTT subscription](./docs/FAQ/Howto_adding_a_new_MQTT_subscription.md)
- [I'm missing some functionality](./docs/FAQ/Missing_functionality.md)

# Libraries

The following libraries are used in this PLC project and can be found under `src\Libraries`:
- CommonTypesAndFunctions ([stefandreyer/CODESYS-Common](https://github.com/stefandreyer/CODESYS-Common))
- MQTT ([stefandreyer/CODESYS-MQTT](https://github.com/stefandreyer/CODESYS-MQTT))
- OSCAT NETWORK ([link](https://store.codesys.com/oscat-building.html))
- OSCAT BASIC ([link](https://store.codesys.com/oscat-basic.html))
- OSCAT BUILDING ([link](https://store.codesys.com/oscat-network.html))

Special thanks to StefanDreyer for his assistance in some of the MQTT aspects of this project and his great work on his open-source CoDeSys MQTT library.

