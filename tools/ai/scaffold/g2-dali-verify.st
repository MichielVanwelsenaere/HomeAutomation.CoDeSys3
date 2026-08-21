// Run the master before anything else, bound to the 753-647 on this device's own
// K-bus. This binding is the whole point of the second controller: I_Port wants a
// WagoTypesModule_753_647.I_Port_753_647, which only WAGO's device description
// creates, and that description does not fit the G1 lab device's bus.
DaliMaster(
	bPortDALI := 1,
	I_Port := IoConfig_Globals.DALI_753_647);

// The block under test. No InitMqtt and no InitMqttDiscovery: this application
// never runs, and calling them would only invent a Home Assistant entity for a
// controller that does not exist.
fbDimmer(
	BALLAST := Ballast,
	TOGGLE := FALSE,
	P_LONG := FALSE);
