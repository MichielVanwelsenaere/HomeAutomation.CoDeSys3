# Wago PFC devices

## Table of Contents

- [Generations](#generations)
  - [Identifying your generation by model number](#identifying-your-generation-by-model-number)
  - [Feature comparison](#feature-comparison)
- [Device preparation](#device-preparation)
  - [G1](#g1)
  - [G2](#g2)
  - [Flashing via SD card](#flashing-via-sd-card)
  - [Install CODESYS Control SL (G1 only)](#install-codesys-control-sl-g1-only)
  - [Activating the license (G1 only)](#activating-the-license-g1-only)

## Generations

### Identifying your generation by model number

The generation of a WAGO PFC100 or PFC200 device can be identified by its article number (found on the device label):

| Device | G1 article numbers | G2 article numbers |
|--------|-------------------|-------------------|
| PFC100 | 750-8101 | 750-8112 |
| PFC200 | 750-8202 | 750-8212 |

As a general rule: lower-numbered variants within a series are G1, while higher-numbered variants with extended feature sets (Docker, built-in CODESYS license) are G2.

### Feature comparison

| Feature | G1 | G2 |
|---------|----|----|  
| WAGO official support | No (end-of-life) | Yes |
| CODESYS support | Yes | Yes |
| CODESYS license required | Yes | No (included with device) |
| CODESYS license cost | Depends on the license tier, which is driven by your I/O count (see [Install CODESYS Control SL](#install-codesys-control-sl-g1-only)) | Free |
| Docker containers | No | Yes |
| WAGO libraries (e.g. DALI) | No | Yes |

## Device preparation

Firmware updates for both G1 and G2 devices can be performed using the [WAGO Upload tool](https://github.com/WAGO/wago-firmware-tools), **provided the device is already running firmware version 12 or above**.

If the device is running a firmware version below 12, the WAGO Upload tool cannot be used and the firmware must be flashed via SD card (see [Flashing via SD card](#flashing-via-sd-card) below).

### G1

Update the device to firmware version 22, which is the latest supported firmware for G1 devices.

**Using WAGO Upload (firmware >= 12):**

1. Download and install the [WAGO Upload tool](https://github.com/WAGO/wago-firmware-tools).
2. Download the G1 firmware version 22 image from the [WAGO firmware page](https://www.wago.com/global/automation-technology/discover-controller/software/firmware).
3. Open WAGO Upload, enter the device IP address, and browse to the downloaded firmware file.
4. Start the upload and wait for the device to reboot.
5. [Install CODESYS Control SL](#install-codesys-control-sl-g1-only)
6. [Activate the license](#activating-the-license-g1-only)

### G2

Update the device to the latest available firmware.

**Using WAGO Upload (firmware >= 12):**

1. Download and install the [WAGO Upload tool](https://github.com/WAGO/wago-firmware-tools).
2. Download the latest G2 firmware image from the [WAGO firmware page](https://www.wago.com/global/automation-technology/discover-controller/software/firmware).
3. Open WAGO Upload, enter the device IP address, and browse to the downloaded firmware file.
4. Start the upload and wait for the device to reboot.

### Flashing via SD card

If the current firmware version is below 12, use an SD card to flash the firmware:

1. Download the firmware image (`.zip` or `.img`) for your device from the [WAGO firmware page](https://www.wago.com/global/automation-technology/discover-controller/software/firmware).
1. Format an SD card as FAT32.
1. Extract and copy the firmware files to the root of the SD card.
1. Power off the PFC device.
1. Insert the SD card into the SD card slot on the PFC device.
1. Power on the device. The firmware on the SD card will be loaded automatically.
1. Open Web-Based Management at http://<device-ip> and go to Administration / Create Image / Create bootable image from active partition (SD) / Start Copy.
1. Once the update is complete, turn off the device, remove the SD card and reboot.
1. Verify the expected firmware version via the WBM (Web-Based Management) interface at `http://<device-ip>`.

### Install CODESYS Control SL (G1 only)

G1 devices do **not** ship with a built-in CODESYS runtime license. Without a license the runtime still starts, but it stops after 2 hours (see the [getting started guide](./FAQ/Getting_started_guide_CODESYS_3S.md)).

Two separate things are involved:

1. **The runtime package** — [CODESYS Control for PFC100 SL](https://store.codesys.com/en/codesys-control-for-pfc100-sl-1.html) or [CODESYS Control for PFC200 SL](https://store.codesys.com/en/codesys-control-for-pfc200-sl-1.html), matching your device. These are the same target packages installed in the getting started guide. The runtime itself is not licensed.
2. **An application license** on top of it, bought per device from the [CODESYS Store](https://store.codesys.com/).

#### Choosing a license tier

The tier is decided by **how many I/O channels you have**, not by which function blocks you use. The commonly used tiers differ only in that number:

| | Control Basic M | Control Basic L |
|---|---|---|
| I/O channels | 128 | 256 |
| Standard fieldbus instances (CANopen / Modbus / J1939) | 2 | 2 |
| Complex fieldbus instances | 1 | 1 |
| Visualization / Communication | S / S | S / S |
| Price (excl. VAT, at time of writing) | from 69 EUR | from 89 EUR |

Count the digital inputs and outputs across your modules. With 8-channel cards such as the 750-430 (8 DI) and 750-530 (8 DO), 128 channels is 16 modules and 256 is 32. For a whole house 128 is tight, since pushbuttons alone often run to 50-80.

Modbus RTU over RS485 does **not** push you to a higher tier: one RS485 master is a single standard fieldbus instance and both tiers allow two. MQTT and Art-Net/DMX use raw TCP/UDP sockets rather than fieldbus instances, so they do not count either.

Verify the current limits and prices in the store before buying — the figures above are a snapshot.

#### Installing the runtime package

The installation is done via the WAGO Web-Based Management (WBM) interface. The following YouTube video walks through the full installation process:

> [CODESYS Control for WAGO – Installation Guide (YouTube)](https://www.youtube.com/watch?v=-uLj3F2xtSU)

The **installation tool** can be found under 'Tools / Deploy Control SL'. This has changed since the video was created.

**Default credentials** for the SSH access used to install Control SL are:

| | |
|---|---|
| Username | `root` |
| Password | `wago` |

Note that the regular 'admin' user does not have sufficient rights.

### Activating the license (G1 only)

Installing the Control SL package puts the runtime on the device; it does **not** license it. Until the license is activated the runtime still stops after 2 hours.

CODESYS licensing is handled by WIBU Systems CodeMeter. A license always lives in a *container*, and there are two kinds:

| | Soft container | Dongle |
|---|---|---|
| What it is | A software container stored on the controller | A physical WIBU CodeMeter USB stick or SD variant |
| Bound to | That specific device | The dongle itself |
| Extra hardware cost | None | The dongle, on top of the license |
| Moving to other hardware | Deactivate on the old device first, then activate on the new one | Move the dongle |

For a PFC100/200 sitting permanently in a cabinet the **soft container** is the normal choice: no extra hardware, and the Control SL runtime supports it directly. A dongle is worth considering only if you expect to move the license between controllers.

**Activating a soft container (device with internet access):**

1. Buy the license from the [CODESYS Store](https://store.codesys.com/). You receive a **ticket ID** by email.
2. Open the project in CODESYS and connect to the PLC.
3. Open the License Manager (under *Tools*) and select your device.
4. Choose to activate a license and paste the ticket ID.
5. CODESYS contacts the licensing server and writes the license into a soft container on the device.
6. Restart the runtime and confirm the application no longer stops after 2 hours.

**Activating without internet access on the device:**

If the PLC or the engineering PC cannot reach the licensing server, the same License Manager offers a file-based exchange: export a license request file from the device, upload it from a machine that does have internet, then import the resulting response file back onto the device.

---

:rotating_light: A soft container is tied to the device it was activated on. **Deactivate the license before you replace, re-flash or decommission a controller** — deactivating returns it to the ticket so it can be activated again elsewhere. Reinstalling firmware without doing this first can strand the license. This matters here because the firmware steps earlier on this page are usually run *before* licensing.

---

Note that menu paths differ slightly between CODESYS versions, so treat the steps above as the general flow rather than exact clicks.
