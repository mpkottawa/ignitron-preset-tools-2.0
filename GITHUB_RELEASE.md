# Ignitron Preset Tools 2.0

IPT 2.0 is the streamlined desktop release for building Ignitron preset banks, installing the IPT 2.0 firmware support, flashing firmware/filesystem data, controlling presets live from the PC, backing up pedal presets, and capturing presets from the Spark app.

## Downloads

### Windows

Download:

```text
Ignitron Preset Tools v2.0.zip
```

Unzip it and run:

```text
Ignitron Preset Tools v2.0.exe
```

The Windows EXE is badged with `IPT.ico`.

### macOS

A macOS app must be built on macOS. The GitHub release includes a macOS ZIP built by the **Build macOS Release** workflow. The release source also includes:

```text
build_release_mac.sh
```

On a Mac:

```bash
python3 -m pip install -r requirements.txt
chmod +x build_release_mac.sh
./build_release_mac.sh
```

That creates:

```text
release/Ignitron Preset Tools v2.0.app
release/Ignitron Preset Tools v2.0 macOS
release/Ignitron Preset Tools v2.0-macOS.zip
```

The macOS ZIP contains the `.app`, README files, and a visible `ignitron firmware` folder at the top level.

Optional: convert `IPT.ico` to `IPT.icns` on macOS before running the script to give the `.app` a custom dock icon.

## Firmware Setup Is The Big Upgrade

IPT 2.0 checks your selected Ignitron firmware folder and tells you whether the required support is already installed.

Basic flow:

1. Open IPT 2.0.
2. Select your Ignitron firmware folder on the Dashboard.
3. If prompted, open **Firmware > IPT 2.0 Setup**.
4. Click **Install IPT 2.0 support**.
5. Go to **Firmware**.
6. Pick your environment/COM port.
7. Click **Build + Flash FW + FS**.

The main flash button writes settings to `platformio.ini`, builds firmware, uploads firmware, builds filesystem data, and uploads filesystem data.

## Included IPT 2.0 Features

- Preset Bank Builder with `PresetList.txt`, `PresetListUUIDs.txt`, and `PresetList.pdf` generation.
- One-button firmware plus filesystem flash workflow.
- Separate firmware-only upload and filesystem-only upload.
- PlatformIO terminal popup for flash, upload, and monitor tasks.
- Firmware setup checker/installer for IPT 2.0 support.
- Pedal Remote for live preset switching over USB.
- Spark hardware preset select/save controls.
- Spark 2 hardware bank detection.
- Spark 2 looper controls in Pedal Remote.
- Tuner display inside Pedal Remote when firmware reports tuner data.
- Spark Capture workspace with live app preset capture and connected-pedal active-bank/full-library backup.
- ESP32/Ignitron reference notes.

## Firmware Support Checked By IPT 2.0

- `SELECTPRESET` remote preset command.
- `SELECTHW` hardware preset command.
- `STOREHW` hardware preset save command.
- `LOOPER` Spark 2 looper command family.
- `TUNERSTREAM` tuner output.
- `HWINFO` hardware type/bank reporting.
- `LISTBANKS` and `LISTPRESETS` for pedal backup inside Spark Capture.
- `received from app:` preset stream for Spark Capture.

## Notes

- Firmware and filesystem upload require PlatformIO.
- Default upload speed is `460800` for reliability.
- App serial tools communicate at `115200`.
- Pedal Remote and Spark Capture (including pedal backup) require IPT-compatible firmware.
- The hardware preset preview experiment was moved out as a separate local prototype.
