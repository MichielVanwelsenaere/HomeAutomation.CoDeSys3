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
| CODESYS license cost | ~89 EUR ([CODESYS Store](https://store.codesys.com/en/codesys-control-basic-l-bundle.html)) | Free |
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

G1 devices do **not** ship with a built-in CODESYS runtime license. To run CODESYS programs, you must separately purchase and install the **CODESYS Control for WAGO Touch Panel SL** runtime package, available from the [CODESYS Store](https://store.codesys.com/en/codesys-control-basic-l-bundle.html). Without this license, the device will not execute any CODESYS application.

The installation is done via the WAGO Web-Based Management (WBM) interface. The following YouTube video walks through the full installation process:

> [CODESYS Control for WAGO – Installation Guide (YouTube)](https://www.youtube.com/watch?v=-uLj3F2xtSU)

The **installation tool** can be found under 'Tools / Deploy Control SL'. This has changed since the video was created.

**Default credentials** for the SSH access used to install Control SL are:

| | |
|---|---|
| Username | `root` |
| Password | `wago` |

Note that the regular 'admin' user does not have sufficient rights.
