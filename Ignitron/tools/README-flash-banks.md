# Ignitron USB Bank Flasher

This tool uploads bank files and preset JSON files to the ESP32 LittleFS over USB serial. It is meant to replace the repeated "build filesystem image + uploadfs" workflow after the pedal has been flashed once with firmware that supports the USB flasher commands.

## One-time firmware step

Build and flash the updated firmware in this repo once. After that, the pedal understands these serial commands:

- `PING`
- `FSINFO`
- `LISTFILES`
- `LISTPRESETS`
- `LISTBANKS`
- `PUTBEGIN`
- `PUTB64`
- `PUTEND`
- `PUTABORT`
- `DELETE`
- `RESTART`

## PC setup

Install Python serial support:

```powershell
python -m pip install pyserial
```

## Upload banks

From the project root:

```powershell
python tools\flash_banks.py --port COM6 --restart
```

If you omit `--port`, the script lists detected serial ports and asks which one to use.

By default, the script uploads:

1. Every `.json` preset referenced by `data\PresetList.txt`
2. `data\PresetListUUIDs.txt`
3. `data\PresetList.txt`

The bank list is uploaded last so an interrupted transfer is less likely to leave the pedal pointing at files that are not there yet.

## Useful checks

Validate without touching the pedal:

```powershell
python tools\flash_banks.py --dry-run
```

Upload every `.json` in `data`, regardless of whether `PresetList.txt` references it:

```powershell
python tools\flash_banks.py --port COM6 --all-json --restart
```

## Important

`PresetList.txt` must reference files that actually exist in `data`. The script intentionally stops if bank slots point at missing preset files, because those slots would load as empty presets on the pedal.

At the time this tool was added, this repo's `data\PresetList.txt` referenced many files that were not present in the local `data` folder. Either restore the missing preset library files, regenerate the bank list with the picker, or use a `data` folder whose list and JSON files match.
