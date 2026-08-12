## DMX via Art-Net

### **General**

DMX is a lighting protocol (an alternative to DALI). It is used in stage lighting. It can have multiple universes. A house typically needs only one universe, since it contains 512 channels. Each channel has 256 steps. Channels can be combined to get more fine-grained control.

### **Setup**

<ins>Global parameters</ins></br>
In `DMXVariables` you can set an IP. This depends on your topology. Multicast works if the PLC and Art-Net node share the subnet mask.

    // unicast: 10.1.1.4
    // multicast: 10.1.1.255
    // broadcast: 255.255.255.255

In `DMX_SEND` you can set the universe. `0` is not recommended for Art-Net, so the default is `1`.

### **Debug**

With Wireshark you can track your network. Art-Net/DMX has a dedicated parser.

<img src="../_img/Wireshark_artnet.png" alt="Wireshark_artnet" width="500"/>

If you work remotely you can SSH into a PLC to check the multicast (in this case `10.1.1.255`). Either use the command line below or pipe SSH directly into Wireshark:

```
ssh root@10.1.1.3 sudo tcpdump --dont-verify-checksums -i ethX2 -U -s0 -w - 'dst host 10.1.1.255' | "C:\Apps\Wireshark\Wireshark.exe" -k -i -
```
