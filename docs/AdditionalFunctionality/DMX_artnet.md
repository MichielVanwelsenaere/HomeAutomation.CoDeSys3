## DMX via Art-Net

### **General**

DMX is a lighting protocol (an alternative to DALI). It is used in stage lighting. It can have multiple universes. A house typically needs only one universe, since it contains 512 channels. Each channel has 256 steps. Channels can be combined to get more fine-grained control.

### **Setup**

#### **Global parameters**
In `GVL_DMX` you can set an IP. This depends on your topology. Multicast works if the PLC and Art-Net node share the subnet mask.

    // unicast: 10.1.1.4
    // multicast: 10.1.1.255
    // broadcast: 255.255.255.255

In `PRG_DMX_SEND` you can set the universe. `0` is not recommended for Art-Net, so the default is `1`.

#### **Channel numbering**
`DmxChannel` is the channel the fixture is addressed to, 1 to 512, and it is the
channel that lights. Anything outside that range is refused by `initDMX` and the
block stays dormant.

#### **Metadata-only inputs**
`initDMX` also takes `DmxWidth` and `DmxUniverse`. Both are published in the Home
Assistant discovery config, and **neither changes what is transmitted**:

| Input | Effect |
|:--|:--|
| `DmxWidth` | none. One byte is written, at `DmxChannel`, so an RGB fixture gets one channel rather than three. |
| `DmxUniverse` | none. Every block transmits on the single universe set in `PRG_DMX_SEND`, so declaring 2 here still sends on that one. |

Set them to describe the fixture; do not expect them to drive it.

### **Debug**

With Wireshark you can track your network. Art-Net/DMX has a dedicated parser.

<img src="../_img/Wireshark_artnet.png" alt="Wireshark_artnet" width="500"/>

If you work remotely you can SSH into a PLC to check the multicast (in this case `10.1.1.255`). Either use the command line below or pipe SSH directly into Wireshark:

```
ssh root@10.1.1.3 sudo tcpdump --dont-verify-checksums -i ethX2 -U -s0 -w - 'dst host 10.1.1.255' | "C:\Apps\Wireshark\Wireshark.exe" -k -i -
```
