# Ignitron Preset Tools 2.0

Ignitron Preset Tools 2.0 is a Windows desktop app for building Ignitron preset banks, flashing firmware, uploading the data filesystem, remotely changing presets on a connected Spark amp rig, backing up pedal presets, and capturing presets sent from the Spark app.

The big goal for 2.0 is less fiddling: choose your firmware folder, install the IPT 2.0 firmware support with a couple clicks, then use one main button to build and flash firmware plus filesystem data.

## What You Need

- Windows 10/11.
- An Ignitron pedal connected by USB.
- PlatformIO installed if you want to build/flash firmware from source.
- A Spark amp connected to Ignitron for remote preset control, capture, hardware preset control, or Spark 2 looper features.
- The bundled `ignitron firmware` folder in the release download, or your own Ignitron firmware folder.

## Quick Start

### Option A: Run The App

If you downloaded the release build, run:

```text
Ignitron Preset Tools v2.0.exe
```

If you are running from source, run:

```powershell
Run IPT 2.0.bat
```

or:

```powershell
py -3 ignitron_preset_tools_v2.0.py
```

### Option B: Install Python Requirements

Only needed when running from source:

```powershell
py -3 -m pip install -r requirements.txt
```

## First-Time Firmware Setup

1. Open IPT 2.0. windows will probably open  Windows protected your PC.  click more info, and run anyways.(it will only ask on first run)
2. On the Dashboard, select your Ignitron PlatformIO firmware folder.
3. If IPT says the firmware support is missing, click the link to open **Firmware > IPT 2.0 Setup**.
4. Click **Install IPT 2.0 support**.
5. Go to **Firmware**.
6. Choose the PlatformIO environment and COM port.
7. Click **Build + Flash FW + FS**.

That main button saves the selected firmware settings, writes the selected PlatformIO environment/port/speed to `platformio.ini`, optionally cleans/erases, uploads firmware, builds the filesystem, and uploads the filesystem.

The reliable default flashing speed is `460800`. The app keeps serial control features at `115200`.

## Main Sections

### Preset Builder

Use this to build the pedal bank layout from JSON preset files.

- Load the selected Ignitron `data` folder.
- Drag or double-click presets into bank slots.
- Set the number of banks.
- Click **Save setup for flash** to write the current layout to the selected firmware project's `data` folder.
- Click **Open PresetList PDF** when you want to view the generated setlist PDF.

If the builder has filled slots, the Firmware page automatically saves that setup before flashing or uploading filesystem data. In other words: what you see in the builder is what gets uploaded.

### Firmware

This is the one-stop firmware and filesystem page.

- **Build + Flash FW + FS**: full release workflow for the pedal.
- **Upload firmware to this pedal**: uploads firmware to the selected COM port without uploading filesystem data.
- **Build + Upload FS Only**: updates only presets/filesystem data.
- **Terminal**: opens the PlatformIO output window. Flash, filesystem upload, firmware upload, and monitor tasks open it automatically.
- **IPT 2.0 Setup**: checks or installs the firmware serial support needed by IPT 2.0.
- **Open PresetList PDF**: opens the current `data/PresetList.pdf` manually.

The IPT 2.0 setup checker verifies support for:

- Remote preset selection.
- Spark hardware preset select/save.
- Spark 2 looper commands.
- Tuner stream hooks.
- Spark Capture pedal-backup `LISTBANKS` and `LISTPRESETS` commands.
- Spark Capture preset streaming.
- App status events.

### Pedal Remote

Use this while Ignitron is connected by USB and connected to the Spark amp.

- Click presets from the on-screen bank grid.
- See the currently selected preset.
- Watch bank changes flash while the pedal changes banks.
- Use Spark hardware preset slots.
- Save the current amp preset to a clicked hardware slot.
- See connected hardware type.
- Use Spark 2 looper mode when a Spark 2 is detected.
- Show tuner readings automatically when the pedal enters tuner mode.

Starting another serial tool automatically closes the previous serial connection. No extra confirmation click is required.

### Spark Capture

Spark Capture combines live Spark app capture and connected-pedal backup in one workspace.

- Connect Ignitron to USB.
- For live capture, keep Ignitron connected to the Spark app over Bluetooth and send presets from the app. IPT saves each unique JSON preset automatically.
- Use **Pull active bank** to save the presets referenced by the pedal's active `PresetList.txt`.
- Use **Pull full library** to save every preset stored on the pedal.
- Pedal backups are saved as JSON in a timestamped folder under `backups`.

This requires IPT-compatible firmware support.

### Reference

Includes ESP32/Ignitron wiring references, firmware notes, and pin guidance.

## Standalone Spark Preset Preview

The hardware preset preview experiment was moved out of IPT 2.0 into a separate local prototype.
That keeps IPT 2.0 focused and stable for release.

## Building A Release

From the source folder:

```powershell
py -3 -m pip install -r requirements.txt
.\build_release.ps1
```

The build script creates:

```text
release\Ignitron Preset Tools v2.0
release\Ignitron Preset Tools v2.0.zip
```

The EXE uses `IPT.ico` as its Windows icon/badge.

### Building A Mac Release

macOS apps must be built on macOS. From a Mac terminal in this project folder:

```bash
python3 -m pip install -r requirements.txt
chmod +x build_release_mac.sh
./build_release_mac.sh
```

The Mac build script creates:

```text
release/Ignitron Preset Tools v2.0.app
release/Ignitron Preset Tools v2.0-macOS.zip
```

If you want a custom macOS dock icon, convert `IPT.ico` to `IPT.icns` on the Mac and place `IPT.icns` beside the script before running it. The Windows EXE always uses `IPT.ico`.

## Files Included

- `ignitron_preset_tools_v2.0.py` - main desktop app.
- `Run IPT 2.0.bat` - source launcher.
- `build_release.ps1` - PyInstaller release builder.
- `build_release_mac.sh` - macOS PyInstaller release builder, to be run on a Mac.
- `IPT.ico` - app icon.
- `ignitron firmware\` - bundled IPT 2.0-ready firmware in the release download.
- `Ignitron\` - bundled IPT 2.0-ready firmware source folder when running from this repository.
- `data\` - preset data folder used by the app.
- `reference\` - reference docs/assets.
- `preset_puller.py`, `preset_chart.py`, `preset_converter.py`, `preset_app_scraper.py` - helper tools.
- `requirements.txt` - Python dependencies for source use.

## Notes

- Filesystem upload changes the pedal's preset/data files; it does not change firmware code.
- Firmware flash changes the ESP32 firmware.
- Pedal Remote and Spark Capture (including pedal backup) need IPT-compatible firmware support.
- Spark 2 looper controls appear only when firmware reports a Spark 2/two hardware-bank amp.
- If upload at `921600` is unreliable, use the default `460800`.

## Repository

```text
https://github.com/mpkottawa/ignitron-preset-tools-2.0
```
