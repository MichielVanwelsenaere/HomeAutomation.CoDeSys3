# MQTT enabled Codesys 3 Home Automation
This CodeSys 3.5 project is build for home automation purposes. The goal of the approach is to perform any critical operations like reading inputs, switching light, controlling sunscreens, etc.. inside the PLC itself and make use of MQTT events to send events to a MQTT broker. Using MQTT subscriptions it's possible to send commands to the PLC to switch outputs. 

The goal? One word: reduncancy!
- Plc's are very (very) robust controllers: no PC, SoC, etc.. is more robust and failure resistant. 
- Avoid performing critical operations that should work 24/7 inside a less redundant controller (it will fail sooner or later)
- Keep your wive/gf happy when you're not at home and your Rpi, Odroid, Banana Pi, Pc crashes (running your MQTT broker, OpenHab, Home Asistant etc..)

# Architecture
Core processing is executed in the (robust) PLC. Meaning that events like reading pushbuttons/switches, updating outputs is executed in the PLC logic. To enable integration with external software the PLC sends out events to a MQTT broker when events occur (like pushbutton events, outputs that change states). MQTT subscriptions are enabled as well to allow control from the outside to control outputs (for example).

![GeneralArchitecture](./docs/_img/HomeAutomation.GeneralArchitecture.svg)

# Software Architecture

More information on the software architecture [here](./docs/SoftwareArchitecture.md).

# Function blocks

- [FB_INPUT_PUSHBUTTON_MQTT](./docs/FunctionBlocks/FB_INPUT_PUSHBUTTON_MQTT.md)
- [FB_OUTPUT_SWITCH_MQTT](./docs/FunctionBlocks/FB_OUTPUT_SWITCH_MQTT.md)

# Additional functionality

- [MQTT Birth and Last will message](./docs/MQTT_Birth_and_Last_will_message.md)

# Libraries

The following libaries are used in this PLC project and can be found under `src\Libraries`:
- CommonTypesAndFunctions ([stefandreyer/CODESYS-Common](https://github.com/stefandreyer/CODESYS-Common))
- MQTT ([stefandreyer/CODESYS-MQTT](https://github.com/stefandreyer/CODESYS-MQTT))
- OSCAT NETWORK ([link](https://store.codesys.com/oscat-building.html))
- OSCAT BASIC ([link](https://store.codesys.com/oscat-basic.html))
- OSCAT BUILDING ([link](https://store.codesys.com/oscat-network.html))

Special thanks to StefanDreyer for his assistance in some of the MQTT aspects of this project and his great work on his open source CodeSys MQTT libraries.


