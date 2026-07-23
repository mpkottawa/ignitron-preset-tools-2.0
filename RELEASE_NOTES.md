# Ignitron Preset Tools v2.0

## Preview Split-Out

- Removed the Hardware Preset Preview page from IPT 2.0.
- Moved the hardware rendering experiment out as a standalone local prototype for loading a base/dry WAV, selecting bank presets through Ignitron, and caching Spark return audio.

## Firmware + Filesystem

- Merged filesystem upload controls into the Firmware section.
- The Firmware page now validates data, builds filesystem images, uploads filesystem data, and can still upload the filesystem after firmware flashing.
- Removed the separate Upload FS entry from the sidebar and dashboard to keep the release surface cleaner.

## Pedal Remote

- Moved tuner display into Pedal Remote.
- Removed the separate Tuner entry from the sidebar and dashboard.
- Removed the live display mirror from Pedal Remote.
- Removed the separate Display Mirror entry from the sidebar and dashboard.
- Firmware can still stream raw OLED framebuffer data as `OLED_HEX`, but Pedal Remote now stays focused on preset switching and tuner readout.
- Added Spark hardware preset buttons for HW bank 1 and HW bank 2, four slots each.
- Added a dedicated Pedal Remote hardware indicator showing connected amp type and reported HW bank count.
- Added a one-shot save option that writes the current amp preset to the clicked Spark hardware slot.
- Added a Spark 2 looper panel inside Pedal Remote with live rec/dub, play/stop, undo/redo, retry, delete, exit, status, and bar/beat visualization.
- Looper controls now open from an Enter Looper button or automatically when firmware reports looper mode after holding preset 4. Transport commands also enter looper mode before sending Spark 2 looper actions.

## Spark Capture

- Merged the separate Pedal Puller into the Spark Capture workspace.
- Added **Pull active bank** and **Pull full library** buttons for saving connected-pedal presets to timestamped backup folders.
- Kept live Spark app capture in the same page, with one shared USB-port selector and safe single-task serial handling.

Release date: 2026-07-06

## Highlights

- Copied forward the v1.1.1 desktop app, helper scripts, data settings, and reference materials.
- Updated the application to v2.0 branding and a v2.0 entry point.
- Added safer Preset Builder exports with automatic backups for generated list/PDF files.
- Reworked duplicate UUID cleanup so duplicate files are moved to a timestamped backup folder instead of deleted.
- Expanded persistent settings so project and preset library folders can both be remembered.
- Added tuner display support, now surfaced inside Pedal Remote as the live control view.
- Added OLED mirror firmware support, then removed the mirror from Pedal Remote for a cleaner control tab.
- Added a Pedal Remote serial tab for clicking the PresetList bank grid and changing the connected amp through Ignitron.
- Added automatic serial handoff: starting a serial tool stops the previous serial tool without asking for confirmation.
- Added firmware-side `SELECTPRESET bank preset`, `SELECTHW hardware-bank preset`, `STOREHW hardware-bank preset`, `LOOPER ...`, `MIRROR ON/OFF`, and `TUNERSTREAM ON/OFF` serial commands in the bundled working firmware folder.
- Added app discovery for an `Ignitron` firmware folder beside the v2.0 tools.
- Added a launcher, README, requirements file, and a release build script.
- Windows release downloads now expose the bundled firmware as a root-level `ignitron firmware` folder beside the EXE instead of burying it in `_internal`.

## Upgrade Notes

- Existing v1.1.1 generated build/release artifacts were not copied into the v2.0 workspace.
- The app prefers an `Ignitron` firmware folder beside the IPT 2.0 app/source folder when it looks like a PlatformIO project.
- Duplicate cleanup backup folders are created inside the selected preset library as `_ipt_duplicate_backups`.
- Preset Builder export backups are created inside the selected data/output folder as `_ipt_backups`.
