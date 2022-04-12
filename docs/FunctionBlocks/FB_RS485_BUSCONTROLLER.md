## FB_RS485_BUSCONTROLLER

### __General__
Used to control the RS485 bus in order to allow only one device with one Modbus RTU query at the time. In addition it manages the silence time on the bus between two requests and is capable of introducing a startup delay to allow devices on the bus to start up on power cycles.

### __Block diagram__

<img src="../_img/FB_RS485_BUSCONTROLLER.svg" width="350">

OUTPUT(S):
- BusOcupied: datatype bool, indicates whether the RS485 bus is occupied or not.

METHOD(S)
- Init: configures the buscontroller, an overview of the parameters: 
    - `StartupDelay`: datatype *TIME*, amount of time that should be waited on PLC startup before using the RS485 bus, can prevent errors due to RS485 devices not booted up yet.
    - `SilenceTime`: datatype *TIME*,  the silence time between two requests. Typically 10-20ms.
	- `BusTrigger`: datatype *POINTER TO BOOL*,  boolean controlling bus actions.
	- `BusData`: datatype *POINTER TO ARRAY [0..124] OF WORD*,  array containing bus read data.
	- `BusError`: datatype *POINTER TO BOOL*,  boolean indicating bus error.
- SetBusOccupied: used internally to set the RS485 bus as occupied.
- ReleaseBus: used internally to release the RS485 bus.

### __Code example__

- variables initiation:
```
RS485BusController 	: FB_RS485_BUSCONTROLLER;
```

- Init  method call -é!COCKPIT version- (called once during startup):
```
RS485BusController.Init(
	StartupDelay := T#5S,				(* Time to wait after startup to start using the bus, prevents boot delay issues when RS485 are not ready yet on startup *)		
	SilenceTime := T#50MS,				(* Silence time between two requests, important to not get faulty data on bus *)
	BusTrigger := ADR(Trigger),			(* Pointer to the bool used to initiate bus requests *)
	BusData := ADR(RtuResponse.awData),	(* Pointer to the array containing the bus response data *)
	BusError := ADR(ModbusMaster.xError)(* Pointer to the bus error bool *)
);
```

- Init  method call -Codesys 3S version- (called once during startup):
```
RS485BusController.Init(
	StartupDelay := T#5S,				(* Time to wait after startup to start using the bus, prevents boot delay issues when RS485 are not ready yet on startup *)		
	SilenceTime := T#50MS,				(* Silence time between two requests, important to not get faulty data on bus *)
	BusTrigger := ADR(Trigger),			(* Pointer to the bool used to initiate bus requests *)
	BusData := ADR(awReadBuffer),		(* Pointer to the array containing the bus response data *)
	BusError := ADR(xComPortError)		(* Pointer to the bus error bool *)
);
```

- Adding a device to the bus (called once during startup):
```
RS485BusController.RegisterDevice(device := FB_RS485_EASTRON_SDM220_1);
```