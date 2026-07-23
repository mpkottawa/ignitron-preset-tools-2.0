#!/usr/bin/env python3
"""Upload Ignitron bank files and presets to the ESP32 over USB serial.

This requires firmware with the Ignitron USB preset flasher commands:
PING, FSINFO, PUTBEGIN, PUTB64, PUTEND, LISTFILES, and RESTART.
"""

from __future__ import annotations

import argparse
import base64
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:
    raise SystemExit(
        "pyserial is required. Install it with: python -m pip install pyserial"
    ) from exc


BAUD = 115200
CHUNK_SIZE = 192


class IgnitronSerial:
    def __init__(self, port: str, baud: int = BAUD, timeout: float = 8.0) -> None:
        self.ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=timeout)
        time.sleep(2.0)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        self.ser.close()

    def command(self, line: str, *, expect_prefix: str | None = "OK") -> str:
        self.ser.write((line + "\n").encode("utf-8"))
        self.ser.flush()
        while True:
            raw = self.ser.readline()
            if not raw:
                raise TimeoutError(f"Timed out waiting for response to: {line}")
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            if text.startswith("Initializing") or text.startswith("======="):
                continue
            if text.startswith("ERR"):
                raise RuntimeError(text)
            if expect_prefix is None or text.startswith(expect_prefix):
                return text

    def ping(self) -> str:
        self.ser.write(b"PING\n")
        self.ser.flush()
        deadline = time.time() + 10
        while time.time() < deadline:
            raw = self.ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if text == "IGNITRON_FLASHER 1":
                return text
        raise TimeoutError("No Ignitron flasher response. Is the new firmware running?")

    def fsinfo(self) -> str:
        return self.command("FSINFO", expect_prefix="FSINFO")

    def upload(self, filename: str, data: bytes, *, dry_run: bool = False) -> None:
        checksum = additive_checksum(data)
        print(f"  {filename}: {len(data)} bytes, checksum {checksum:08x}")
        if dry_run:
            return

        self.command(f"PUTBEGIN {filename} {len(data)} {checksum:08x}")
        for offset in range(0, len(data), CHUNK_SIZE):
            chunk = data[offset : offset + CHUNK_SIZE]
            encoded = base64.b64encode(chunk).decode("ascii")
            self.command(f"PUTB64 {encoded}")
        self.command("PUTEND")

    def restart(self) -> None:
        self.command("RESTART")


def additive_checksum(data: bytes) -> int:
    return sum(data) & 0xFFFFFFFF


def parse_preset_list(preset_list_path: Path) -> list[str]:
    names: list[str] = []
    for raw_line in preset_list_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("--"):
            continue
        names.append(line.split()[0])
    return names


def validate_filename(name: str) -> None:
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"Unsafe filename: {name!r}")
    if any(ch.isspace() for ch in name):
        raise ValueError(
            f"Filename contains whitespace and cannot be sent by this protocol: {name!r}"
        )


def collect_files(data_dir: Path, include_all_json: bool) -> list[Path]:
    preset_list = data_dir / "PresetList.txt"
    preset_uuid_list = data_dir / "PresetListUUIDs.txt"

    if not preset_list.exists():
        raise FileNotFoundError(f"Missing {preset_list}")
    if not preset_uuid_list.exists():
        raise FileNotFoundError(f"Missing {preset_uuid_list}")

    if include_all_json:
        preset_names = sorted(path.name for path in data_dir.glob("*.json"))
    else:
        preset_names = parse_preset_list(preset_list)

    missing: list[str] = []
    files: list[Path] = []
    seen: set[str] = set()

    for name in preset_names:
        validate_filename(name)
        if name in seen:
            continue
        seen.add(name)
        path = data_dir / name
        if not path.exists():
            missing.append(name)
        else:
            files.append(path)

    if missing:
        preview = "\n".join(f"  - {name}" for name in missing[:25])
        suffix = "" if len(missing) <= 25 else f"\n  ...and {len(missing) - 25} more"
        raise FileNotFoundError(
            "PresetList.txt references files that are missing from data:\n"
            f"{preview}{suffix}"
        )

    files.extend([preset_uuid_list, preset_list])
    return files


def choose_port() -> str:
    ports = list(list_ports.comports())
    if not ports:
        raise SystemExit("No serial ports found. Connect the ESP32 over USB and try again.")
    print("Serial ports:")
    for idx, port in enumerate(ports, start=1):
        desc = f"{port.description}" if port.description else ""
        print(f"  {idx}. {port.device} {desc}")
    while True:
        choice = input("Port number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Enter a valid port number.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flash Ignitron preset banks over USB serial.")
    parser.add_argument("--data", default="data", help="Path to Ignitron data folder.")
    parser.add_argument("--port", help="Serial port, for example COM6.")
    parser.add_argument("--baud", type=int, default=BAUD, help="Serial baud rate.")
    parser.add_argument(
        "--all-json",
        action="store_true",
        help="Upload every .json in data instead of only presets referenced by PresetList.txt.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and print what would upload.")
    parser.add_argument("--restart", action="store_true", help="Restart the ESP32 after upload.")
    args = parser.parse_args(argv)

    data_dir = Path(args.data).resolve()
    files = collect_files(data_dir, args.all_json)

    print(f"Data folder: {data_dir}")
    print(f"Files to upload: {len(files)}")
    for path in files:
        validate_filename(path.name)

    if args.dry_run:
        for path in files:
            print(f"  {path.name}: {path.stat().st_size} bytes")
        return 0

    port = args.port or choose_port()
    device = IgnitronSerial(port, baud=args.baud)
    try:
        print(f"Connected: {device.ping()}")
        print(device.fsinfo())
        print("Uploading:")
        for path in files:
            device.upload(path.name, path.read_bytes())
        print(device.fsinfo())
        if args.restart:
            print("Restarting pedal...")
            device.restart()
    finally:
        device.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
