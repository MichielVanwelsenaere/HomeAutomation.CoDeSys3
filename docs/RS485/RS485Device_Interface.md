## RS485 Device Interface

The RS485Device interface is a simple interface designed to guarantee the presence of several methods with a correct input and output type so the RS485 function block can be used in both e!COCKPIT and CODESYS 3S.

The interface defines three methods:
1. RequestBusTime: Should check whether RS485 is initialized and whether the function block requires the bus for executing a Modbus command.

1. GetRtuQuery: Should return an RTU query to execute depending on the state of the interval timer(s). In case there are multiple Modbus RTU queries to be executed for a device the FB should keep track of the active RTU query.

1. ProcessDataArray: Should process the result returned by the RTU query returned by method 'GetRtuQuery'. In case there are multiple Modbus RTU queries to be executed for a device the correct one should be processed. 

