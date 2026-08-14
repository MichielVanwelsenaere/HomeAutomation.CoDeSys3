## FB_RS485_BUSCONTROLLER
<!-- fb-badge:start -->
<!-- fb-badge:end -->

### **General**
Used to control the RS485 bus in order to allow only one device with one Modbus RTU query at a time. In addition it manages the silence time on the bus between two requests and is capable of introducing a startup delay to allow devices on the bus to start up on power cycles.

----------------------------

:rotating_light: **Untested since the CODESYS conversion.** The RS485 chain has not yet been run against real hardware on a CODESYS runtime — see [Using Modbus RTU with the CODESYS 3S runtime](../RS485/UsingModbusRTU_CODESYS3S.md).

----------------------------

<!-- fb-interface:start -->
### **Block diagram**

```text
   ┌────────────────────────┐
   │ FB_RS485_BUSCONTROLLER │
   ├────────────────────────┤
   │             BusOcupied ├── BOOL
   └────────────────────────┘
```

### **Interface**

**Outputs**

| Pin | Type | Description |
|:--|:--|:--|
| `BusOcupied` | BOOL | Datatype bool, indicates whether the RS485 bus is occupied or not. |

### **Methods**

**`Init`** — Configures the bus controller, an overview of the parameters:

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `StartupDelay` | TIME |  | Amount of time that should be waited on PLC startup before using the RS485 bus, can prevent errors due to RS485 devices not having booted up yet. |
| `FailSafeTimeout` | TIME | `TIME#10s0ms` | How long a device may hold the bus before it is taken back. A device that stops answering mid-query would otherwise keep the bus occupied forever and stall every other device on it; when this expires the controller processes what arrived and releases the bus. |
| `SilenceTime` | TIME |  | The silence time between two requests. Typically 10-20ms. |
| `BusTrigger` | POINTER TO BOOL |  | Boolean controlling bus actions. |
| `BusData` | POINTER TO ARRAY [0..124] OF WORD |  | Array containing bus read data. |
| `BusError` | POINTER TO BOOL |  | Boolean indicating bus error. |

**`RegisterDevice`** — Registers an RS485 device function block with the bus controller. Call once at startup for each device on the bus.

| Parameter | Type | Default | Description |
|:--|:--|:--|:--|
| `device` | RS485Device |  | The RS485 device function block to register. |

**`ReleaseBus`** — Used internally to release the RS485 bus.

**`SetBusOccupied`** — Used internally to set the RS485 bus as occupied.
<!-- fb-interface:end -->

### **Code example**

- variables initiation:
```
RS485BusController 	: FB_RS485_BUSCONTROLLER;
```

- Init method call -e!COCKPIT version- (called once during startup):
```
RS485BusController.Init(
	StartupDelay := T#5S,				(* Time to wait after startup to start using the bus, prevents boot delay issues when RS485 are not ready yet on startup *)		
	SilenceTime := T#50MS,				(* Silence time between two requests, important to not get faulty data on bus *)
	BusTrigger := ADR(Trigger),			(* Pointer to the bool used to initiate bus requests *)
	BusData := ADR(RtuResponse.awData),	(* Pointer to the array containing the bus response data *)
	BusError := ADR(ModbusMaster.xError)(* Pointer to the bus error bool *)
);
```

- Init method call -CODESYS 3S version- (called once during startup):
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
