## HVAC Getting Started

### **General**

This guide aims to get you acquainted with the principles applied in the HVAC function blocks and how they are designed to work together. An implementation of scenario C can be found in the project under program `PLC_PRG_HVAC`. 

### **Scenario A: Floorheating**

This scenario assumes a single floorheating system with one thermostat and one pump. To control this system the following logical components are required:
- a thermostat that measures the temperature in the room and allows setting the desired temperature.
- a pump that controls the flow of water through the floorheating circuit.
- a heatsource that produces warm water when the pump is on.

<img src="../_img/HVAC_Getting_Started_Guide-ScenarioA.svg" width="1000">


### **Scenario B: 2 Floorheating circuits**

Building upon scenario A, consider a scenario where there not one floorheating circuit but two. In a real life situation this could for example be the floorheating on the first floor and the floorheating on the second floor. Each with their own thermostat.

<img src="../_img/HVAC_Getting_Started_Guide-ScenarioB.svg" width="1000">

### **Scenario C: 1 Floorheating circuit and 2 radiators on the same collector**

Not all buildings leverage floorheatin in every single room. In many setups radiators are used to heat multiple rooms in a building. This scenario treats such an example and assumes a thermostat in every room heated by a radiator:

---

:information_source: Due to the lack of PID logic in the function blocks the target temperature will always overshoot. This is only the case for radiators and not floorheating as they generate heat much faster.

---

<img src="../_img/HVAC_Getting_Started_Guide-ScenarioC.svg" width="1000">