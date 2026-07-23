#!/usr/bin/env python3
"""Ignitron Preset Tools v2.0 - desktop control center."""

import contextlib
import importlib.util
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import wave
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


APP_NAME = "Ignitron Preset Tools"
APP_VERSION = "2.0"
DEFAULT_UPLOAD_SPEED = "460800"
APP_RELEASE_DATE = "2026-07-06"
APP_DESCRIPTION = "Preset building, firmware setup, filesystem upload, and serial capture tools."
IPT_ADDON_BASE_FILES = ("Ignitron.ino",)
IPT_ADDON_SRC_EXCLUDES = {"Config_Definitions.h.bak", "Readme.md"}
IPT_ADDON_MARKERS = (
    ("Ignitron.ino", "SELECTPRESET serial command", "SELECTPRESET <bank> <preset>"),
    ("Ignitron.ino", "Spark HW preset serial command", "STOREHW <hardware-bank> <preset>"),
    ("Ignitron.ino", "Spark 2 looper serial command", "LOOPER <ENTER|EXIT|MODE"),
    ("Ignitron.ino", "Hardware info report", "HWINFO banks="),
    ("Ignitron.ino", "Spark Capture pedal-backup bank list command", "LISTBANKS"),
    ("Ignitron.ino", "Spark Capture pedal-backup preset dump command", "LISTPRESETS"),
    ("src/SparkPresetControl.cpp", "Remote active preset event", "REMOTE_PRESET bank=%d preset=%d hwbank=%d"),
    ("src/SparkPresetControl.cpp", "Remote pending bank event", "REMOTE_BANK bank=%d hwbank=%d"),
    ("src/SparkPresetControl.cpp", "Spark Capture app preset stream", "received from app:"),
    ("src/SparkDataControl.cpp", "Hardware info event", "HWINFO banks=%d amp="),
    ("src/SparkDataControl.cpp", "Hardware preset store ack", "OK STOREHW"),
    ("src/SparkDataControl.cpp", "Looper mode event", "LOOPER_MODE active=%d submode=%d"),
    ("src/SparkMessage.cpp", "Spark hardware preset store message", "storeHardwarePreset"),
    ("src/SparkDataControl.h", "Spark HW store API", "storeHWPreset"),
)

BG = "#0d0e12"
SURFACE = "#15171d"
CARD = "#1c1f27"
CARD_ALT = "#232731"
BORDER = "#343946"
TEXT = "#f4f1ea"
MUTED = "#9ba1ad"
GOLD = "#f5a623"
GOLD_HOVER = "#ffbd4a"
ORANGE = "#e66a1f"
GREEN = "#37c878"
RED = "#e35050"
FIRMWARE_MOD_PAGES = {"firmware", "remote", "capture"}


def app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(name):
    roots = [app_dir(), app_dir().parent, Path(getattr(sys, "_MEIPASS", app_dir()))]
    for root in roots:
        candidate = root / name
        if candidate.exists():
            return candidate
    return roots[0] / name


def settings_file():
    return app_dir() / "data" / "settings.json"


def load_settings():
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_settings(**updates):
    data = load_settings()
    data.update({key: str(value) if isinstance(value, Path) else value for key, value in updates.items()})
    save_settings(data)


def load_saved_project_dir():
    try:
        data = load_settings()
        folder = Path(data.get("ignitron_folder", ""))
        if (folder / "data").exists():
            return folder
    except Exception:
        pass
    return default_project_dir()


def save_project_dir(folder):
    update_settings(ignitron_folder=folder)


def load_saved_path(key):
    value = load_settings().get(key, "")
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.exists() else None


def backup_file(path, backup_root):
    path = Path(path)
    if not path.exists():
        return None
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_root / f"{path.stem}_{stamp}{path.suffix}"
    counter = 1
    while backup_path.exists():
        backup_path = backup_root / f"{path.stem}_{stamp}_{counter}{path.suffix}"
        counter += 1
    shutil.copy2(path, backup_path)
    return backup_path


def open_folder(path):
    path = str(Path(path).resolve())
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def open_serial_no_reset(port, baud=115200, timeout=0.25):
    import serial

    connection = serial.Serial()
    connection.port = port
    connection.baudrate = baud
    connection.timeout = timeout
    connection.write_timeout = 1
    connection.rtscts = False
    connection.dsrdtr = False
    connection.dtr = False
    connection.rts = False
    connection.open()
    try:
        connection.setDTR(False)
        connection.setRTS(False)
        connection.reset_input_buffer()
        connection.reset_output_buffer()
    except Exception:
        pass
    return connection


def serial_port_text(port):
    parts = [
        getattr(port, "device", ""),
        getattr(port, "description", ""),
        getattr(port, "manufacturer", ""),
        getattr(port, "product", ""),
        getattr(port, "hwid", ""),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def serial_port_score(port):
    text = serial_port_text(port)
    score = 0
    if getattr(port, "vid", None) is not None and getattr(port, "pid", None) is not None:
        score += 8
    for needle, weight in (
        ("ignitron", 80),
        ("esp32", 40),
        ("silicon labs", 34),
        ("cp210", 34),
        ("ch340", 28),
        ("wch", 22),
        ("usb serial", 20),
        ("usb-to-uart", 20),
        ("uart", 14),
        ("serial converter", 14),
    ):
        if needle in text:
            score += weight
    if "bluetooth" in text:
        score -= 100
    if "com" in str(getattr(port, "device", "")).lower():
        score += 1
    return score


def format_serial_port(port):
    return f"{port.device}  |  {port.description}"


def list_serial_ports():
    import serial.tools.list_ports

    return list(serial.tools.list_ports.comports())


def best_serial_port(ports, preferred=""):
    if not ports:
        return None
    preferred_device = preferred.split("  |  ", 1)[0].strip().lower()

    def sort_key(port):
        preferred_bonus = 1000 if preferred_device and port.device.lower() == preferred_device else 0
        return preferred_bonus + serial_port_score(port)

    return max(ports, key=sort_key)


def probe_ignitron_port(port, timeout=0.9):
    connection = None
    try:
        connection = open_serial_no_reset(port.device, 115200, timeout=0.08)
        time.sleep(0.04)
        connection.write(b"PING\n")
        deadline = time.time() + timeout
        buffer = ""
        while time.time() < deadline:
            line = connection.readline().decode(errors="ignore").strip()
            if line:
                buffer += line + "\n"
                upper = line.upper()
                if "IGNITRON_FLASHER" in upper or "INITIALIZING" in upper:
                    return True
            time.sleep(0.02)
    except Exception:
        return False
    finally:
        try:
            if connection:
                connection.close()
        except Exception:
            pass
    return False


def auto_detect_ignitron_port(preferred=""):
    try:
        ports = list_serial_ports()
    except Exception:
        return None, []
    if not ports:
        return None, []

    preferred_device = preferred.split("  |  ", 1)[0].strip().lower()
    candidates = sorted(
        ports,
        key=lambda port: (1000 if preferred_device and port.device.lower() == preferred_device else 0) + serial_port_score(port),
        reverse=True,
    )
    likely = [port for port in candidates if serial_port_score(port) > 0]
    if not likely:
        likely = candidates[:1]

    for port in likely:
        if probe_ignitron_port(port):
            return port, ports
    return best_serial_port(ports), ports


def run_hidden_subprocess(cmd, cwd):
    kwargs = {
        "cwd": str(cwd),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "errors": "replace",
        "bufsize": 1,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
    return subprocess.Popen(cmd, **kwargs)


def default_project_dir():
    candidates = [
        app_dir() / "Ignitron",
        app_dir().parent / "Ignitron",
        app_dir().parent.parent / "Ignitron",
        Path(r"T:\ignitron"),
        app_dir().parent,
        app_dir(),
    ]
    for candidate in candidates:
        if (candidate / "platformio.ini").exists() and (candidate / "data").exists():
            return candidate
    return candidates[0]


def default_platformio():
    candidates = [
        Path.home() / ".platformio" / "penv" / "Scripts" / "platformio.exe",
        Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "platformio"


def parse_platformio_envs(platformio_ini):
    if not platformio_ini.exists():
        return ["esp32dev"]
    envs = []
    for line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\[env:([^\]]+)\]", line.strip())
        if match:
            envs.append(match.group(1))
    return envs or ["esp32dev"]


def parse_platformio_upload_port(platformio_ini, env_name):
    if not platformio_ini.exists():
        return ""
    current_section = ""
    inherited_port = ""
    env_port = ""
    for raw_line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key != "upload_port":
            continue
        if current_section == "env":
            inherited_port = value
        elif current_section == f"env:{env_name}":
            env_port = value
    return env_port or inherited_port


def parse_platformio_env_value(platformio_ini, env_name, option_name, fallback=""):
    if not platformio_ini.exists():
        return fallback
    current_section = ""
    inherited_value = ""
    env_value = ""
    for raw_line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key != option_name:
            continue
        if current_section == "env":
            inherited_value = value
        elif current_section == f"env:{env_name}":
            env_value = value
    return env_value or inherited_value or fallback


def inspect_ipt_addon_support(project_dir):
    project_dir = Path(project_dir).expanduser().resolve()
    missing_files = []
    missing_markers = []
    for rel_path, label, marker in IPT_ADDON_MARKERS:
        path = project_dir / rel_path
        if not path.exists():
            missing_files.append(rel_path)
            missing_markers.append((rel_path, label, marker))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            missing_markers.append((rel_path, label, marker))
    return missing_files, missing_markers


def ipt_addon_files(source_root):
    source_root = Path(source_root)
    files = list(IPT_ADDON_BASE_FILES)
    src_dir = source_root / "src"
    if src_dir.exists():
        for path in sorted(src_dir.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and path.suffix.lower() in (".cpp", ".h") and path.name not in IPT_ADDON_SRC_EXCLUDES:
                files.append(str(path.relative_to(source_root)).replace("\\", "/"))
    return tuple(files)


def preset_list_missing_files(data_dir):
    preset_list = data_dir / "PresetList.txt"
    if not preset_list.exists():
        return ["PresetList.txt is missing"]
    missing = []
    for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
        name = raw_line.strip()
        if not name or name.startswith("--"):
            continue
        if not (data_dir / name).exists():
            missing.append(name)
    return missing


def generate_preset_chart(data_dir):
    def write_simple_pdf(output_path, rows):
        def pdf_escape(value):
            return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        lines = ["BT", "/F1 18 Tf", "50 750 Td", "(Ignitron Preset Chart) Tj", "/F1 8 Tf", "0 -24 Td"]
        for row in rows:
            text = "   |   ".join(row)
            lines.append(f"({pdf_escape(text)}) Tj")
            lines.append("0 -14 Td")
        lines.append("ET")
        stream = "\n".join(lines).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        content = bytearray(b"%PDF-1.4\n")
        offsets = []
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(content))
            content.extend(f"{index} 0 obj\n".encode("ascii"))
            content.extend(obj)
            content.extend(b"\nendobj\n")
        xref = len(content)
        content.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        for offset in offsets:
            content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        content.extend(
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        )
        output_path.write_bytes(content)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        colors = letter = getSampleStyleSheet = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None

    data_dir = Path(data_dir)
    preset_list = data_dir / "PresetList.txt"
    output_path = data_dir / "PresetList.pdf"
    if not preset_list.exists():
        raise FileNotFoundError(f"PresetList.txt was not found at {preset_list}")

    banks = []
    current_bank = None
    for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-- Bank"):
            current_bank = [line.replace("--", "").strip(), []]
            banks.append(current_bank)
            continue
        if current_bank is None:
            current_bank = ["Bank 1", []]
            banks.append(current_bank)
        preset_name = Path(line).stem.replace("_", " ")
        current_bank[1].append(preset_name)

    table_data = [["Bank", "Slot 1", "Slot 2", "Slot 3", "Slot 4"]]
    for bank_name, presets in banks:
        row = list(presets[:4])
        while len(row) < 4:
            row.append("-")
        table_data.append([bank_name] + row)

    if SimpleDocTemplate is None:
        write_simple_pdf(output_path, table_data)
        return output_path

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, rightMargin=24, leftMargin=24)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("<font color='#f5a623'><b>Ignitron Preset Chart</b></font>", styles["Title"]),
        Spacer(1, 12),
    ]
    table = Table(table_data, colWidths=[64, 112, 112, 112, 112], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f5a623")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f7f1e5"), colors.HexColor("#ead7b7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#6d5d42")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    doc.build(elements)
    return output_path


class StdoutQueue(io.TextIOBase):
    def __init__(self, callback):
        self.callback = callback

    def write(self, value):
        if value:
            self.callback(value)
        return len(value)

    def flush(self):
        return None


class IgnitronApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.configure(bg=BG)
        self.geometry("1320x820")
        self.minsize(1060, 680)
        self.current_page = None
        self.pages = {}
        self.active_serial_page = None
        self.logo_image = None
        self.project_dir_var = tk.StringVar(value=str(load_saved_project_dir()))
        self._configure_window()
        self._configure_styles()
        self._build_shell()
        self.show_page("home")
        self.after_idle(self._maximize_window)
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

    def _configure_window(self):
        icon = resource_path("IPT.ico")
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                self.geometry(f"{screen_width}x{screen_height}+0+0")

    def _toggle_fullscreen(self, _event=None):
        current = bool(self.attributes("-fullscreen"))
        self.attributes("-fullscreen", not current)

    def _exit_fullscreen(self, _event=None):
        if bool(self.attributes("-fullscreen")):
            self.attributes("-fullscreen", False)
            self.after_idle(self._maximize_window)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=SURFACE)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 24), foreground=TEXT)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=MUTED)
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 14), foreground=TEXT)
        style.configure("Gold.TButton", background=GOLD, foreground="#16120b", borderwidth=0,
                        padding=(18, 10), font=("Segoe UI Semibold", 10))
        style.map("Gold.TButton", background=[("active", GOLD_HOVER), ("pressed", ORANGE)])
        style.configure("Dark.TButton", background=CARD_ALT, foreground=TEXT, borderwidth=1,
                        padding=(14, 9), font=("Segoe UI Semibold", 9))
        style.map("Dark.TButton", background=[("active", BORDER)])
        style.configure("Danger.TButton", background="#402326", foreground="#ffb4b4", borderwidth=0,
                        padding=(10, 7))
        style.map("Danger.TButton", background=[("active", "#5b292d")])
        style.configure("TEntry", fieldbackground=CARD_ALT, foreground=TEXT, insertcolor=TEXT,
                        bordercolor=BORDER, padding=9)
        style.map(
            "TEntry",
            fieldbackground=[("disabled", CARD_ALT), ("readonly", CARD_ALT)],
            foreground=[("disabled", MUTED), ("readonly", TEXT)],
        )
        style.configure("TSpinbox", fieldbackground=CARD_ALT, background=CARD_ALT,
                        foreground=TEXT, arrowcolor=GOLD, bordercolor=BORDER, padding=4)
        style.map(
            "TSpinbox",
            fieldbackground=[("disabled", CARD_ALT), ("readonly", CARD_ALT)],
            foreground=[("disabled", MUTED), ("readonly", TEXT)],
            background=[("active", BORDER)],
        )
        style.configure("TCombobox", fieldbackground=CARD_ALT, background=CARD_ALT,
                        foreground=TEXT, arrowcolor=GOLD, bordercolor=BORDER, lightcolor=BORDER,
                        darkcolor=BORDER, padding=7)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", CARD_ALT), ("disabled", CARD_ALT)],
            selectbackground=[("readonly", CARD_ALT)],
            selectforeground=[("readonly", TEXT)],
            foreground=[("readonly", TEXT), ("disabled", MUTED)],
            background=[("readonly", CARD_ALT), ("disabled", CARD_ALT)],
        )
        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            bordercolor=BORDER,
            rowheight=24,
        )
        style.configure(
            "Treeview.Heading",
            background=CARD_ALT,
            foreground=TEXT,
            bordercolor=BORDER,
            relief="flat",
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Treeview",
            background=[("selected", ORANGE)],
            foreground=[("selected", "white")],
        )
        self.option_add("*TCombobox*Listbox.background", CARD_ALT)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ORANGE)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        style.configure("Vertical.TScrollbar", background=CARD_ALT, troughcolor=SURFACE,
                        bordercolor=SURFACE, arrowcolor=MUTED)
        style.configure("Horizontal.TScrollbar", background=CARD_ALT, troughcolor=SURFACE,
                        bordercolor=SURFACE, arrowcolor=MUTED)

    def _build_shell(self):
        sidebar = tk.Frame(self, bg="#111319", width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = tk.Frame(sidebar, bg="#111319")
        brand.pack(fill="x", padx=20, pady=(22, 24))
        logo = self._load_logo_image(142)
        if logo:
            tk.Label(brand, image=logo, bg="#111319", bd=0).pack(anchor="center")
        else:
            tk.Label(brand, text="IPT", bg=GOLD, fg="#05070a",
                     font=("Segoe UI Black", 22), width=8, height=3).pack(anchor="center")
        tk.Label(brand, text="IGNITRON", bg="#111319", fg=GOLD,
                 font=("Segoe UI Black", 18)).pack(anchor="center", pady=(8, 0))
        tk.Label(brand, text="PRESET TOOLS", bg="#111319", fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="center", pady=(1, 0))
        tk.Label(brand, text=f"VERSION {APP_VERSION}", bg="#111319", fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="center", pady=(8, 0))

        self.nav_buttons = {}
        self.nav_rows = {}
        self.nav_dots = {}
        for key, label, glyph in (
            ("home", "Dashboard", "HOME"),
            ("builder", "Preset Builder", "01"),
            ("firmware", "Firmware", "02"),
            ("remote", "Pedal Remote", "03"),
            ("capture", "Spark Capture", "04"),
            ("reference", "Reference", "05"),
        ):
            row = tk.Frame(sidebar, bg="#111319")
            row.pack(fill="x", padx=10, pady=2)
            button = tk.Button(row, text=f"  {glyph}   {label}", anchor="w",
                               bg="#111319", fg=MUTED, activebackground=CARD,
                               activeforeground=TEXT, relief="flat", bd=0,
                               font=("Segoe UI Semibold", 10), padx=15, pady=13,
                               command=lambda name=key: self.show_page(name))
            button.pack(side="left", fill="x", expand=True)
            self.nav_buttons[key] = button
            self.nav_rows[key] = row
            dot = tk.Canvas(row, width=18, height=18, bg="#111319", highlightthickness=0)
            dot.pack(side="right", padx=(0, 8))
            if key in FIRMWARE_MOD_PAGES:
                dot.create_oval(5, 5, 13, 13, fill=RED, outline="")
                self.nav_dots[key] = dot
            else:
                dot.pack_forget()

        tk.Frame(sidebar, bg=BORDER, height=1).pack(side="bottom", fill="x", padx=18, pady=(0, 15))
        legend = tk.Frame(sidebar, bg="#111319")
        legend.pack(side="bottom", fill="x", padx=20, pady=(0, 4))
        tk.Label(legend, text="Firmware mod", bg="#111319", fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w")
        legend_row = tk.Frame(legend, bg="#111319")
        legend_row.pack(anchor="w", pady=(5, 0))
        self._legend_dot(legend_row, GREEN).pack(side="left")
        tk.Label(legend_row, text="installed", bg="#111319", fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(4, 10))
        self._legend_dot(legend_row, RED).pack(side="left")
        tk.Label(legend_row, text="required", bg="#111319", fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))
        tk.Label(sidebar, text="Tone organized. Presets protected.", bg="#111319", fg=MUTED,
                 wraplength=170, justify="left", font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=20, pady=18)

        main = tk.Frame(self, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        self.page_host = tk.Frame(main, bg=BG)
        self.page_host.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Frame(main, bg="#111319", height=34)
        status.pack(fill="x", side="bottom")
        tk.Label(status, textvariable=self.status_var, bg="#111319", fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=18, pady=8)
        self.update_firmware_mod_indicators()

    def _legend_dot(self, parent, color):
        dot = tk.Canvas(parent, width=12, height=12, bg="#111319", highlightthickness=0)
        dot.create_oval(3, 3, 9, 9, fill=color, outline="")
        return dot

    def _load_logo_image(self, size):
        icon = resource_path("IPT.ico")
        if not icon.exists() or Image is None or ImageTk is None:
            return None
        try:
            image = Image.open(icon)
            image.seek(0)
            image = image.convert("RGBA")
            # The ICO contains a clipped fragment of an older IGNITRON wordmark
            # along its bottom edge. The sidebar renders its own complete title,
            # subtitle, and version labels, so keep only the flaming guitar art.
            logo_bottom = max(1, int(image.height * 0.94))
            image = image.crop((0, 0, image.width, logo_bottom))
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            self.logo_image = ImageTk.PhotoImage(image)
            return self.logo_image
        except Exception:
            return None

    def set_status(self, text):
        self.status_var.set(text)

    @property
    def project_dir(self):
        return Path(self.project_dir_var.get()).expanduser().resolve()

    @property
    def data_dir(self):
        return self.project_dir / "data"

    def set_project_dir(self, folder):
        self.project_dir_var.set(str(Path(folder).expanduser().resolve()))
        save_project_dir(self.project_dir)
        for page in self.pages.values():
            refresh = getattr(page, "on_project_changed", None)
            if refresh:
                refresh()
        self.set_status(f"Ignitron folder set to {self.project_dir}")
        self.update_firmware_mod_indicators()

    def show_page(self, name):
        if self.current_page:
            self.current_page.pack_forget()
        if name not in self.pages:
            page_class = {
                "home": HomePage,
                "builder": BuilderPage,
                "firmware": FirmwareUploadPage,
                "remote": PedalRemotePage,
                "capture": CapturePage,
                "reference": ReferencePage,
            }[name]
            self.pages[name] = page_class(self.page_host, self)
        self.current_page = self.pages[name]
        self.current_page.pack(fill="both", expand=True)
        for key, button in self.nav_buttons.items():
            bg = CARD if key == name else "#111319"
            fg = TEXT if key == name else MUTED
            button.configure(bg=bg, fg=fg, activebackground=CARD)
            row = self.nav_rows.get(key)
            if row:
                row.configure(bg=bg)
            dot = self.nav_dots.get(key)
            if dot:
                dot.configure(bg=bg)
        self.update_firmware_mod_indicators()

    def update_firmware_mod_indicators(self):
        project_dir = self.project_dir
        installed = False
        if (project_dir / "platformio.ini").exists():
            try:
                _missing_files, missing_markers = inspect_ipt_addon_support(project_dir)
                installed = not missing_markers
            except Exception:
                installed = False
        color = GREEN if installed else RED
        for key, dot in self.nav_dots.items():
            row_bg = CARD if self.current_page is self.pages.get(key) else "#111319"
            dot.configure(bg=row_bg)
            dot.delete("all")
            dot.create_oval(5, 5, 13, 13, fill=color, outline="")

    def show_firmware_setup(self):
        self.show_page("firmware")
        firmware = self.pages.get("firmware")
        show_setup = getattr(firmware, "show_ipt_setup_tab", None)
        if show_setup:
            show_setup()

    def request_serial_start(self, page):
        previous = self.active_serial_page
        if previous and previous is not page and getattr(previous, "running", False):
            previous.stop_serial(f"{page.tool_title} started")
            self.set_status(f"Stopped {previous.tool_title}; starting {page.tool_title}")
            time.sleep(0.25)
        self.active_serial_page = page

    def release_serial_page(self, page):
        if self.active_serial_page is page:
            self.active_serial_page = None


class Page(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

    def heading(self, title, subtitle, action=None, action_text=None):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=34, pady=(28, 20))
        copy = tk.Frame(header, bg=BG)
        copy.pack(side="left")
        ttk.Label(copy, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(copy, text=subtitle, style="Subtitle.TLabel").pack(anchor="w", pady=(5, 0))
        if action:
            ttk.Button(header, text=action_text, style="Gold.TButton", command=action).pack(side="right")
        return header


class HomePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.ipt_setup_popup = None
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")

        self.content = tk.Frame(self.canvas, bg=BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.canvas_window, width=event.width))
        self.canvas.bind("<MouseWheel>", self.mousewheel)
        self.content.bind("<MouseWheel>", self.mousewheel)

        header = tk.Frame(self.content, bg=BG)
        header.pack(fill="x", padx=34, pady=(28, 18))
        ttk.Label(header, text="Your tone workspace", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=f"{APP_NAME} v{APP_VERSION} - {APP_DESCRIPTION}",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(5, 0))

        project = tk.Frame(self.content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        project.pack(fill="x", padx=34, pady=(0, 14), ipady=8)
        tk.Label(project, text="IGNITRON FOLDER", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 10))
        ttk.Entry(project, textvariable=app.project_dir_var).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(project, text="Browse", style="Dark.TButton",
                   command=self.choose_ignitron_folder).pack(side="left", padx=(0, 10))
        ttk.Button(project, text="Load data", style="Gold.TButton",
                   command=self.load_project_data).pack(side="left", padx=(0, 18))
        self.project_status = tk.StringVar()
        tk.Label(self.content, textvariable=self.project_status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=34, pady=(0, 12))
        self.refresh_project_status()

        hero = tk.Frame(self.content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", padx=34, pady=(0, 18), ipady=16)
        hero_copy = tk.Frame(hero, bg=SURFACE)
        hero_copy.pack(side="left", fill="both", expand=True, padx=28, pady=10)
        tk.Label(hero_copy, text="IGNITRON", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 28)).pack(anchor="w")
        tk.Label(hero_copy, text="Version 2.0: safer exports, safer cleanup, smoother pedal workflows.", bg=SURFACE,
                 fg=TEXT, font=("Segoe UI Semibold", 16)).pack(anchor="w", pady=(4, 8))
        tk.Label(hero_copy, text=f"Released {APP_RELEASE_DATE}. Arrange, back up, flash, and capture your guitar tones.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(hero, text="IPT", bg=GOLD, fg="#17120a", width=6, height=3,
                 font=("Segoe UI Black", 18)).pack(side="right", padx=30)

        grid = tk.Frame(self.content, bg=BG)
        grid.pack(fill="both", expand=True, padx=34, pady=(0, 34))
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="tools")
        cards = (
            ("BUILD", "Preset Bank Builder", "Search your library and arrange four-slot banks with drag and double-click controls.", "builder"),
            ("FIRMWARE", "Firmware + Filesystem", "Build firmware, upload firmware, validate data, and upload the data filesystem from one place.", "firmware"),
            ("REMOTE", "Pedal Remote", "Click presets and show tuner readings when Ignitron enters tuner mode.", "remote"),
            ("CAPTURE + BACKUP", "Spark Capture", "Capture presets sent by the Spark app or pull the active bank or full library from a connected pedal.", "capture"),
            ("REFERENCE", "ESP32 Reference", "Interactive ESP32 Dev pinout and Ignitron wiring notes.", "reference"),
        )
        for index, (eyebrow, title, body, page) in enumerate(cards):
            row, col = divmod(index, 2)
            card = tk.Frame(grid, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0),
                      pady=(0 if row == 0 else 8, 8 if row == 0 else 0))
            tk.Label(card, text=eyebrow, bg=CARD, fg=GOLD,
                     font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22, pady=(20, 8))
            tk.Label(card, text=title, bg=CARD, fg=TEXT, wraplength=260, justify="left",
                     font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=22)
            tk.Label(card, text=body, bg=CARD, fg=MUTED, wraplength=270, justify="left",
                     font=("Segoe UI", 9), pady=10).pack(anchor="w", padx=22)
            ttk.Button(card, text="Open tool", style="Dark.TButton",
                       command=lambda p=page: app.show_page(p)).pack(anchor="w", padx=22, pady=(6, 20))

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        self._bind_mousewheel_tree(self.content)

    def mousewheel(self, event):
        if not self.winfo_ismapped():
            return None

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas or widget is self.content:
                delta = -1 * int(event.delta / 120) if event.delta else 0
                if delta:
                    self.canvas.yview_scroll(delta, "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def _bind_mousewheel_tree(self, widget):
        widget.bind("<MouseWheel>", self.mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_tree(child)

    def choose_ignitron_folder(self):
        folder = filedialog.askdirectory(
            title="Select main Ignitron project folder",
            initialdir=str(self.app.project_dir if self.app.project_dir.exists() else Path.home()),
        )
        if folder:
            self.app.set_project_dir(folder)
            self.refresh_project_status()
            self.check_firmware_ipt_setup()

    def load_project_data(self):
        self.app.set_project_dir(self.app.project_dir)
        self.refresh_project_status()
        self.check_firmware_ipt_setup()
        self.app.show_page("builder")
        builder = self.app.pages.get("builder")
        if isinstance(builder, BuilderPage):
            builder.load_project_data()

    def refresh_project_status(self):
        data_dir = self.app.data_dir
        if data_dir.exists():
            count = len(list(data_dir.glob("*.json")))
            self.project_status.set(f"Using data folder: {data_dir}  |  {count} JSON preset file(s)")
        else:
            self.project_status.set(f"Data folder not found yet: {data_dir}")

    def on_project_changed(self):
        self.refresh_project_status()

    def check_firmware_ipt_setup(self):
        project_dir = self.app.project_dir
        if not (project_dir / "platformio.ini").exists():
            return
        missing_files, missing_markers = inspect_ipt_addon_support(project_dir)
        if missing_markers:
            title = "IPT 2.0 firmware setup needed"
            body = (
                "This firmware folder is missing some IPT 2.0 support code.\n\n"
                f"Missing support item(s): {len(missing_markers)}\n"
                "Open Firmware > IPT 2.0 Setup to install the addon files before building or flashing."
            )
            accent = RED
            show_setup_link = True
        else:
            title = "IPT 2.0 firmware setup is good"
            body = (
                "This firmware folder already has the required IPT 2.0 support code.\n\n"
                "Remote preset control, hardware preset save/select, Spark 2 looper support, and status events were found."
            )
            accent = GREEN
            show_setup_link = False
        self.show_ipt_setup_popup(title, body, accent, show_setup_link)

    def show_ipt_setup_popup(self, title, body, accent, show_setup_link):
        if self.ipt_setup_popup and self.ipt_setup_popup.winfo_exists():
            self.ipt_setup_popup.destroy()
        popup = tk.Toplevel(self)
        self.ipt_setup_popup = popup
        popup.title(title)
        popup.configure(bg=BG)
        popup.transient(self.winfo_toplevel())
        popup.resizable(False, False)
        popup.grab_set()

        panel = tk.Frame(popup, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(panel, text=title, bg=SURFACE, fg=accent,
                 font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(16, 8))
        tk.Label(panel, text=body, bg=SURFACE, fg=TEXT, justify="left", wraplength=430,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(0, 16))
        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(fill="x", padx=18, pady=(0, 16))

        def open_setup():
            popup.destroy()
            self.app.show_firmware_setup()

        if show_setup_link:
            ttk.Button(actions, text="Open IPT 2.0 Setup", style="Gold.TButton",
                       command=open_setup).pack(side="left")
        ttk.Button(actions, text="Close", style="Dark.TButton",
                   command=popup.destroy).pack(side="right")
        popup.update_idletasks()
        root = self.winfo_toplevel()
        x = root.winfo_rootx() + max(40, (root.winfo_width() - popup.winfo_width()) // 2)
        y = root.winfo_rooty() + max(40, (root.winfo_height() - popup.winfo_height()) // 3)
        popup.geometry(f"+{x}+{y}")


class BuilderPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.library_folder = None
        self.output_folder = self.app.data_dir
        self.presets = []
        self.filtered = []
        self.bank_count = 30
        self.bank_count_var = tk.IntVar(value=self.bank_count)
        self.slots = {(b, s): None for b in range(1, self.bank_count + 1) for s in range(1, 5)}
        self.slot_widgets = {}
        self.dragging = None
        self.drag_ghost = None
        self.drag_target = None
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_library())
        self.library_count = tk.StringVar(value="Load Ignitron data to begin")
        self.usage_var = tk.StringVar(value=f"0 / {self.bank_count * 4} slots filled")
        self.heading("Preset Bank Builder", "Uses the data folder inside the selected Ignitron project.",
                     self.load_project_data, "Load Ignitron data")
        self._build()
        self.load_project_data(show_message=False)

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 26))
        body.grid_columnconfigure(0, weight=0, minsize=310)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        library = tk.Frame(body, bg=SURFACE, width=310, highlightbackground=BORDER, highlightthickness=1)
        library.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        library.grid_propagate(False)
        tk.Label(library, text="PRESET LIBRARY", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(library, textvariable=self.library_count, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(0, 12))
        ttk.Entry(library, textvariable=self.search_var).pack(fill="x", padx=18, pady=(0, 12))

        list_wrap = tk.Frame(library, bg=SURFACE)
        list_wrap.pack(fill="both", expand=True, padx=18)
        scroll = ttk.Scrollbar(list_wrap, orient="vertical")
        self.preset_list = tk.Listbox(list_wrap, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                      selectforeground="white", relief="flat", bd=0,
                                      highlightthickness=1, highlightbackground=BORDER,
                                      font=("Segoe UI", 9), activestyle="none", yscrollcommand=scroll.set)
        scroll.configure(command=self.preset_list.yview)
        self.preset_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.preset_list.bind("<Double-Button-1>", self.add_selected)
        self.preset_list.bind("<ButtonPress-1>", self.start_drag)
        self.preset_list.bind("<B1-Motion>", self.drag_motion)
        self.preset_list.bind("<ButtonRelease-1>", self.drop_drag)

        tk.Label(library, text="Double-click or drag a preset into a slot.", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=12)
        actions = tk.Frame(library, bg=SURFACE)
        actions.pack(fill="x", padx=18, pady=(0, 18))
        ttk.Button(actions, text="Load Ignitron data folder", style="Gold.TButton",
                   command=self.load_project_data).pack(fill="x", pady=(0, 5))
        ttk.Button(actions, text="Choose other library", style="Dark.TButton",
                   command=self.choose_library_folder).pack(fill="x", pady=3)
        ttk.Button(actions, text="Fill empty", style="Dark.TButton", command=self.fill_empty).pack(fill="x", pady=3)
        ttk.Button(actions, text="Clear all", style="Dark.TButton", command=self.clear_all).pack(fill="x", pady=3)

        workspace = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        workspace.grid(row=0, column=1, sticky="nsew")
        toolbar = tk.Frame(workspace, bg=SURFACE)
        toolbar.pack(fill="x", padx=20, pady=16)
        tk.Label(toolbar, text="BANK LAYOUT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        tk.Label(toolbar, textvariable=self.usage_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=14)
        bank_selector = tk.Frame(toolbar, bg=SURFACE)
        bank_selector.pack(side="left", padx=(8, 0))
        tk.Label(bank_selector, text="BANKS", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(0, 7))
        self.bank_spinbox = ttk.Spinbox(
            bank_selector, from_=1, to=30, width=4, justify="center",
            textvariable=self.bank_count_var, command=self.apply_bank_count
        )
        self.bank_spinbox.pack(side="left")
        self.bank_spinbox.bind("<Return>", self.apply_bank_count)
        self.bank_spinbox.bind("<FocusOut>", self.apply_bank_count)
        ttk.Button(toolbar, text="Export + select port", style="Gold.TButton",
                   command=self.export_and_upload_filesystem).pack(side="right")
        ttk.Button(toolbar, text="Save setup for flash", style="Dark.TButton",
                   command=self.save_setup_for_flash).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Open PresetList PDF", style="Dark.TButton",
                   command=self.open_current_pdf).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Export files", style="Dark.TButton",
                   command=self.export).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Add bank", style="Dark.TButton", command=self.add_bank).pack(side="right", padx=8)

        canvas_wrap = tk.Frame(workspace, bg=SURFACE)
        canvas_wrap.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.canvas = tk.Canvas(canvas_wrap, bg=SURFACE, highlightthickness=0)
        scroll = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.bank_host = tk.Frame(self.canvas, bg=SURFACE)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.bank_host, anchor="nw")
        self.bank_host.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self.mousewheel)
        self.render_banks()

    def choose_library_folder(self):
        initial = load_saved_path("preset_library_folder") or self.app.data_dir
        folder = filedialog.askdirectory(title="Select your main preset library", initialdir=str(initial))
        if not folder:
            return
        self.load_library_folder(Path(folder))

    def load_project_data(self, show_message=True):
        self.output_folder = self.app.data_dir
        if not self.output_folder.exists():
            self.presets = []
            self.filtered = []
            self.library_count.set(f"Data folder not found: {self.output_folder}")
            self.refresh_library()
            self.app.set_status(f"Data folder not found: {self.output_folder}")
            if show_message:
                messagebox.showerror("Data folder not found", f"No data folder exists at:\n{self.output_folder}")
            return False
        self.load_library_folder(self.output_folder)
        self.app.set_status(f"Using Ignitron data folder: {self.output_folder}")
        return True

    def on_project_changed(self):
        self.load_project_data(show_message=False)

    def load_library_folder(self, folder):
        self.library_folder = Path(folder)
        update_settings(preset_library_folder=self.library_folder)
        self.presets = []
        for path in sorted(self.library_folder.rglob("*.json"), key=lambda p: p.name.lower()):
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                data = {}
            self.presets.append({
                "filename": path.name,
                "name": str(data.get("Name", path.stem)),
                "uuid": str(data.get("UUID", "UNKNOWN")).upper(),
                "description": str(data.get("Description", "")),
                "bpm": data.get("BPM", ""),
                "version": str(data.get("Version", "")),
                "path": path,
                "data": data,
            })
        self.library_count.set(f"{len(self.presets)} presets  |  {self.library_folder.name}")
        self.refresh_library()
        self.app.set_status(f"Loaded {len(self.presets)} presets from main library: {self.library_folder}")

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Select Ignitron data folder for PresetList files")
        if not folder:
            return
        self.output_folder = Path(folder)
        json_files = list(self.output_folder.rglob("*.json"))
        if json_files:
            self.load_library_folder(self.output_folder)
            self.app.set_status(
                f"Loaded {len(self.presets)} presets and set data output folder: {self.output_folder}")
        else:
            self.app.set_status(
                f"Data output folder selected, but no JSON presets were found: {self.output_folder}")

    def refresh_library(self):
        query = self.search_var.get().strip().lower()
        self.filtered = [p for p in self.presets if query in p["name"].lower() or query in p["filename"].lower()]
        self.preset_list.delete(0, "end")
        used = {value for value in self.slots.values() if value}
        for index, preset in enumerate(self.filtered):
            self.preset_list.insert("end", preset["name"])
            self.preset_list.itemconfig(index, fg=GREEN if preset["filename"] in used else TEXT,
                                        bg=CARD_ALT if index % 2 else CARD)

    def render_banks(self):
        for child in self.bank_host.winfo_children():
            child.destroy()
        self.slot_widgets.clear()
        for bank in range(1, self.bank_count + 1):
            card = tk.Frame(self.bank_host, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
            card.pack(fill="x", padx=8, pady=7)
            header = tk.Frame(card, bg=CARD)
            header.pack(fill="x", padx=16, pady=(13, 5))
            tk.Label(header, text=f"BANK {bank:02d}", bg=CARD, fg=TEXT,
                     font=("Segoe UI Semibold", 12)).pack(side="left")
            ttk.Button(header, text="Remove", style="Danger.TButton",
                       command=lambda b=bank: self.remove_bank(b)).pack(side="right")
            slots = tk.Frame(card, bg=CARD)
            slots.pack(fill="x", padx=10, pady=(0, 13))
            for column in range(4):
                slots.grid_columnconfigure(column, weight=1, uniform="slot")
            for slot in range(1, 5):
                value = self.slots.get((bank, slot))
                text = self.display_name(value) if value else f"SLOT {slot}\nDrop preset here"
                widget = tk.Label(slots, text=text, bg="#24352e" if value else CARD_ALT,
                                  fg=TEXT if value else MUTED, height=4, justify="center",
                                  wraplength=150, relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=GREEN if value else BORDER,
                                  font=("Segoe UI Semibold", 9) if value else ("Segoe UI", 8))
                widget.grid(row=0, column=slot - 1, sticky="nsew", padx=5, pady=5)
                widget.bank, widget.slot = bank, slot
                widget.bind("<Button-3>", self.clear_slot)
                widget.bind("<Double-Button-1>", self.clear_slot)
                widget.bind("<Enter>", lambda e: e.widget.configure(highlightbackground=GOLD))
                widget.bind("<Leave>", lambda e, filled=bool(value): e.widget.configure(
                    highlightbackground=GREEN if filled else BORDER))
                self.slot_widgets[(bank, slot)] = widget
        self.update_usage()

    def display_name(self, filename):
        preset = next((p for p in self.presets if p["filename"] == filename), None)
        return preset["name"] if preset else (Path(filename).stem if filename else "")

    def selected_filename(self):
        selection = self.preset_list.curselection()
        if not selection or selection[0] >= len(self.filtered):
            return None
        return self.filtered[selection[0]]["filename"]

    def add_selected(self, _event=None):
        filename = self.selected_filename()
        if not filename:
            return
        for key, value in self.slots.items():
            if value is None:
                self.slots[key] = filename
                self.render_banks()
                self.refresh_library()
                return
        self.app.set_status("Every bank slot is already filled")

    def add_filename_to_next_slot(self, filename):
        for key, value in self.slots.items():
            if value is None:
                self.slots[key] = filename
                self.render_banks()
                self.refresh_library()
                self.app.set_status(f"Added {self.display_name(filename)} to Bank {key[0]:02d}, Slot {key[1]}")
                return True
        self.app.set_status("Every bank slot is already filled")
        return False

    def start_drag(self, event):
        index = self.preset_list.nearest(event.y)
        if 0 <= index < len(self.filtered):
            self.preset_list.selection_clear(0, "end")
            self.preset_list.selection_set(index)
            self.dragging = self.filtered[index]["filename"]
            self.drag_target = None

    def drag_motion(self, event):
        if not self.dragging:
            return
        if self.drag_ghost is None:
            self.drag_ghost = tk.Toplevel(self)
            self.drag_ghost.overrideredirect(True)
            try:
                self.drag_ghost.attributes("-topmost", True)
                self.drag_ghost.attributes("-alpha", 0.94)
            except tk.TclError:
                pass
            tk.Label(
                self.drag_ghost,
                text=self.display_name(self.dragging),
                bg=GOLD,
                fg="#17120a",
                padx=14,
                pady=8,
                relief="flat",
                font=("Segoe UI Semibold", 9),
            ).pack()

        x_root = event.x_root
        y_root = event.y_root
        self.drag_ghost.geometry(f"+{x_root + 16}+{y_root + 16}")
        self._set_drag_target(self._slot_at_pointer(x_root, y_root))

    def drop_drag(self, event):
        if not self.dragging:
            return
        target = self._slot_at_pointer(event.x_root, event.y_root)
        if target is not None:
            self.slots[(target.bank, target.slot)] = self.dragging
            self.render_banks()
            self.refresh_library()
            self.app.set_status(
                f"Dropped {self.display_name(self.dragging)} into Bank {target.bank:02d}, Slot {target.slot}")
        else:
            self._restore_slot_highlight(self.drag_target)
        self.dragging = None
        self.drag_target = None
        if self.drag_ghost is not None:
            self.drag_ghost.destroy()
            self.drag_ghost = None

    def _slot_at_pointer(self, x_root, y_root):
        widget = self.winfo_containing(x_root, y_root)
        while widget is not None and widget is not self:
            if hasattr(widget, "bank") and hasattr(widget, "slot"):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _set_drag_target(self, target):
        if target is self.drag_target:
            return
        self._restore_slot_highlight(self.drag_target)
        self.drag_target = target
        if target is not None:
            target.configure(highlightbackground=GOLD, highlightthickness=2)

    def _restore_slot_highlight(self, widget):
        if widget is None or not widget.winfo_exists():
            return
        value = self.slots.get((widget.bank, widget.slot))
        widget.configure(highlightbackground=GREEN if value else BORDER, highlightthickness=1)

    def clear_slot(self, event):
        self.slots[(event.widget.bank, event.widget.slot)] = None
        self.render_banks()
        self.refresh_library()

    def fill_empty(self):
        if not self.presets:
            self.app.set_status("Choose a preset folder first")
            return
        filenames = [p["filename"] for p in self.presets]
        unused = [name for name in filenames if name not in self.slots.values()]
        random.shuffle(unused)
        for key in self.slots:
            if self.slots[key] is None:
                self.slots[key] = unused.pop() if unused else random.choice(filenames)
        self.render_banks()
        self.refresh_library()

    def clear_all(self):
        if any(self.slots.values()) and not messagebox.askyesno("Clear layout", "Clear every preset slot?"):
            return
        for key in self.slots:
            self.slots[key] = None
        self.render_banks()
        self.refresh_library()

    def add_bank(self):
        if self.bank_count >= 30:
            self.app.set_status("The maximum is 30 banks")
            return
        self.bank_count += 1
        self.bank_count_var.set(self.bank_count)
        for slot in range(1, 5):
            self.slots[(self.bank_count, slot)] = None
        self.render_banks()

    def apply_bank_count(self, _event=None):
        try:
            requested = int(self.bank_count_var.get())
        except (TypeError, ValueError, tk.TclError):
            requested = self.bank_count
        requested = max(1, min(30, requested))
        self.bank_count_var.set(requested)
        if requested == self.bank_count:
            return

        if requested < self.bank_count:
            removed_values = [
                self.slots.get((bank, slot))
                for bank in range(requested + 1, self.bank_count + 1)
                for slot in range(1, 5)
            ]
            if any(removed_values) and not messagebox.askyesno(
                    "Reduce bank count",
                    f"Changing to {requested} bank(s) will remove assigned presets from the final "
                    f"{self.bank_count - requested} bank(s). Continue?"):
                self.bank_count_var.set(self.bank_count)
                return
            self.slots = {
                key: value for key, value in self.slots.items()
                if key[0] <= requested
            }
        else:
            for bank in range(self.bank_count + 1, requested + 1):
                for slot in range(1, 5):
                    self.slots[(bank, slot)] = None

        self.bank_count = requested
        self.render_banks()
        self.refresh_library()
        self.app.set_status(f"Bank layout changed to {self.bank_count} bank(s)")

    def remove_bank(self, bank):
        if self.bank_count == 1:
            self.app.set_status("At least one bank is required")
            return
        if any(self.slots.get((bank, slot)) for slot in range(1, 5)):
            if not messagebox.askyesno("Remove bank", f"Remove Bank {bank:02d} and its assigned presets?"):
                return
        new_slots = {}
        new_bank = 1
        for old_bank in range(1, self.bank_count + 1):
            if old_bank == bank:
                continue
            for slot in range(1, 5):
                new_slots[(new_bank, slot)] = self.slots.get((old_bank, slot))
            new_bank += 1
        self.bank_count -= 1
        self.bank_count_var.set(self.bank_count)
        self.slots = new_slots
        self.render_banks()
        self.refresh_library()

    def update_usage(self):
        filled = sum(value is not None for value in self.slots.values())
        self.usage_var.set(f"{filled} / {self.bank_count * 4} slots filled")

    def has_assigned_slots(self):
        return any(value for value in self.slots.values())

    def mousewheel(self, event):
        if not self.winfo_ismapped():
            return None

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self.canvas or widget is self.bank_host:
                delta = -1 * int(event.delta / 120) if event.delta else 0
                if delta:
                    self.canvas.yview_scroll(delta, "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def export(self, show_message=True, backup_existing=True):
        if not self.output_folder:
            self.choose_output_folder()
        if not self.output_folder:
            return False
        self.output_folder.mkdir(parents=True, exist_ok=True)
        backup_root = self.output_folder / "_ipt_backups"
        backed_up = []
        if backup_existing:
            backed_up = [
                backup
                for backup in (
                    backup_file(self.output_folder / "PresetList.txt", backup_root),
                    backup_file(self.output_folder / "PresetListUUIDs.txt", backup_root),
                    backup_file(self.output_folder / "PresetList.pdf", backup_root),
                )
                if backup
            ]
        lines, uuid_lines = [], []
        lookup = {p["filename"]: p for p in self.presets}
        copied = 0
        copied_files = set()
        for bank in range(1, self.bank_count + 1):
            lines.append(f"-- Bank {bank}")
            assigned = [self.slots[(bank, slot)] for slot in range(1, 5) if self.slots[(bank, slot)]]
            if assigned:
                while len(assigned) < 4:
                    assigned.append(assigned[-1])
                for filename in assigned:
                    lines.append(filename)
                    preset = lookup.get(filename, {})
                    uuid_lines.append(f"{filename} {preset.get('uuid', 'UNKNOWN')}")
                    source_path = preset.get("path")
                    if source_path:
                        source_path = Path(source_path)
                        destination = self.output_folder / source_path.name
                        if (
                            source_path.name not in copied_files
                            and source_path.exists()
                            and source_path.resolve() != destination.resolve()
                        ):
                            shutil.copy2(source_path, destination)
                            copied_files.add(source_path.name)
                            copied += 1
        (self.output_folder / "PresetList.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.output_folder / "PresetListUUIDs.txt").write_text("\n".join(uuid_lines) + "\n", encoding="utf-8")
        pdf_message = ""
        pdf_path = None
        try:
            pdf_path = generate_preset_chart(self.output_folder)
            pdf_message = f"\n\nUpdated {pdf_path.name}."
            self.app.set_status(f"Exported PresetList files and PDF to {self.output_folder}")
        except Exception as exc:
            pdf_message = f"\n\nPresetList.pdf was not updated: {exc}"
            self.app.set_status(f"Exported PresetList files, but PDF update failed: {exc}")
        if show_message:
            backup_message = ""
            if backed_up:
                backup_message = f"\n\nPrevious files were backed up to:\n{backup_root}"
            messagebox.showinfo(
                "Export complete",
                "PresetList.txt and PresetListUUIDs.txt were created." + pdf_message + backup_message,
            )
        if copied:
            self.app.set_status(f"Saved preset setup and copied {copied} selected JSON file(s) to {self.output_folder}")
        return True

    def open_current_pdf(self):
        folder = self.output_folder or self.app.data_dir
        pdf_path = Path(folder) / "PresetList.pdf"
        if pdf_path.exists():
            open_folder(pdf_path)
            self.app.set_status(f"Opened {pdf_path}")
        else:
            messagebox.showinfo("PresetList PDF not found", f"No PresetList.pdf exists yet at:\n{pdf_path}\n\nExport or save the setup first.")

    def save_setup_for_flash(self, show_message=True):
        self.output_folder = self.app.data_dir
        if not self.has_assigned_slots():
            if show_message:
                messagebox.showinfo("No preset setup", "Assign presets to the bank layout before saving it for flashing.")
            self.app.set_status("No preset setup to save")
            return False
        if not self.export(show_message=False, backup_existing=False):
            return False
        message = f"Saved this bank layout to:\n{self.output_folder}\n\nThe next firmware/filesystem flash will upload this preset setup."
        self.app.set_status("Preset setup saved for next flash")
        if show_message:
            messagebox.showinfo("Preset setup saved", message)
        return True

    def export_and_upload_filesystem(self):
        if not self.export(show_message=False):
            return
        self.app.show_page("firmware")
        firmware = self.app.pages.get("firmware")
        if isinstance(firmware, FirmwareUploadPage):
            if self.output_folder and self.output_folder.name.lower() == "data":
                project = self.output_folder.parent
                if (project / "platformio.ini").exists():
                    self.app.set_project_dir(project)
                    firmware.load_project_defaults()
            firmware.prepare_upload_after_builder_export()


class PresetLibraryBrowser(tk.Toplevel):
    def __init__(self, builder):
        super().__init__(builder)
        self.builder = builder
        self.title("Ignitron Preset Library Browser")
        self.configure(bg=BG)
        self.geometry("1120x720")
        self.minsize(900, 580)
        self.transient(builder.winfo_toplevel())
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="All presets")
        self.sort_column = "name"
        self.sort_reverse = False
        self.visible_presets = []
        self.detail_title = tk.StringVar(value="Select a preset")
        self.detail_meta = tk.StringVar(value="Preset details will appear here.")
        self._build()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.filter_var.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=26, pady=(22, 16))
        tk.Label(header, text="Preset Library", bg=BG, fg=TEXT,
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(header, text="Browse metadata, inspect JSON, and send presets directly to the bank layout.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        controls.pack(fill="x", padx=26, pady=(0, 14))
        tk.Label(controls, text="SEARCH", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(16, 8), pady=14)
        ttk.Entry(controls, textvariable=self.search_var, width=36).pack(side="left", pady=10)
        tk.Label(controls, text="SHOW", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(side="left", padx=(18, 8))
        ttk.Combobox(controls, textvariable=self.filter_var, state="readonly", width=14,
                     values=("All presets", "Unused only", "Used only")).pack(side="left")
        self.result_label = tk.Label(controls, text="", bg=SURFACE, fg=MUTED,
                                     font=("Segoe UI", 9))
        self.result_label.pack(side="right", padx=16)

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=26, pady=(0, 16))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        table_panel = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        table_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        columns = ("name", "filename", "bpm", "status")
        self.tree = ttk.Treeview(table_panel, columns=columns, show="headings", selectmode="browse")
        headings = {"name": "Preset name", "filename": "Filename", "bpm": "BPM", "status": "Usage"}
        widths = {"name": 190, "filename": 220, "bpm": 58, "status": 75}
        for column in columns:
            self.tree.heading(column, text=headings[column],
                              command=lambda col=column: self.sort_by(col))
            self.tree.column(column, width=widths[column], minwidth=50,
                             anchor="center" if column in ("bpm", "status") else "w")
        scroll = ttk.Scrollbar(table_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)
        self.tree.bind("<Double-Button-1>", self.add_selected)

        details = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        details.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(details, text="PRESET DETAILS", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=18, pady=(17, 7))
        tk.Label(details, textvariable=self.detail_title, bg=SURFACE, fg=TEXT,
                 wraplength=360, justify="left", font=("Segoe UI Semibold", 15)).pack(anchor="w", padx=18)
        tk.Label(details, textvariable=self.detail_meta, bg=SURFACE, fg=MUTED,
                 wraplength=360, justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(6, 12))
        self.description_label = tk.Label(details, text="", bg=SURFACE, fg=TEXT,
                                          wraplength=360, justify="left", font=("Segoe UI", 9))
        self.description_label.pack(anchor="w", padx=18, pady=(0, 12))
        self.json_preview = tk.Text(details, bg="#0b0d11", fg="#cbd0d8", relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER,
                                    font=("Consolas", 8), wrap="none", state="disabled")
        self.json_preview.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=26, pady=(0, 22))
        ttk.Button(footer, text="Open preset folder", style="Dark.TButton",
                   command=lambda: open_folder(self.builder.folder)).pack(side="left")
        ttk.Button(footer, text="Close", style="Dark.TButton", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="Add to next empty slot", style="Gold.TButton",
                   command=self.add_selected).pack(side="right", padx=9)

    def refresh(self, preserve_selection=False):
        selected_filename = self.selected_filename() if preserve_selection else None
        query = self.search_var.get().strip().lower()
        used = {value for value in self.builder.slots.values() if value}
        filter_name = self.filter_var.get()
        presets = []
        for preset in self.builder.presets:
            searchable = " ".join((preset["name"], preset["filename"], preset["uuid"],
                                   preset.get("description", ""))).lower()
            is_used = preset["filename"] in used
            if query and query not in searchable:
                continue
            if filter_name == "Unused only" and is_used:
                continue
            if filter_name == "Used only" and not is_used:
                continue
            presets.append(preset)
        presets.sort(key=self.sort_key, reverse=self.sort_reverse)
        self.visible_presets = presets
        self.tree.delete(*self.tree.get_children())
        selected_item = None
        for index, preset in enumerate(presets):
            status = "Used" if preset["filename"] in used else "Unused"
            item = self.tree.insert("", "end", iid=f"preset-{index}", values=(
                preset["name"], preset["filename"], preset.get("bpm", ""), status))
            if preset["filename"] == selected_filename:
                selected_item = item
        self.result_label.configure(text=f"{len(presets)} of {len(self.builder.presets)} presets")
        if selected_item:
            self.tree.selection_set(selected_item)
            self.tree.see(selected_item)
        elif presets and not preserve_selection:
            self.tree.selection_set("preset-0")
            self.show_selected()

    def sort_key(self, preset):
        if self.sort_column == "status":
            return preset["filename"] in self.builder.slots.values()
        value = preset.get(self.sort_column, "")
        if self.sort_column == "bpm":
            try:
                return float(value)
            except (TypeError, ValueError):
                return -1
        return str(value).lower()

    def sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh(preserve_selection=True)

    def selected_preset(self):
        selection = self.tree.selection()
        if not selection:
            return None
        try:
            index = int(selection[0].split("-", 1)[1])
            return self.visible_presets[index]
        except (IndexError, ValueError):
            return None

    def selected_filename(self):
        preset = self.selected_preset()
        return preset["filename"] if preset else None

    def show_selected(self, _event=None):
        preset = self.selected_preset()
        if not preset:
            return
        used_count = sum(value == preset["filename"] for value in self.builder.slots.values())
        bpm = preset.get("bpm", "Not specified") or "Not specified"
        version = preset.get("version", "Not specified") or "Not specified"
        self.detail_title.set(preset["name"])
        self.detail_meta.set(
            f"{preset['filename']}\nBPM: {bpm}   Version: {version}\n"
            f"Used in {used_count} slot(s)\nUUID: {preset['uuid']}")
        self.description_label.configure(text=preset.get("description", "") or "No description provided.")
        raw = json.dumps(preset.get("data", {}), indent=2, ensure_ascii=False)
        self.json_preview.configure(state="normal")
        self.json_preview.delete("1.0", "end")
        self.json_preview.insert("1.0", raw)
        self.json_preview.configure(state="disabled")

    def add_selected(self, _event=None):
        preset = self.selected_preset()
        if preset and self.builder.add_filename_to_next_slot(preset["filename"]):
            self.refresh(preserve_selection=True)
            self.show_selected()


class ReferencePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.pin_items = {}
        self.pin_detail_var = tk.StringVar(value="Click a pin on the ESP32 Dev board to see wiring notes.")
        self.reference_dir = resource_path("reference")
        self.heading("ESP32 Reference", "Interactive ESP32 Dev pinout, Ignitron hardware docs, and firmware setting notes.")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        pinout = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        pinout.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(pinout, text="ESP32 DEV MODULE", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(pinout, text="Click a GPIO to view Ignitron usage and boot-safety notes.",
                 bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))
        self.canvas = tk.Canvas(pinout, bg="#0b0d11", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.canvas.bind("<Configure>", lambda _event: self.draw_pinout())

        side = tk.Frame(body, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        side.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(side, text="PIN DETAIL", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(side, textvariable=self.pin_detail_var, bg=SURFACE, fg=TEXT,
                 justify="left", wraplength=460, font=("Segoe UI Semibold", 12)).pack(
                     anchor="w", fill="x", padx=18, pady=(0, 18))

        tk.Label(side, text="REFERENCE FILES", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=18, pady=(0, 8))
        files = tk.Frame(side, bg=SURFACE)
        files.pack(fill="x", padx=18, pady=(0, 18))
        files.grid_columnconfigure(0, weight=1)
        files.grid_columnconfigure(1, weight=1)
        reference_files = self.reference_files()
        for index, (label, filename) in enumerate(reference_files):
            path = self.reference_dir / filename
            ttk.Button(files, text=label, style="Dark.TButton",
                       command=lambda item=path: self.open_reference(item)).grid(
                           row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=3)
        ttk.Button(files, text="Folder", style="Dark.TButton",
                   command=lambda: self.open_reference(self.reference_dir)).grid(
                       row=(len(reference_files) + 1) // 2, column=0, columnspan=2,
                       sticky="ew", padx=(0, 6), pady=3)

        notes = tk.Text(side, bg="#0b0d11", fg="#cbd0d8", relief="flat",
                        highlightthickness=1, highlightbackground=BORDER,
                        font=("Segoe UI", 9), wrap="word")
        notes.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        notes.insert("1.0", self.reference_text())
        notes.configure(state="disabled")

    def reference_text(self):
        return (
            "IGNITRON DEFAULTS\n"
            "- Amp mode rocker: GPIO35 with external 10k pull-up to 3.3V, switch to GND.\n"
            "- Battery ADC: GPIO36. Keep battery voltage divided before it reaches the ESP32.\n"
            "- OLED I2C: SDA GPIO21, SCL GPIO22.\n"
            "- Filesystem upload only updates the data folder and presetlist; it does not flash firmware.\n\n"
            "BOOT / SAFETY NOTES\n"
            "- GPIO34 to GPIO39 are input-only. They are good for switches or ADC, not LEDs.\n"
            "- GPIO35 has no internal pull-up, so the rocker needs the physical 10k pull-up.\n"
            "- GPIO0, GPIO2, GPIO4, GPIO5, GPIO12, and GPIO15 affect ESP32 boot strapping. Avoid adding switches "
            "or pull resistors there unless you know the boot-state requirement.\n"
            "- GPIO6 to GPIO11 are normally connected to flash memory and should not be used.\n\n"
            "FIRMWARE OPTIONS\n"
            "- Use the Firmware tab to change OLED driver, battery display, LED mode, firmware version, "
            "and whether the amp mode rocker is installed.\n"
            "- When the rocker is installed, LOW means amp mode on boot and HIGH means normal app boot."
            "\n\nREFERENCE FOLDER MATERIAL\n"
            "- Ignitron-Schematics.pdf: main PCB schematic reference.\n"
            "- Ignitron-Battery-Indicator-Schematics.pdf: battery divider and power reference.\n"
            "- Ignitron-UV-Print.pdf: Tayda UV print template. Use a PDF viewer with layer support.\n"
            "- ignitron-cheatsheet.pdf: quick reference sheet.\n"
            "- README.md: hardware BOM, PCB assembly, enclosure drill locations, battery notes, 3D case notes, "
            "and optional preset LED wiring."
            "\n\nMAIN SCHEMATIC PIN MAP\n"
            "- SW1 P1/Drive: GPIO25. D1 P1/Drive LED: GPIO27.\n"
            "- SW2 P2/Mod: GPIO26. D2 P2/Mod LED: GPIO13.\n"
            "- SW3 P3/Delay: GPIO32. D3 P3/Delay LED: GPIO16.\n"
            "- SW4 P4/Reverb: GPIO33. D4 P4/Reverb LED: GPIO14.\n"
            "- SW5 Bank Down/Noise Gate: GPIO19. D5 Bank Down/Noise Gate LED: GPIO23.\n"
            "- SW6 Bank Up/Comp: GPIO18. D6 Bank Up/Comp LED: GPIO17.\n"
            "- J2 OLED: VCC, SCL GPIO22, SDA GPIO21, GND.\n"
            "- J1 PowerIn: 9V and GND into the PCB power input."
        )

    def reference_files(self):
        files = [
            ("Cheatsheet", "ignitron-cheatsheet.pdf"),
            ("Schematics", "Ignitron-Schematics.pdf"),
            ("Battery", "Ignitron-Battery-Indicator-Schematics.pdf"),
            ("UV Print", "Ignitron-UV-Print.pdf"),
            ("README", "README.md"),
        ]
        return [(label, filename) for label, filename in files if (self.reference_dir / filename).exists()]

    def open_reference(self, path):
        path = Path(path)
        if not path.exists():
            messagebox.showwarning("Missing reference", f"Could not find:\n{path}")
            return
        open_folder(path)
        self.app.set_status(f"Opened reference: {path.name}")

    def pin_data(self):
        return [
            {"pin": "3V3", "side": "left", "kind": "power", "note": "3.3V power rail. The schematic uses this for switch pull-ups and OLED VCC. Use it for the amp rocker 10k pull-up too."},
            {"pin": "EN", "side": "left", "kind": "control", "note": "Reset enable pin. Usually left alone."},
            {"pin": "GPIO36", "side": "left", "kind": "adc", "note": "Battery voltage ADC input in firmware. Used with the battery indicator divider schematic, not on the original main PCB schematic."},
            {"pin": "GPIO39", "side": "left", "kind": "input", "note": "Input-only ADC-capable pin. Available if firmware is changed."},
            {"pin": "GPIO34", "side": "left", "kind": "input", "note": "Input-only. Usable for switches with an external pull-up or pull-down."},
            {"pin": "GPIO35", "label": "GPIO35 - Amp SW", "side": "left", "kind": "rocker", "note": "Optional amp mode rocker switch input. Add-on mod, not on the original main PCB schematic. External 10k pull-up to 3.3V, SPST switch to GND. LOW at boot forces AMP mode."},
            {"pin": "GPIO32", "label": "GPIO32 - SW3", "side": "left", "kind": "button", "note": "SW3 on the schematic: P3 / Delay footswitch. Firmware names: BUTTON_PRESET3_GPIO and BUTTON_DELAY_GPIO."},
            {"pin": "GPIO33", "label": "GPIO33 - SW4", "side": "left", "kind": "button", "note": "SW4 on the schematic: P4 / Reverb footswitch. Firmware names: BUTTON_PRESET4_GPIO and BUTTON_REVERB_GPIO."},
            {"pin": "GPIO25", "label": "GPIO25 - SW1", "side": "left", "kind": "button", "note": "SW1 on the schematic: P1 / Drive footswitch. Firmware names: BUTTON_PRESET1_GPIO and BUTTON_DRIVE_GPIO."},
            {"pin": "GPIO26", "label": "GPIO26 - SW2", "side": "left", "kind": "button", "note": "SW2 on the schematic: P2 / Mod footswitch. Firmware names: BUTTON_PRESET2_GPIO and BUTTON_MOD_GPIO."},
            {"pin": "GPIO27", "label": "GPIO27 - D1", "side": "left", "kind": "led", "note": "D1 LED on the schematic through R1: P1 / Drive LED. Firmware names: LED_PRESET1_GPIO and LED_DRIVE_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO14", "label": "GPIO14 - D4", "side": "left", "kind": "led", "note": "D4 LED on the schematic through R4: P4 / Reverb LED. Firmware names: LED_PRESET4_GPIO and LED_REVERB_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO12", "label": "GPIO12 - Optional P3 LED", "side": "left", "kind": "strap", "note": "Optional dedicated preset LED 3 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; avoid pulling it into the wrong state at reset."},
            {"pin": "GND", "side": "left", "kind": "power", "note": "Ground reference. Rocker switch closes to GND."},
            {"pin": "VIN", "side": "right", "kind": "power", "note": "5V/VIN supply depending on board. Do not connect directly to GPIO."},
            {"pin": "GND", "side": "right", "kind": "power", "note": "Ground reference."},
            {"pin": "GPIO13", "label": "GPIO13 - D2", "side": "right", "kind": "led", "note": "D2 LED on the schematic through R2: P2 / Mod LED. Firmware names: LED_PRESET2_GPIO and LED_MOD_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO9", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO10", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO11", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO6", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO7", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO8", "side": "right", "kind": "flash", "note": "Usually connected to module flash. Do not use."},
            {"pin": "GPIO15", "label": "GPIO15 - Optional P4 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 4 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; avoid pulling it into the wrong state at reset."},
            {"pin": "GPIO2", "side": "right", "kind": "strap", "note": "Boot strap pin. Often tied to onboard LED; avoid for switches."},
            {"pin": "GPIO0", "label": "GPIO0 - Optional P1 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 1 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot/program strap pin; LOW at reset enters bootloader."},
            {"pin": "GPIO4", "label": "GPIO4 - Optional P2 LED", "side": "right", "kind": "strap", "note": "Optional dedicated preset LED 2 from the 3D case docs and firmware DEDICATED_PRESET_LEDS mode. Boot strap pin; wire carefully."},
            {"pin": "GPIO16", "label": "GPIO16 - D3", "side": "right", "kind": "led", "note": "D3 LED on the schematic through R3: P3 / Delay LED. Firmware names: LED_PRESET3_GPIO and LED_DELAY_GPIO when dedicated preset LEDs are off."},
            {"pin": "GPIO17", "label": "GPIO17 - D6", "side": "right", "kind": "led", "note": "D6 LED on the schematic through R6: Bank Up / Comp LED. Firmware names: LED_BANK_UP_GPIO and LED_COMP_GPIO."},
            {"pin": "GPIO5", "side": "right", "kind": "strap", "note": "Boot strap pin. Avoid for add-on switches."},
            {"pin": "GPIO18", "label": "GPIO18 - SW6", "side": "right", "kind": "button", "note": "SW6 on the schematic: Bank Up / Comp footswitch. Firmware names: BUTTON_BANK_UP_GPIO and BUTTON_COMP_GPIO."},
            {"pin": "GPIO19", "label": "GPIO19 - SW5", "side": "right", "kind": "button", "note": "SW5 on the schematic: Bank Down / Noise Gate footswitch. Firmware names: BUTTON_BANK_DOWN_GPIO and BUTTON_NOISEGATE_GPIO."},
            {"pin": "GPIO21", "label": "GPIO21 - J2 SDA", "side": "right", "kind": "i2c", "note": "J2 OLED connector pin 3: SDA for the SSD1306/SSD1309/SH1106 display."},
            {"pin": "GPIO22", "label": "GPIO22 - J2 SCL", "side": "right", "kind": "i2c", "note": "J2 OLED connector pin 2: SCL for the SSD1306/SSD1309/SH1106 display."},
            {"pin": "GPIO23", "label": "GPIO23 - D5", "side": "right", "kind": "led", "note": "D5 LED on the schematic through R5: Bank Down / Noise Gate LED. Firmware names: LED_BANK_DOWN_GPIO and LED_NOISEGATE_GPIO."},
        ]

    def draw_pinout(self):
        self.canvas.delete("all")
        self.pin_items = {}
        width = max(self.canvas.winfo_width(), 620)
        height = max(self.canvas.winfo_height(), 660)
        board_w = max(220, min(320, width - 300))
        board_h = height - 48
        x1 = (width - board_w) / 2
        y1 = 24
        x2 = x1 + board_w
        y2 = y1 + board_h

        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#18202b", outline=BORDER, width=2)
        self.canvas.create_rectangle(x1 + 74, y1 + 22, x2 - 74, y1 + 88, fill="#263141", outline="#4a5668")
        self.canvas.create_text((x1 + x2) / 2, y1 + 55, text="USB", fill=TEXT, font=("Segoe UI Semibold", 11))
        self.canvas.create_text((x1 + x2) / 2, y1 + 122, text="ESP32 DEVKIT", fill=GOLD,
                                font=("Segoe UI Semibold", 16))
        self.canvas.create_text((x1 + x2) / 2, y2 - 28, text="Click any labeled pin", fill=MUTED,
                                font=("Segoe UI", 9))

        pins = self.pin_data()
        left = [pin for pin in pins if pin["side"] == "left"]
        right = [pin for pin in pins if pin["side"] == "right"]
        self._draw_pin_column(left, x1, y1 + 138, y2 - 58, "left")
        self._draw_pin_column(right, x2, y1 + 138, y2 - 58, "right")

        legend = [
            ("rocker", "Amp rocker"),
            ("button", "Button"),
            ("led", "LED"),
            ("i2c", "OLED"),
            ("adc", "Battery ADC"),
            ("strap", "Boot strap"),
            ("flash", "Flash"),
        ]
        lx, ly = 18, 18
        for kind, label in legend:
            self.canvas.create_rectangle(lx, ly, lx + 12, ly + 12, fill=self.pin_color(kind), outline="")
            self.canvas.create_text(lx + 18, ly + 6, text=label, fill=MUTED, anchor="w", font=("Segoe UI", 8))
            ly += 18

    def _draw_pin_column(self, pins, board_edge, top, bottom, side):
        spacing = (bottom - top) / max(len(pins) - 1, 1)
        for index, pin in enumerate(pins):
            y = top + index * spacing
            if side == "left":
                pad_x = board_edge - 10
                label_x = pad_x - 8
                anchor = "e"
                pin_x1, pin_x2 = board_edge - 20, board_edge
            else:
                pad_x = board_edge + 10
                label_x = pad_x + 8
                anchor = "w"
                pin_x1, pin_x2 = board_edge, board_edge + 20

            color = self.pin_color(pin["kind"])
            tag = f"pin_{pin['pin']}_{side}"
            items = [
                self.canvas.create_rectangle(pin_x1, y - 6, pin_x2, y + 6, fill=color, outline=""),
                self.canvas.create_oval(pad_x - 4, y - 4, pad_x + 4, y + 4, fill="#050608", outline=color),
                self.canvas.create_text(label_x, y, text=pin.get("label", pin["pin"]), fill=TEXT, anchor=anchor, font=("Segoe UI", 9)),
            ]
            self.pin_items[tag] = {"pin": pin, "items": items}
            for item in items:
                self.canvas.itemconfigure(item, tags=(tag,))
            self.canvas.tag_bind(tag, "<Button-1>", lambda _event, item=pin: self.select_pin(item))
            self.canvas.tag_bind(tag, "<Enter>", lambda _event, tag=tag: self.canvas.itemconfigure(tag, fill=GOLD))
            self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.draw_pinout())

    def pin_color(self, kind):
        colors = {
            "rocker": GOLD,
            "button": "#67b7dc",
            "led": "#8dd37e",
            "i2c": "#c792ea",
            "adc": "#ffcb6b",
            "strap": "#ff6f61",
            "flash": "#6f7785",
            "power": "#f07178",
            "input": "#82aaff",
            "control": "#89ddff",
        }
        return colors.get(kind, "#cbd0d8")

    def select_pin(self, pin):
        self.pin_detail_var.set(f"{pin['pin']}\n{pin['note']}")
        self.app.set_status(f"Reference selected: {pin['pin']}")


class SetlistBuilder:
    def __init__(self, parent, presets):
        self.parent = parent
        self.presets = presets
        self.filtered = list(presets)
        self.storage_file = app_dir() / "data" / "setlists.json"
        self.setlists = self.load_setlists()
        self.current_name = None
        self.current_items = []
        self.window = tk.Toplevel(parent)
        self.window.title("Ignitron Live Setlist Builder")
        self.window.configure(bg=BG)
        self.window.geometry("1200x740")
        self.window.minsize(900, 560)
        self._build()
        self.refresh_names()
        self.refresh_library()

    def load_setlists(self):
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def save_setlists(self):
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.storage_file.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.setlists, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.storage_file)

    def _build(self):
        toolbar = tk.Frame(self.window, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        toolbar.pack(fill="x", padx=20, pady=20)
        tk.Label(toolbar, text="SETLIST", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(14, 8), pady=14)
        self.name_var = tk.StringVar()
        self.name_combo = ttk.Combobox(toolbar, textvariable=self.name_var, state="readonly", width=30)
        self.name_combo.pack(side="left")
        self.name_combo.bind("<<ComboboxSelected>>", self.load_selected)
        ttk.Button(toolbar, text="New", style="Dark.TButton", command=self.new).pack(side="left", padx=(10, 3))
        ttk.Button(toolbar, text="Save", style="Dark.TButton", command=self.save).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Save As", style="Dark.TButton", command=self.save_as).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Live Mode", style="Gold.TButton", command=self.open_live_mode).pack(side="right", padx=12)
        self.status_var = tk.StringVar(value="Unsaved setlist")
        tk.Label(toolbar, textvariable=self.status_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=12)

        content = tk.Frame(self.window, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(2, weight=1)
        content.grid_rowconfigure(1, weight=1)
        tk.Label(content, text="PRESET LIBRARY", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", pady=(0, 8))
        tk.Label(content, text="SETLIST ORDER", bg=BG, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=2, sticky="w", pady=(0, 8))

        left = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=1, column=0, sticky="nsew")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_library())
        ttk.Entry(left, textvariable=self.search_var).pack(fill="x", padx=12, pady=12)
        self.library_list = tk.Listbox(left, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                       selectforeground="white", relief="flat", exportselection=False)
        self.library_list.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.library_list.bind("<Double-Button-1>", lambda _event: self.add_preset())

        controls = tk.Frame(content, bg=BG)
        controls.grid(row=1, column=1, padx=14)
        ttk.Button(controls, text="Add  >", style="Dark.TButton", command=self.add_preset).pack(fill="x", pady=4)
        ttk.Button(controls, text="<  Remove", style="Dark.TButton", command=self.remove_preset).pack(fill="x", pady=4)
        ttk.Button(controls, text="Move Up", style="Dark.TButton", command=lambda: self.move(-1)).pack(fill="x", pady=(24, 4))
        ttk.Button(controls, text="Move Down", style="Dark.TButton", command=lambda: self.move(1)).pack(fill="x", pady=4)

        right = tk.Frame(content, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=1, column=2, sticky="nsew")
        self.setlist_list = tk.Listbox(right, bg=CARD, fg=TEXT, selectbackground=ORANGE,
                                       selectforeground="white", relief="flat", exportselection=False)
        self.setlist_list.pack(fill="both", expand=True, padx=12, pady=12)
        self.setlist_list.bind("<Double-Button-1>", lambda _event: self.remove_preset())

    def refresh_names(self):
        self.name_combo["values"] = sorted(self.setlists, key=str.casefold)

    def refresh_library(self):
        self.library_list.delete(0, "end")
        for preset in self.filtered:
            self.library_list.insert("end", preset["name"])

    def filter_library(self):
        query = self.search_var.get().casefold()
        self.filtered = [preset for preset in self.presets if query in preset["name"].casefold()]
        self.refresh_library()

    def refresh_items(self, selected=None):
        self.setlist_list.delete(0, "end")
        for index, item in enumerate(self.current_items, 1):
            self.setlist_list.insert("end", f"{index:02d}.  {item['name']}")
        if selected is not None and self.current_items:
            selected = min(selected, len(self.current_items) - 1)
            self.setlist_list.selection_set(selected)
            self.setlist_list.see(selected)
        self.status_var.set(f"{len(self.current_items)} preset(s)")

    def add_preset(self):
        selection = self.library_list.curselection()
        if not selection:
            return
        preset = self.filtered[selection[0]]
        self.current_items.append({"name": preset["name"], "uuid": preset["uuid"], "path": str(preset["path"])})
        self.refresh_items(len(self.current_items) - 1)

    def remove_preset(self):
        selection = self.setlist_list.curselection()
        if selection:
            index = selection[0]
            del self.current_items[index]
            self.refresh_items(index)

    def move(self, direction):
        selection = self.setlist_list.curselection()
        if not selection:
            return
        old = selection[0]
        new = old + direction
        if 0 <= new < len(self.current_items):
            item = self.current_items.pop(old)
            self.current_items.insert(new, item)
            self.refresh_items(new)

    def new(self):
        if self.current_items and not messagebox.askyesno("New setlist", "Clear the current setlist?"):
            return
        self.current_name = None
        self.current_items = []
        self.name_var.set("")
        self.refresh_items()

    def load_selected(self, _event=None):
        name = self.name_var.get()
        if name:
            self.current_name = name
            self.current_items = [dict(item) for item in self.setlists.get(name, [])]
            self.refresh_items()

    def save(self):
        if not self.current_name:
            self.save_as()
            return
        self.setlists[self.current_name] = [dict(item) for item in self.current_items]
        self._write()

    def save_as(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Save setlist", "Setlist name:",
                                      initialvalue=self.current_name or "", parent=self.window)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.setlists and name != self.current_name:
            if not messagebox.askyesno("Replace setlist", f'Replace the existing setlist "{name}"?'):
                return
        self.current_name = name
        self.name_var.set(name)
        self.setlists[name] = [dict(item) for item in self.current_items]
        self._write()

    def _write(self):
        try:
            self.save_setlists()
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.refresh_names()
        self.status_var.set(f"Saved: {self.current_name}")

    def delete(self):
        if not self.current_name or not messagebox.askyesno("Delete setlist", f'Delete "{self.current_name}"?'):
            return
        del self.setlists[self.current_name]
        try:
            self.save_setlists()
        except OSError as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self.current_name = None
        self.current_items = []
        self.name_var.set("")
        self.refresh_names()
        self.refresh_items()

    def open_live_mode(self):
        if not self.current_items:
            messagebox.showinfo("Empty setlist", "Add at least one preset first.")
            return
        LiveMode(self.window, self.current_name or "Unsaved Setlist", self.current_items)


class LiveMode:
    def __init__(self, parent, name, items):
        self.items = items
        self.index = 0
        self.window = tk.Toplevel(parent)
        self.window.title(f"Live Mode - {name}")
        self.window.geometry("1000x650")
        self.window.configure(bg="#08090c")
        self.window.bind("<Right>", lambda _event: self.next())
        self.window.bind("<Down>", lambda _event: self.next())
        self.window.bind("<space>", lambda _event: self.next())
        self.window.bind("<Left>", lambda _event: self.previous())
        self.window.bind("<Up>", lambda _event: self.previous())
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.position = tk.Label(self.window, bg="#08090c", fg=MUTED, font=("Segoe UI", 18))
        self.position.pack(pady=(35, 15))
        self.current = tk.Label(self.window, bg="#08090c", fg=TEXT,
                                font=("Segoe UI Semibold", 48), wraplength=900)
        self.current.pack(fill="both", expand=True, padx=30)
        self.up_next = tk.Label(self.window, bg="#08090c", fg=GOLD,
                                font=("Segoe UI Semibold", 22), wraplength=900)
        self.up_next.pack(pady=(10, 25))
        controls = tk.Frame(self.window, bg="#08090c")
        controls.pack(pady=(0, 30))
        ttk.Button(controls, text="Previous", style="Dark.TButton", command=self.previous).pack(side="left", padx=8)
        ttk.Button(controls, text="Next", style="Gold.TButton", command=self.next).pack(side="left", padx=8)
        self.update()
        self.window.focus_set()

    def update(self):
        self.position.configure(text=f"{self.index + 1} of {len(self.items)}")
        self.current.configure(text=self.items[self.index]["name"])
        next_text = f"NEXT: {self.items[self.index + 1]['name']}" if self.index + 1 < len(self.items) else "END OF SETLIST"
        self.up_next.configure(text=next_text)

    def next(self):
        if self.index < len(self.items) - 1:
            self.index += 1
            self.update()

    def previous(self):
        if self.index > 0:
            self.index -= 1
            self.update()

    def toggle_fullscreen(self):
        self.window.attributes("-fullscreen", not bool(self.window.attributes("-fullscreen")))


class FilesystemUploaderPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.monitor_process = None
        self.terminal_window = None
        self.terminal_text = None
        self.log_buffer = []
        self.project_var = self.app.project_dir_var
        self.platformio_var = tk.StringVar(value=default_platformio())
        self.env_var = tk.StringVar(value="esp32dev")
        self.port_var = tk.StringVar()
        self.allow_missing_var = tk.BooleanVar(value=True)
        self.open_pdf_after_success = None
        self.heading("Filesystem Uploader", "Build and upload the Ignitron data folder without reflashing firmware.")
        self._build()
        self.load_project_defaults()

    @property
    def project_dir(self):
        return Path(self.project_var.get()).expanduser().resolve()

    @property
    def platformio_ini(self):
        return self.project_dir / "platformio.ini"

    @property
    def data_dir(self):
        return self.project_dir / "data"

    def _build(self):
        panel = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 30))

        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=20)
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="PROJECT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_project).grid(row=0, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="PLATFORMIO", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.platformio_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_platformio).grid(row=1, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="ENV", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        row = tk.Frame(controls, bg=SURFACE)
        row.grid(row=2, column=1, sticky="w", pady=5)
        self.env_combo = ttk.Combobox(row, textvariable=self.env_var, state="readonly", width=22)
        self.env_combo.pack(side="left")
        self.env_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_env_port())
        tk.Label(row, text="PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, width=24)
        self.port_combo.pack(side="left")
        ttk.Button(row, text="Refresh ports", style="Dark.TButton",
                   command=self.refresh_ports).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Use ini port", style="Dark.TButton",
                   command=self.load_env_port).pack(side="left", padx=(8, 0))

        options = tk.Frame(panel, bg=CARD)
        options.pack(fill="x", padx=22, pady=(0, 16))
        tk.Checkbutton(options, text="Allow upload when PresetList.txt references missing JSON files",
                       variable=self.allow_missing_var, bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=12)

        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(fill="x", padx=22, pady=(0, 16))
        self.validate_button = ttk.Button(actions, text="Validate data", style="Dark.TButton",
                                          command=self.validate_data)
        self.validate_button.pack(side="left")
        self.build_button = ttk.Button(actions, text="Build filesystem", style="Dark.TButton",
                                       command=lambda: self.run_targets(["buildfs"]))
        self.build_button.pack(side="left", padx=(8, 0))
        self.upload_button = ttk.Button(actions, text="Upload filesystem", style="Dark.TButton",
                                        command=lambda: self.run_targets(["uploadfs"]))
        self.upload_button.pack(side="left", padx=(8, 0))
        self.both_button = ttk.Button(actions, text="Build + upload", style="Gold.TButton",
                                      command=lambda: self.run_targets(["buildfs", "uploadfs"]))
        self.both_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open data folder", style="Dark.TButton",
                   command=self.open_data_folder).pack(side="right")

        log_header = tk.Frame(panel, bg=SURFACE)
        log_header.pack(fill="x", padx=22)
        tk.Label(log_header, text="PLATFORMIO OUTPUT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(log_header, text="Clear log", style="Dark.TButton", command=self.clear_log).pack(side="right")
        self.log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=22, pady=(10, 22))

    def choose_project(self):
        folder = filedialog.askdirectory(title="Select Ignitron PlatformIO project", initialdir=self.project_var.get())
        if folder:
            self.app.set_project_dir(folder)
            self.load_project_defaults()

    def choose_platformio(self):
        filename = filedialog.askopenfilename(
            title="Select platformio.exe",
            initialdir=str(Path.home()),
            filetypes=(("Executables", "*.exe"), ("All files", "*.*")),
        )
        if filename:
            self.platformio_var.set(filename)

    def load_project_defaults(self):
        envs = parse_platformio_envs(self.platformio_ini)
        self.env_combo.configure(values=envs)
        if self.env_var.get() not in envs:
            self.env_var.set(envs[0])
        self.refresh_ports(select_first=False)
        self.load_env_port()
        self.app.set_status(f"Filesystem uploader ready: {self.project_dir}")

    def on_project_changed(self):
        self.load_project_defaults()

    def load_env_port(self):
        port = parse_platformio_upload_port(self.platformio_ini, self.env_var.get())
        if port:
            self.port_var.set(port)

    def refresh_ports(self, select_first=True):
        current = self.port_var.get().strip()
        values = []
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            values = [f"{port.device}  |  {port.description}" for port in ports]
        except ImportError:
            values = []
        self.port_combo.configure(values=values)
        devices = [value.split("  |  ", 1)[0].strip() for value in values]
        if current in devices:
            self.port_var.set(current)
        elif select_first and values:
            self.port_var.set(devices[0])
        self.app.set_status(f"Found {len(values)} serial port(s)" if values else "No serial ports found")

    def selected_port(self):
        return self.port_var.get().split("  |  ", 1)[0].strip()

    def prepare_upload_after_builder_export(self):
        self.refresh_ports(select_first=True)
        if self.selected_port():
            self.app.set_status("Preset files exported. Choose the COM port, then click Upload filesystem.")
        else:
            self.app.set_status("Preset files exported. Connect Ignitron, refresh ports, then click Upload filesystem.")
            messagebox.showinfo(
                "Select COM port",
                "Preset files were exported.\n\nConnect Ignitron, choose its COM port on the Upload FS page, "
                "then click Upload filesystem or Build + upload.",
            )

    def open_data_folder(self):
        if self.data_dir.exists():
            open_folder(self.data_dir)
        else:
            messagebox.showerror("Data folder not found", f"No data folder exists at:\n{self.data_dir}")

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log_buffer.append(text)
        if len(self.log_buffer) > 1200:
            self.log_buffer = self.log_buffer[-1200:]
        terminal = getattr(self, "terminal_text", None)
        if terminal is not None and terminal.winfo_exists():
            terminal.configure(state="normal")
            terminal.insert("end", text)
            terminal.see("end")
            terminal.configure(state="disabled")

    def clear_log(self):
        self.log_buffer.clear()
        terminal = getattr(self, "terminal_text", None)
        if terminal is not None and terminal.winfo_exists():
            terminal.configure(state="normal")
            terminal.delete("1.0", "end")
            terminal.configure(state="disabled")

    def show_terminal(self):
        window = getattr(self, "terminal_window", None)
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Ignitron PlatformIO Terminal")
        window.configure(bg=BG)
        window.geometry("1120x520")
        self.terminal_window = window

        header = tk.Frame(window, bg=SURFACE)
        header.pack(fill="x")
        tk.Label(header, text="PLATFORMIO TERMINAL", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=16, pady=12)
        ttk.Button(header, text="Clear", style="Dark.TButton", command=self.clear_log).pack(side="right", padx=(0, 12), pady=8)
        ttk.Button(header, text="Hide", style="Dark.TButton", command=window.withdraw).pack(side="right", padx=(0, 8), pady=8)

        terminal = tk.Text(window, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        terminal.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.terminal_text = terminal

        def on_close():
            window.withdraw()

        window.protocol("WM_DELETE_WINDOW", on_close)
        terminal.configure(state="normal")
        terminal.insert("1.0", "".join(self.log_buffer))
        terminal.see("end")
        terminal.configure(state="disabled")

    def set_busy(self, busy):
        self.running = busy
        state = "disabled" if busy else "normal"
        for button in (self.validate_button, self.build_button, self.upload_button, self.both_button):
            button.configure(state=state)

    def validate_data(self, show_success=True):
        if not self.project_dir.exists():
            messagebox.showerror("Project not found", f"Project folder does not exist:\n{self.project_dir}")
            return False
        if not self.platformio_ini.exists():
            messagebox.showerror("platformio.ini not found", f"Missing file:\n{self.platformio_ini}")
            return False
        if not self.data_dir.exists():
            messagebox.showerror("Data folder not found", f"Missing folder:\n{self.data_dir}")
            return False

        json_count = len(list(self.data_dir.glob("*.json")))
        missing = preset_list_missing_files(self.data_dir)
        if missing:
            message = (
                f"Data folder: {self.data_dir}\n"
                f"JSON presets: {json_count}\n\n"
                "PresetList.txt references missing files:\n"
                + "\n".join(missing[:45])
            )
            if len(missing) > 45:
                message += f"\n...and {len(missing) - 45} more"
            if not self.allow_missing_var.get():
                messagebox.showerror("PresetList check failed", message)
                return False
            if show_success:
                messagebox.showwarning("PresetList warning", message)
            self.app.set_status(f"Data warning: {len(missing)} missing referenced file(s)")
            return True

        if show_success:
            messagebox.showinfo(
                "Data looks good",
                f"Data folder: {self.data_dir}\nJSON presets: {json_count}\n\nPresetList.txt references all required files.",
            )
        self.app.set_status(f"Data validated: {json_count} JSON preset file(s)")
        return True

    def run_targets(self, targets):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A filesystem task is already running.")
            return
        if not self.validate_data(show_success=False):
            return
        if "uploadfs" in targets and not self.selected_port():
            self.refresh_ports(select_first=True)
            if not self.selected_port():
                messagebox.showinfo("Select COM port", "Choose the Ignitron COM port before uploading the filesystem.")
                return
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Running PlatformIO filesystem task...")
        threading.Thread(target=self._run_targets_worker, args=(targets,), daemon=True).start()

    def _run_targets_worker(self, targets):
        try:
            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    self.append_log(f"\n{target} failed with exit code {code}\n")
                    self.after(0, lambda t=target: self.app.set_status(f"{t} failed"))
                    return
            self.append_log("\nFilesystem task complete.\n")
            self.after(0, lambda: self.app.set_status("Filesystem upload workflow complete"))
            self.open_pdf_after_success = None
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_platformio_target(self, target):
        cmd = [
            self.platformio_var.get(),
            "run",
            "-e",
            self.env_var.get(),
            "-t",
            target,
        ]
        port = self.selected_port()
        if target == "uploadfs" and port:
            cmd.extend(["--upload-port", port])

        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            process = run_hidden_subprocess(cmd, self.project_dir)
        except Exception as exc:
            self.append_log(f"Could not start PlatformIO: {exc}\n")
            return 1

        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(line)
        return process.wait()


class FirmwareUploadPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.monitor_process = None
        self.terminal_window = None
        self.terminal_text = None
        self.log_buffer = []
        self.project_var = self.app.project_dir_var
        self.platformio_var = tk.StringVar(value=default_platformio())
        self.env_var = tk.StringVar(value="esp32dev")
        self.port_var = tk.StringVar()
        self.speed_var = tk.StringVar(value=DEFAULT_UPLOAD_SPEED)
        self.clean_var = tk.BooleanVar(value=True)
        self.erase_var = tk.BooleanVar(value=True)
        self.allow_missing_var = tk.BooleanVar(value=True)
        self.open_pdf_after_success = None
        self.fw_version_var = tk.StringVar()
        self.oled_driver_choices = {
            "OLED_DRIVER_SSD1306 - 1.3 inch": "OLED_DRIVER_SSD1306",
            "OLED_DRIVER_SSD1309 - 2.42 inch": "OLED_DRIVER_SSD1309",
            "OLED_DRIVER_SH1106 - 1.3 inch": "OLED_DRIVER_SH1106",
            "OLED_DRIVER_SH1107 - 1.5 inch": "OLED_DRIVER_SH1107",
        }
        self.oled_driver_labels_by_define = {value: label for label, value in self.oled_driver_choices.items()}
        self.oled_driver_var = tk.StringVar(value=self.oled_driver_labels_by_define["OLED_DRIVER_SH1106"])
        self.battery_enabled_var = tk.BooleanVar(value=True)
        self.battery_type_var = tk.StringVar(value="BATTERY_TYPE_LI_ION")
        self.battery_cells_var = tk.StringVar(value="2")
        self.battery_adc_pin_var = tk.StringVar(value="36")
        self.battery_r1_var = tk.StringVar(value="22")
        self.battery_r2_var = tk.StringVar(value="10")
        self.fx_blink_var = tk.BooleanVar(value=False)
        self.amp_mode_rocker_switch_var = tk.BooleanVar(value=True)
        self.amp_mode_rocker_pin_var = tk.StringVar(value="35")
        self.dedicated_leds_var = tk.BooleanVar(value=False)
        self.long_press_var = tk.StringVar(value="1000")
        self.ipt_setup_status_var = tk.StringVar(value="Check the selected firmware project for IPT 2.0 support.")
        self.ipt_setup_detail_var = tk.StringVar(value="")
        self.heading("Firmware + Filesystem", "Build firmware and upload the Ignitron data filesystem from one section.")
        self._build()
        self.load_project_defaults()

    @property
    def project_dir(self):
        return Path(self.project_var.get()).expanduser().resolve()

    @property
    def platformio_ini(self):
        return self.project_dir / "platformio.ini"

    @property
    def firmware_config_path(self):
        return self.project_dir / "src" / "Config_Definitions.h"

    @property
    def data_dir(self):
        return self.project_dir / "data"

    def _build(self):
        notebook = ttk.Notebook(self)
        self.notebook = notebook
        notebook.pack(fill="both", expand=True, padx=34, pady=(0, 30))

        firmware_tab = tk.Frame(notebook, bg=BG)
        setup_tab = tk.Frame(notebook, bg=BG)
        self.ipt_setup_tab = setup_tab
        notebook.add(firmware_tab, text="Firmware")
        notebook.add(setup_tab, text="IPT 2.0 Setup")

        panel = tk.Frame(firmware_tab, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)

        tk.Label(panel, text="PROJECT / PLATFORMIO", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22, pady=(18, 0))
        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=(10, 14))
        controls.grid_columnconfigure(1, weight=1)

        tk.Label(controls, text="PROJECT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_project).grid(row=0, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="PLATFORMIO", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(controls, textvariable=self.platformio_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(controls, text="Browse", style="Dark.TButton",
                   command=self.choose_platformio).grid(row=1, column=2, padx=(10, 0), pady=5)

        tk.Label(controls, text="ENV", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=2, column=0, sticky="w", padx=(0, 10), pady=5)
        row = tk.Frame(controls, bg=SURFACE)
        row.grid(row=2, column=1, sticky="w", pady=5)
        self.env_combo = ttk.Combobox(row, textvariable=self.env_var, state="readonly", width=20)
        self.env_combo.pack(side="left")
        self.env_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_env_defaults())
        tk.Label(row, text="PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var, width=24)
        self.port_combo.pack(side="left")
        self.port_combo.bind("<<ComboboxSelected>>", lambda _event: self.write_env_upload_port(show_status=True))
        ttk.Button(row, text="Refresh ports", style="Dark.TButton",
                   command=self.refresh_ports).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Save port", style="Dark.TButton",
                   command=lambda: self.write_env_upload_port(show_status=True)).pack(side="left", padx=(8, 0))
        tk.Label(row, text="SPEED", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=(18, 8))
        ttk.Combobox(
            row,
            textvariable=self.speed_var,
            values=("115200", "460800", "921600"),
            width=10,
        ).pack(side="left")

        firmware_body = tk.Frame(panel, bg=SURFACE)
        firmware_body.pack(fill="x", padx=22, pady=(0, 14))
        firmware_body.grid_columnconfigure(0, weight=1)
        firmware_body.grid_columnconfigure(1, weight=1)

        options = tk.Frame(firmware_body, bg=CARD)
        options.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(options, text="UPLOAD OPTIONS", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=16, pady=(12, 0))
        for label, var in (
            ("Clean before build", self.clean_var),
            ("Erase flash before upload", self.erase_var),
        ):
            tk.Checkbutton(options, text=label, variable=var, bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                           activebackground=CARD, activeforeground=TEXT,
                           font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(8, 0))

        data_options = tk.Frame(firmware_body, bg=CARD)
        data_options.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(data_options, text="DATA / FILESYSTEM", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Checkbutton(data_options, text="Allow filesystem upload when PresetList.txt references missing JSON files",
                       variable=self.allow_missing_var, bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9), wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(8, 12))

        actions = tk.Frame(panel, bg=SURFACE)
        actions.pack(fill="x", padx=22, pady=(0, 14))
        tk.Label(actions, text="ACTIONS", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(0, 8))
        action_buttons = tk.Frame(actions, bg=SURFACE)
        action_buttons.pack(fill="x")
        self.flash_button = ttk.Button(action_buttons, text="Build + Flash FW + FS", style="Gold.TButton",
                                       command=self.run_flash_workflow)
        self.flash_button.pack(side="left")
        self.upload_fw_button = ttk.Button(action_buttons, text="Upload firmware to this pedal", style="Dark.TButton",
                                           command=self.run_firmware_upload_workflow)
        self.upload_fw_button.pack(side="left", padx=(18, 0))
        self.validate_fs_button = ttk.Button(action_buttons, text="Validate data", style="Dark.TButton",
                                             command=self.validate_data)
        self.validate_fs_button.pack(side="left", padx=(8, 0))
        self.fs_button = ttk.Button(action_buttons, text="Build + Upload FS Only", style="Dark.TButton",
                                    command=self.run_filesystem_workflow)
        self.fs_button.pack(side="left", padx=(8, 0))
        self.monitor_button = ttk.Button(action_buttons, text="Monitor", style="Dark.TButton",
                                         command=self.run_monitor_workflow)
        self.monitor_button.pack(side="left", padx=(8, 0))
        self.stop_monitor_button = ttk.Button(action_buttons, text="Stop monitor", style="Dark.TButton",
                                              command=self.stop_monitor)
        self.stop_monitor_button.pack(side="left", padx=(8, 0))
        self.stop_monitor_button.configure(state="disabled")
        ttk.Button(action_buttons, text="Terminal", style="Dark.TButton",
                   command=self.show_terminal).pack(side="left", padx=(8, 0))
        ttk.Button(action_buttons, text="Open project", style="Dark.TButton",
                   command=lambda: open_folder(self.project_dir)).pack(side="right")
        ttk.Button(action_buttons, text="Open data", style="Dark.TButton",
                   command=self.open_data_folder).pack(side="right", padx=(0, 8))
        ttk.Button(action_buttons, text="Open PresetList PDF", style="Dark.TButton",
                   command=self.open_current_pdf).pack(side="right", padx=(0, 8))

        settings_section = tk.Frame(panel, bg=SURFACE)
        settings_section.pack(fill="x", padx=22, pady=(0, 14))
        tk.Label(settings_section, text="FIRMWARE SETTINGS", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(0, 8))
        self._build_settings_tab(settings_section, embedded=True)

        info = tk.Frame(panel, bg=CARD)
        info.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(
            info,
            text="Firmware tasks open a terminal popup automatically. Selected env, port, and speed are saved to platformio.ini before upload. 460800 is the reliable default.",
            bg=CARD,
            fg=MUTED,
            justify="left",
            wraplength=950,
            font=("Segoe UI", 9),
            padx=16,
            pady=12,
        ).pack(anchor="w")

        self._build_ipt_setup_tab(setup_tab)

    def _build_settings_tab(self, parent, embedded=False):
        if embedded:
            panel = tk.Frame(parent, bg=CARD)
            panel.pack(fill="x")
        else:
            panel = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
            panel.pack(fill="both", expand=True)

        section_bg = CARD if embedded else SURFACE
        top = tk.Frame(panel, bg=section_bg)
        top.pack(fill="x", padx=16 if embedded else 22, pady=(12, 10) if embedded else 20)
        tk.Label(top, text="CONFIG FILE", bg=section_bg, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.config_path_var = tk.StringVar(value=str(self.firmware_config_path))
        ttk.Entry(top, textvariable=self.config_path_var).pack(side="left", fill="x", expand=True, padx=12)
        ttk.Button(top, text="Reload", style="Dark.TButton", command=self.load_firmware_settings).pack(side="left")
        ttk.Button(top, text="Open config", style="Dark.TButton",
                   command=lambda: open_folder(self.firmware_config_path.parent)).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Save settings", style="Gold.TButton",
                   command=self.save_firmware_settings).pack(side="right")

        grid = tk.Frame(panel, bg=section_bg)
        grid.pack(fill="x", padx=16 if embedded else 22, pady=(0, 8 if embedded else 16))
        for column in range(6):
            grid.grid_columnconfigure(column, weight=1)

        self._setting_label(grid, "Firmware version", 0, 0, bg=section_bg)
        ttk.Entry(grid, textvariable=self.fw_version_var, width=18).grid(row=1, column=0, sticky="w", padx=(0, 18), pady=(0, 8))

        self._setting_label(grid, "OLED driver", 0, 1, bg=section_bg)
        ttk.Combobox(
            grid,
            textvariable=self.oled_driver_var,
            state="readonly",
            values=tuple(self.oled_driver_choices.keys()),
            width=34,
        ).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(0, 8))

        self._setting_label(grid, "Long press ms", 0, 2, bg=section_bg)
        ttk.Entry(grid, textvariable=self.long_press_var, width=12).grid(row=1, column=2, sticky="w", padx=(0, 18), pady=(0, 8))

        tk.Checkbutton(grid, text="FX blink", variable=self.fx_blink_var,
                       bg=section_bg, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=section_bg, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=1, column=3, sticky="w", pady=(14, 8))

        tk.Checkbutton(grid, text="AMP mode rocker switch installed", variable=self.amp_mode_rocker_switch_var,
                       bg=section_bg, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=section_bg, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=1, column=4, sticky="w", pady=(14, 8))
        self._setting_label(grid, "Rocker GPIO", 0, 5, bg=section_bg)
        ttk.Entry(grid, textvariable=self.amp_mode_rocker_pin_var, width=10).grid(
            row=1, column=5, sticky="w", padx=(0, 18), pady=(0, 8)
        )

        battery = tk.Frame(panel, bg=section_bg)
        battery.pack(fill="x", padx=16 if embedded else 22, pady=(0, 8 if embedded else 16))
        tk.Label(battery, text="BATTERY", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=0, column=0, sticky="w", padx=16, pady=(10, 6))
        tk.Checkbutton(battery, text="Enable battery status", variable=self.battery_enabled_var,
                       bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
        tk.Label(battery, text="Type", bg=CARD, fg=MUTED,
                 font=("Segoe UI Semibold", 8)).grid(row=0, column=1, sticky="w", padx=8, pady=(10, 6))
        ttk.Combobox(
            battery,
            textvariable=self.battery_type_var,
            state="readonly",
            values=("BATTERY_TYPE_LI_ION", "BATTERY_TYPE_LI_FE_PO4", "BATTERY_TYPE_AMP"),
            width=24,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(0, 8))
        for label, var, col, width in (
            ("Cells", self.battery_cells_var, 2, 8),
            ("ADC pin", self.battery_adc_pin_var, 3, 8),
            ("R1 kohm", self.battery_r1_var, 4, 10),
            ("R2 kohm", self.battery_r2_var, 5, 10),
        ):
            tk.Label(battery, text=label, bg=CARD, fg=MUTED,
                     font=("Segoe UI Semibold", 8)).grid(row=0, column=col, sticky="w", padx=8, pady=(10, 6))
            ttk.Entry(battery, textvariable=var, width=width).grid(row=1, column=col, sticky="w", padx=8, pady=(0, 8))

        note = tk.Frame(panel, bg=section_bg)
        note.pack(fill="x", padx=16 if embedded else 22, pady=(0, 8 if embedded else 16))
        tk.Checkbutton(note, text="Dedicated preset LEDs", variable=self.dedicated_leds_var,
                       bg=CARD, fg=TEXT, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(side="left", padx=(16, 18), pady=10)
        tk.Label(
            note,
            text="These settings modify src\\Config_Definitions.h. Build + Flash automatically writes the current settings before upload. Only one OLED driver is enabled at a time.",
            bg=CARD,
            fg=MUTED,
            justify="left",
            wraplength=1050,
            font=("Segoe UI", 9),
            padx=0,
            pady=10,
        ).pack(side="left", anchor="w")

    def _setting_label(self, parent, text, row, column, bg=SURFACE):
        tk.Label(parent, text=text.upper(), bg=bg, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).grid(row=row, column=column, sticky="w", padx=(0, 18), pady=(0, 6))

    def _build_ipt_setup_tab(self, parent):
        panel = tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True)

        top = tk.Frame(panel, bg=SURFACE)
        top.pack(fill="x", padx=22, pady=20)
        tk.Label(top, text="IPT 2.0 FIRMWARE SUPPORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        ttk.Button(top, text="Check support", style="Dark.TButton",
                   command=self.check_ipt_addon_support).pack(side="right")
        ttk.Button(top, text="Install IPT 2.0 support", style="Gold.TButton",
                   command=self.install_ipt_addon_support).pack(side="right", padx=(0, 8))

        status = tk.Frame(panel, bg=CARD)
        status.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(status, textvariable=self.ipt_setup_status_var, bg=CARD, fg=TEXT,
                 font=("Segoe UI Semibold", 11), padx=16, pady=10).pack(anchor="w")
        tk.Label(status, textvariable=self.ipt_setup_detail_var, bg=CARD, fg=MUTED,
                 justify="left", wraplength=980, font=("Segoe UI", 9),
                 padx=16).pack(anchor="w", pady=(0, 12))

        note = tk.Frame(panel, bg=CARD)
        note.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(
            note,
            text=(
                "This setup checks the selected PlatformIO firmware project for IPT 2.0 serial support: "
                "remote preset selection, hardware preset save/select, Spark 2 looper commands, tuner stream hooks, "
                "Spark Capture pedal-backup list/dump commands, app preset streaming, and app status events. "
                "Install replaces the selected firmware files with the vetted v2.0 support files."
            ),
            bg=CARD,
            fg=MUTED,
            justify="left",
            wraplength=980,
            font=("Segoe UI", 9),
            padx=16,
            pady=12,
        ).pack(anchor="w")

        self.ipt_setup_log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                                     relief="flat", highlightthickness=1, highlightbackground=BORDER,
                                     font=("Consolas", 9), wrap="word", height=14, state="disabled")
        self.ipt_setup_log.pack(fill="both", expand=True, padx=22, pady=(0, 22))

    def show_ipt_setup_tab(self):
        try:
            self.notebook.select(self.ipt_setup_tab)
        except Exception:
            pass
        self.check_ipt_addon_support(show_message=False)

    def choose_project(self):
        folder = filedialog.askdirectory(title="Select Ignitron PlatformIO project", initialdir=self.project_var.get())
        if folder:
            self.app.set_project_dir(folder)
            self.load_project_defaults()

    def choose_platformio(self):
        filename = filedialog.askopenfilename(
            title="Select platformio.exe",
            initialdir=str(Path.home()),
            filetypes=(("Executables", "*.exe"), ("All files", "*.*")),
        )
        if filename:
            self.platformio_var.set(filename)

    def load_project_defaults(self):
        envs = parse_platformio_envs(self.platformio_ini)
        self.env_combo.configure(values=envs)
        if self.env_var.get() not in envs:
            self.env_var.set(envs[0])
        self.refresh_ports(select_first=False)
        self.load_env_defaults()
        self.config_path_var.set(str(self.firmware_config_path))
        self.load_firmware_settings(show_errors=False)
        self.check_ipt_addon_support(show_message=False)

    def load_env_defaults(self):
        port = parse_platformio_upload_port(self.platformio_ini, self.env_var.get())
        if port:
            self.port_var.set(port)
        speed = parse_platformio_env_value(self.platformio_ini, self.env_var.get(), "upload_speed", DEFAULT_UPLOAD_SPEED)
        self.speed_var.set(speed or DEFAULT_UPLOAD_SPEED)
        self.app.set_status(f"Firmware + filesystem ready: {self.project_dir}")

    def on_project_changed(self):
        self.load_project_defaults()

    def bundled_firmware_dir(self):
        return resource_path("Ignitron")

    def _write_ipt_setup_log(self, text):
        log = getattr(self, "ipt_setup_log", None)
        if not log:
            return
        log.configure(state="normal")
        log.delete("1.0", "end")
        log.insert("end", text)
        log.configure(state="disabled")

    def inspect_ipt_addon_support(self):
        return inspect_ipt_addon_support(self.project_dir)

    def check_ipt_addon_support(self, show_message=True):
        if not self.project_dir.exists() or not self.platformio_ini.exists():
            self.ipt_setup_status_var.set("Select a valid PlatformIO firmware project.")
            self.ipt_setup_detail_var.set("The project must contain platformio.ini and the Ignitron source files.")
            self._write_ipt_setup_log(f"Project not ready:\n{self.project_dir}\n")
            return False
        missing_files, missing_markers = self.inspect_ipt_addon_support()
        if not missing_markers:
            self.ipt_setup_status_var.set("IPT 2.0 support is installed.")
            self.ipt_setup_detail_var.set("Remote preset control, hardware preset save/select, Spark 2 looper, tuner stream, and app status events were found.")
            self._write_ipt_setup_log(
                "IPT 2.0 support check passed.\n\n"
                + "\n".join(f"OK  {label}  ({rel_path})" for rel_path, label, _marker in IPT_ADDON_MARKERS)
                + "\n"
            )
            if show_message:
                self.app.set_status("IPT 2.0 firmware support is installed")
            return True

        lines = ["IPT 2.0 support check found missing items.", ""]
        if missing_files:
            lines.append("Missing files:")
            lines.extend(f"MISS {rel_path}" for rel_path in sorted(set(missing_files)))
            lines.append("")
        lines.append("Missing support markers:")
        lines.extend(f"MISS {label}  ({rel_path})" for rel_path, label, _marker in missing_markers)
        self.ipt_setup_status_var.set("IPT 2.0 support is incomplete.")
        self.ipt_setup_detail_var.set(f"{len(missing_markers)} support item(s) are missing. Use Install IPT 2.0 support to add the v2.0 addon files with backups.")
        self._write_ipt_setup_log("\n".join(lines) + "\n")
        if show_message:
            self.app.set_status("IPT 2.0 firmware support is incomplete")
        return False

    def install_ipt_addon_support(self):
        if self.running:
            messagebox.showinfo("PlatformIO running", "Wait for the current firmware task to finish first.")
            return
        if not self.project_dir.exists() or not self.platformio_ini.exists():
            messagebox.showerror("Project not found", f"Select a valid PlatformIO project first:\n{self.project_dir}")
            return
        source_root = self.bundled_firmware_dir()
        if not source_root.exists():
            messagebox.showerror("Bundled firmware not found", f"Missing bundled firmware folder:\n{source_root}")
            return
        support_files = ipt_addon_files(source_root)
        missing_sources = [rel_path for rel_path in support_files if not (source_root / rel_path).exists()]
        if missing_sources:
            messagebox.showerror("IPT support source missing", "Missing bundled support file(s):\n" + "\n".join(missing_sources))
            return

        already_installed = self.check_ipt_addon_support(show_message=False)
        if already_installed and not messagebox.askyesno(
                "IPT 2.0 support already installed",
                "The selected firmware already appears to have IPT 2.0 support. Reinstall the support files anyway?"):
            return

        if not messagebox.askyesno(
                "Install IPT 2.0 support",
                "This will replace the IPT-supported firmware files in the selected project.\n\n"
                f"Project:\n{self.project_dir}\n\nContinue?"):
            return

        copied = []
        try:
            for rel_path in support_files:
                src = source_root / rel_path
                dst = self.project_dir / rel_path
                try:
                    if src.resolve() == dst.resolve():
                        copied.append(f"{rel_path} (already source)")
                        continue
                except Exception:
                    pass
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel_path)
            self.write_platformio_section_value("platformio", "src_dir", "src")
        except Exception as exc:
            messagebox.showerror("Install failed", f"Could not install IPT 2.0 support:\n{exc}")
            self.app.set_status("IPT 2.0 support install failed")
            return

        self.load_firmware_settings(show_errors=False)
        self.check_ipt_addon_support(show_message=False)
        log_lines = [
            "Installed IPT 2.0 support files.",
            f"Source: {source_root}",
            f"Project: {self.project_dir}",
            "",
            "Copied files:",
            *[f"OK  {rel_path}" for rel_path in copied],
            "",
            "Build firmware before flashing the pedal.",
        ]
        self._write_ipt_setup_log("\n".join(log_lines) + "\n")
        self.app.set_status("IPT 2.0 firmware support installed")
        self.app.update_firmware_mod_indicators()
        messagebox.showinfo("IPT 2.0 support installed", "Support files were installed.")

    def _config_text(self):
        return self.firmware_config_path.read_text(encoding="utf-8", errors="replace")

    def _is_define_enabled(self, text, name):
        return re.search(rf"^\s*#define\s+{re.escape(name)}\b", text, re.MULTILINE) is not None

    def _extract_define_value(self, text, name, default=""):
        match = re.search(rf"^\s*#define\s+{re.escape(name)}\s+([^\r\n/]+)", text, re.MULTILINE)
        return match.group(1).strip() if match else default

    def _extract_const_value(self, text, ctype, name, default=""):
        match = re.search(rf"^\s*const\s+{ctype}\s+{re.escape(name)}\s*=\s*([^;\r\n]+);", text, re.MULTILINE)
        return match.group(1).strip() if match else default

    def load_firmware_settings(self, show_errors=True):
        path = self.firmware_config_path
        if not path.exists():
            if show_errors:
                messagebox.showerror("Config not found", f"Missing firmware config:\n{path}")
            return False
        text = self._config_text()
        self.config_path_var.set(str(path))
        self.fw_version_var.set(self._extract_const_value(text, "string", "VERSION", "\"\"").strip('"'))
        for driver in ("OLED_DRIVER_SSD1306", "OLED_DRIVER_SSD1309", "OLED_DRIVER_SH1106", "OLED_DRIVER_SH1107"):
            if self._is_define_enabled(text, driver):
                self.oled_driver_var.set(self.oled_driver_labels_by_define.get(driver, driver))
                break
        self.battery_enabled_var.set(self._is_define_enabled(text, "ENABLE_BATTERY_STATUS_INDICATOR"))
        self.battery_type_var.set(self._extract_define_value(text, "BATTERY_TYPE", "BATTERY_TYPE_LI_ION"))
        self.battery_cells_var.set(self._extract_const_value(text, "int", "BATTERY_CELLS", "2"))
        self.battery_adc_pin_var.set(self._extract_const_value(text, "int", "BATTERY_VOLTAGE_ADC_PIN", "36"))
        self.battery_r1_var.set(self._resistor_to_kohm(self._extract_const_value(text, "float", "VOLTAGE_DIVIDER_R1", "(22 * 1000)")))
        self.battery_r2_var.set(self._resistor_to_kohm(self._extract_const_value(text, "float", "VOLTAGE_DIVIDER_R2", "(10 * 1000)")))
        self.fx_blink_var.set(self._extract_const_value(text, "bool", "ENABLE_FX_BLINK", "false").lower() == "true")
        self.amp_mode_rocker_switch_var.set(self._is_define_enabled(text, "ENABLE_AMP_MODE_ROCKER_SWITCH"))
        self.amp_mode_rocker_pin_var.set(self._extract_const_value(text, "int", "AMP_MODE_SWITCH_PIN", "35"))
        self.dedicated_leds_var.set(self._is_define_enabled(text, "DEDICATED_PRESET_LEDS"))
        self.long_press_var.set(self._extract_const_value(text, "int", "LONG_BUTTON_PRESS_TIME", "1000"))
        self.app.set_status(f"Loaded firmware settings from {path}")
        return True

    def _resistor_to_kohm(self, value):
        match = re.search(r"([0-9.]+)\s*\*\s*1000", value)
        if match:
            return match.group(1)
        try:
            return str(float(value.strip("()")) / 1000.0)
        except Exception:
            return value

    def _validate_number(self, label, value, allow_float=False):
        try:
            number = float(value) if allow_float else int(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number") from exc
        if number <= 0:
            raise ValueError(f"{label} must be greater than zero")
        return number

    def save_firmware_settings(self, show_message=True):
        path = self.firmware_config_path
        if not path.exists():
            if show_message:
                messagebox.showerror("Config not found", f"Missing firmware config:\n{path}")
            else:
                self.append_log(f"Missing firmware config: {path}\n")
            return False
        try:
            self._validate_number("Battery cells", self.battery_cells_var.get())
            self._validate_number("Battery ADC pin", self.battery_adc_pin_var.get())
            self._validate_number("R1 kohm", self.battery_r1_var.get(), allow_float=True)
            self._validate_number("R2 kohm", self.battery_r2_var.get(), allow_float=True)
            self._validate_number("Long press time", self.long_press_var.get())
            self._validate_number("Rocker GPIO", self.amp_mode_rocker_pin_var.get())
        except ValueError as exc:
            if show_message:
                messagebox.showerror("Invalid firmware setting", str(exc))
            else:
                self.append_log(f"Invalid firmware setting: {exc}\n")
            return False

        text = self._config_text()
        text = self._set_string_const(text, "VERSION", self.fw_version_var.get().strip() or "1.9.4")
        text = self._set_define_enabled(text, "ENABLE_BATTERY_STATUS_INDICATOR", self.battery_enabled_var.get())
        selected_oled_driver = self.oled_driver_choices.get(self.oled_driver_var.get(), self.oled_driver_var.get())
        for driver in ("OLED_DRIVER_SSD1306", "OLED_DRIVER_SSD1309", "OLED_DRIVER_SH1106", "OLED_DRIVER_SH1107"):
            text = self._set_define_enabled(text, driver, driver == selected_oled_driver)
        text = self._set_define_value(text, "BATTERY_TYPE", self.battery_type_var.get())
        text = self._set_const_value(text, "int", "BATTERY_CELLS", self.battery_cells_var.get().strip())
        text = self._set_const_value(text, "int", "BATTERY_VOLTAGE_ADC_PIN", self.battery_adc_pin_var.get().strip())
        text = self._set_const_value(text, "float", "VOLTAGE_DIVIDER_R1", f"({self.battery_r1_var.get().strip()} * 1000)")
        text = self._set_const_value(text, "float", "VOLTAGE_DIVIDER_R2", f"({self.battery_r2_var.get().strip()} * 1000)")
        text = self._set_const_value(text, "bool", "ENABLE_FX_BLINK", "true" if self.fx_blink_var.get() else "false")
        text = self._set_define_enabled(text, "ENABLE_AMP_MODE_ROCKER_SWITCH", self.amp_mode_rocker_switch_var.get())
        text = self._set_const_value(text, "int", "AMP_MODE_SWITCH_PIN", self.amp_mode_rocker_pin_var.get().strip())
        text = self._set_define_enabled(text, "DEDICATED_PRESET_LEDS", self.dedicated_leds_var.get())
        text = self._set_const_value(text, "int", "LONG_BUTTON_PRESS_TIME", self.long_press_var.get().strip())

        path.write_text(text, encoding="utf-8")
        self.app.set_status(f"Saved firmware settings to {path}")
        self.append_log(f"Saved firmware settings to {path}\n")
        if show_message:
            messagebox.showinfo("Firmware settings saved", f"Updated:\n{path}")
        return True

    def _set_define_enabled(self, text, name, enabled):
        pattern = rf"^(\s*)(//\s*)?#define\s+{re.escape(name)}\b(.*)$"
        replacement = rf"\1#define {name}\3" if enabled else rf"\1// #define {name}\3"
        new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        line = f"#define {name}" if enabled else f"// #define {name}"
        return self._insert_config_line(text, line)

    def _set_define_value(self, text, name, value):
        pattern = rf"^(\s*#define\s+{re.escape(name)}\s+)([^\r\n/]+)(.*)$"
        new_text, count = re.subn(pattern, rf"\g<1>{value}\3", text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        return self._insert_config_line(text, f"#define {name} {value}")

    def _set_const_value(self, text, ctype, name, value):
        pattern = rf"^(\s*const\s+{ctype}\s+{re.escape(name)}\s*=\s*)([^;\r\n]+)(;.*)$"
        new_text, count = re.subn(pattern, rf"\g<1>{value}\3", text, count=1, flags=re.MULTILINE)
        if count:
            return new_text
        return self._insert_config_line(text, f"const {ctype} {name} = {value};")

    def _set_string_const(self, text, name, value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return self._set_const_value(text, "string", name, f'"{escaped}"')

    def _insert_config_line(self, text, line):
        match = list(re.finditer(r"^\s*#endif\b.*CONFIG_DEFINITIONS_H_.*$", text, flags=re.MULTILINE))
        if match:
            index = match[-1].start()
            prefix = text[:index].rstrip()
            suffix = text[index:].lstrip("\r\n")
            return f"{prefix}\n{line}\n\n{suffix}"
        return text.rstrip() + "\n" + line + "\n"

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log_buffer.append(text)
        if len(self.log_buffer) > 1200:
            self.log_buffer = self.log_buffer[-1200:]
        terminal = getattr(self, "terminal_text", None)
        if terminal is not None and terminal.winfo_exists():
            terminal.configure(state="normal")
            terminal.insert("end", text)
            terminal.see("end")
            terminal.configure(state="disabled")

    def clear_log(self):
        self.log_buffer.clear()
        terminal = getattr(self, "terminal_text", None)
        if terminal is not None and terminal.winfo_exists():
            terminal.configure(state="normal")
            terminal.delete("1.0", "end")
            terminal.configure(state="disabled")

    def show_terminal(self):
        window = getattr(self, "terminal_window", None)
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Ignitron PlatformIO Terminal")
        window.configure(bg=BG)
        window.geometry("1120x520")
        self.terminal_window = window

        header = tk.Frame(window, bg=SURFACE)
        header.pack(fill="x")
        tk.Label(header, text="PLATFORMIO TERMINAL", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left", padx=16, pady=12)
        ttk.Button(header, text="Clear", style="Dark.TButton", command=self.clear_log).pack(side="right", padx=(0, 12), pady=8)
        ttk.Button(header, text="Hide", style="Dark.TButton", command=window.withdraw).pack(side="right", padx=(0, 8), pady=8)

        terminal = tk.Text(window, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        terminal.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.terminal_text = terminal

        def on_close():
            window.withdraw()

        window.protocol("WM_DELETE_WINDOW", on_close)
        terminal.configure(state="normal")
        terminal.insert("1.0", "".join(self.log_buffer))
        terminal.see("end")
        terminal.configure(state="disabled")

    def set_busy(self, busy):
        self.running = busy
        state = "disabled" if busy else "normal"
        for button in (
            self.flash_button,
            self.upload_fw_button,
            self.validate_fs_button,
            self.fs_button,
            self.monitor_button,
        ):
            button.configure(state=state)
        if getattr(self, "monitor_process", None) is not None:
            self.stop_monitor_button.configure(state="normal")
        else:
            self.stop_monitor_button.configure(state="disabled")

    def refresh_ports(self, select_first=True):
        current = self.port_var.get().strip()
        values = []
        try:
            ports = list_serial_ports()
            values = [format_serial_port(port) for port in ports]
        except ImportError:
            ports = []
        self.port_combo.configure(values=values)
        devices = [port.device for port in ports]
        if current in devices:
            self.port_var.set(current)
        elif values:
            selected = best_serial_port(ports, current) if (select_first or not current) else None
            if selected:
                self.port_var.set(selected.device)
        self.app.set_status(f"Found {len(values)} serial port(s)" if values else "No serial ports found")

    def selected_port(self):
        return self.port_var.get().split("  |  ", 1)[0].strip()

    def validate_data(self, show_success=True):
        if not self.validate_project(check_erase=False):
            return False
        if not self.data_dir.exists():
            messagebox.showerror("Data folder not found", f"Missing folder:\n{self.data_dir}")
            return False

        json_count = len(list(self.data_dir.glob("*.json")))
        missing = preset_list_missing_files(self.data_dir)
        if missing:
            message = (
                f"Data folder: {self.data_dir}\n"
                f"JSON presets: {json_count}\n\n"
                "PresetList.txt references missing files:\n"
                + "\n".join(missing[:45])
            )
            if len(missing) > 45:
                message += f"\n...and {len(missing) - 45} more"
            if not self.allow_missing_var.get():
                messagebox.showerror("PresetList check failed", message)
                return False
            if show_success:
                messagebox.showwarning("PresetList warning", message)
            self.app.set_status(f"Data warning: {len(missing)} missing referenced file(s)")
            return True

        if show_success:
            messagebox.showinfo(
                "Data looks good",
                f"Data folder: {self.data_dir}\nJSON presets: {json_count}\n\nPresetList.txt references all required files.",
            )
        self.app.set_status(f"Data validated: {json_count} JSON preset file(s)")
        return True

    def prepare_upload_after_builder_export(self):
        self.refresh_ports(select_first=True)
        if self.selected_port():
            self.app.set_status("Preset files exported. Use Upload FS or Build + Upload FS on the Firmware page.")
        else:
            self.app.set_status("Preset files exported. Connect Ignitron, refresh ports, then upload the filesystem.")
            messagebox.showinfo(
                "Select COM port",
                "Preset files were exported.\n\nConnect Ignitron, choose its COM port on the Firmware page, "
                "then click Upload FS or Build + Upload FS.",
            )

    def open_data_folder(self):
        if self.data_dir.exists():
            open_folder(self.data_dir)
        else:
            messagebox.showerror("Data folder not found", f"No data folder exists at:\n{self.data_dir}")

    def open_current_pdf(self):
        pdf_path = self.data_dir / "PresetList.pdf"
        if pdf_path.exists():
            open_folder(pdf_path)
            self.app.set_status(f"Opened {pdf_path}")
        else:
            messagebox.showinfo("PresetList PDF not found", f"No PresetList.pdf exists yet at:\n{pdf_path}")

    def validate_project(self, check_erase=True):
        if not self.project_dir.exists():
            messagebox.showerror("Project not found", f"Project folder does not exist:\n{self.project_dir}")
            return False
        if not self.platformio_ini.exists():
            messagebox.showerror("platformio.ini not found", f"Missing file:\n{self.platformio_ini}")
            return False
        return True

    def save_builder_setup_for_flash_if_present(self):
        builder = self.app.pages.get("builder")
        if not isinstance(builder, BuilderPage) or not builder.has_assigned_slots():
            return True
        previous_output = builder.output_folder
        builder.output_folder = self.data_dir
        try:
            saved = builder.save_setup_for_flash(show_message=False)
        finally:
            builder.output_folder = previous_output
        if saved:
            self.append_log(f"Saved Preset Bank Builder layout to {self.data_dir} before upload.\n")
            return True
        return False

    def prepare_selected_firmware_options(self, save_config=True):
        if save_config and not self.save_firmware_settings(show_message=False):
            return False
        self.use_reliable_upload_speed()
        if not self.write_platformio_default_env(show_status=True):
            return False
        if not self.write_env_upload_speed(show_status=True):
            return False
        if not self.write_env_upload_port(show_status=True):
            messagebox.showinfo("Select COM port", "Choose the Ignitron COM port before flashing or uploading the filesystem.")
            return False
        return True

    def run_flash_workflow(self):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A firmware task is already running.")
            return
        if not self.validate_project():
            return
        if not self.save_builder_setup_for_flash_if_present():
            return
        if not self.validate_data(show_success=False):
            return
        if not self.prepare_selected_firmware_options(save_config=True):
            return
        self.show_terminal()
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Building and flashing firmware + filesystem...")
        threading.Thread(target=self._run_flash_worker, daemon=True).start()

    def run_firmware_upload_workflow(self):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A firmware task is already running.")
            return
        if not self.validate_project():
            return
        if not self.prepare_selected_firmware_options(save_config=True):
            return
        self.show_terminal()
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Uploading firmware to selected pedal...")
        threading.Thread(target=self._run_firmware_upload_worker, daemon=True).start()

    def run_filesystem_workflow(self):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A PlatformIO task is already running.")
            return
        if not self.validate_project(check_erase=False):
            return
        if not self.save_builder_setup_for_flash_if_present():
            return
        if not self.validate_data(show_success=False):
            return
        if not self.selected_port():
            self.refresh_ports(select_first=True)
            if not self.selected_port():
                messagebox.showinfo("Select COM port", "Choose the Ignitron COM port before uploading the filesystem.")
                return
        if not self.prepare_selected_firmware_options(save_config=False):
            return
        self.show_terminal()
        self.set_busy(True)
        self.append_log("\n")
        self.app.set_status("Building and uploading filesystem...")
        threading.Thread(target=self._run_filesystem_worker, daemon=True).start()

    def run_monitor_workflow(self):
        if self.running:
            messagebox.showinfo("PlatformIO running", "A firmware task is already running.")
            return
        if not self.validate_project(check_erase=False):
            return
        if not self.selected_port():
            self.refresh_ports(select_first=True)
            if not self.selected_port():
                messagebox.showinfo("Select COM port", "Choose the Ignitron COM port before opening the serial monitor.")
                return
        if not self.write_platformio_default_env(show_status=True):
            return
        if not self.write_env_upload_port(show_status=True):
            return
        self.show_terminal()
        self.set_busy(True)
        self.stop_monitor_button.configure(state="normal")
        self.append_log("\n")
        self.app.set_status("Opening serial monitor...")
        threading.Thread(target=self._run_monitor_worker, daemon=True).start()

    def stop_monitor(self):
        process = self.monitor_process
        if process is None:
            return
        self.append_log("\nStopping serial monitor...\n")
        with contextlib.suppress(Exception):
            process.terminate()

    def _run_filesystem_worker(self):
        try:
            for target in ("buildfs", "uploadfs"):
                code = self._run_platformio_target(target)
                if code != 0:
                    self.append_log(f"\n{target} failed with exit code {code}\n")
                    self.after(0, lambda t=target: self.app.set_status(f"{t} failed"))
                    return
            self.append_log("\nFilesystem task complete.\n")
            self.after(0, lambda: self.app.set_status("Filesystem upload workflow complete"))
            self.open_pdf_after_success = None
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_firmware_upload_worker(self):
        try:
            targets = []
            if self.clean_var.get():
                targets.append("clean")
            if self.erase_var.get():
                targets.append("erase")
            targets.append("upload")

            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    self.append_log(f"\n{target} failed with exit code {code}\n")
                    self.after(0, lambda name=target: self.app.set_status(f"Firmware {name} failed"))
                    return
            self.append_log("\nFirmware upload complete.\n")
            self.after(0, lambda: self.app.set_status("Firmware upload complete"))
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_flash_worker(self):
        try:
            targets = []
            if self.clean_var.get():
                targets.append("clean")
            if self.erase_var.get():
                targets.append("erase")
            targets.append("upload")
            targets.extend(("buildfs", "uploadfs"))

            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    label = target or "build"
                    self.append_log(f"\n{label} failed with exit code {code}\n")
                    self.after(0, lambda name=label: self.app.set_status(f"Firmware {name} failed"))
                    self.open_pdf_after_success = None
                    return
            self.append_log("\nFirmware + filesystem workflow complete.\n")
            self.after(0, lambda: self.app.set_status("Firmware + filesystem workflow complete"))
            self.open_pdf_after_success = None
        finally:
            self.after(0, lambda: self.set_busy(False))

    def _run_monitor_worker(self):
        port = self.selected_port()
        cmd = [
            self.platformio_var.get(),
            "device",
            "monitor",
            "-e",
            self.env_var.get(),
            "-p",
            port,
            "-b",
            "115200",
        ]
        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            process = run_hidden_subprocess(cmd, self.project_dir)
            self.monitor_process = process
        except Exception as exc:
            self.append_log(f"Could not start PlatformIO monitor: {exc}\n")
            self.monitor_process = None
            self.after(0, lambda: self.app.set_status("Serial monitor failed"))
            self.after(0, lambda: self.set_busy(False))
            return

        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.append_log(line)
            code = process.wait()
            self.append_log(f"\nSerial monitor ended with exit code {code}.\n")
            self.after(0, lambda: self.app.set_status("Serial monitor ended"))
        finally:
            self.monitor_process = None
            self.after(0, lambda: self.set_busy(False))

    def use_reliable_upload_speed(self):
        speed = self.speed_var.get().strip()
        if speed == "921600":
            self.speed_var.set(DEFAULT_UPLOAD_SPEED)
            self.append_log(f"Upload speed changed from 921600 to {DEFAULT_UPLOAD_SPEED} for a more reliable flash.\n")

    def _run_platformio_target(self, target):
        cmd = [self.platformio_var.get(), "run", "-e", self.env_var.get()]
        if target:
            cmd.extend(["-t", target])

        port = self.selected_port()
        if target in ("upload", "uploadfs", "erase") and port:
            cmd.extend(["--upload-port", port])

        self.append_log(f"> {' '.join(cmd)}\n")
        try:
            process = run_hidden_subprocess(cmd, self.project_dir)
        except Exception as exc:
            self.append_log(f"Could not start PlatformIO: {exc}\n")
            return 1

        assert process.stdout is not None
        for line in process.stdout:
            self.append_log(line)
        return process.wait()

    def write_env_upload_speed(self, show_status=False):
        speed = self.speed_var.get().strip()
        if not speed:
            if show_status:
                self.app.set_status("Choose an upload speed before flashing")
            return False
        return self.write_platformio_env_value("upload_speed", speed, show_status=show_status)

    def write_env_upload_port(self, show_status=False):
        port = self.selected_port()
        if not port:
            if show_status:
                self.app.set_status("Choose a COM port before saving it to platformio.ini")
            return False
        return self.write_platformio_env_value("upload_port", port, show_status=show_status)

    def write_platformio_default_env(self, show_status=False):
        env_name = self.env_var.get().strip()
        if not env_name:
            if show_status:
                self.app.set_status("Choose a PlatformIO environment before flashing")
            return False
        return self.write_platformio_section_value("platformio", "default_envs", env_name, show_status=show_status)

    def write_platformio_env_value(self, option_name, value, show_status=False):
        return self.write_platformio_section_value(f"env:{self.env_var.get()}", option_name, value, show_status=show_status)

    def write_platformio_section_value(self, section_name, option_name, value, show_status=False):
        path = self.platformio_ini
        if not path.exists():
            if show_status:
                messagebox.showerror("platformio.ini not found", f"Missing file:\n{path}")
            return False
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        section = f"[{section_name}]"
        section_index = None
        next_section_index = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == section:
                section_index = index
                continue
            if section_index is not None and index > section_index and stripped.startswith("[") and stripped.endswith("]"):
                next_section_index = index
                break
        if section_index is None:
            if section_name == "platformio":
                lines = [section, f"{option_name} = {value}", ""] + lines
            else:
                lines.extend(["", section, f"{option_name} = {value}"])
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            message = f"Set {option_name} = {value} in {section}"
            self.append_log(f"{message}\n")
            if show_status:
                self.app.set_status(message)
            return True

        for index in range(section_index + 1, next_section_index):
            raw = lines[index]
            code = raw.split(";", 1)[0].strip()
            if re.match(rf"^{re.escape(option_name)}\s*=", code):
                prefix = raw[:len(raw) - len(raw.lstrip())]
                comment = ""
                if ";" in raw:
                    comment = "  ;" + raw.split(";", 1)[1]
                lines[index] = f"{prefix}{option_name} = {value}{comment}"
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                message = f"Set {option_name} = {value} in {section}"
                self.append_log(f"{message}\n")
                if show_status:
                    self.app.set_status(message)
                return True

        insert_at = next_section_index
        lines.insert(insert_at, f"{option_name} = {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        message = f"Set {option_name} = {value} in {section}"
        self.append_log(f"{message}\n")
        if show_status:
            self.app.set_status(message)
        return True


class SerialPage(Page):
    tool_title = "Serial tool"
    tool_subtitle = "Connect to Ignitron over USB."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.running = False
        self.stop_event = threading.Event()
        self.port_var = tk.StringVar()
        self.heading(self.tool_title, self.tool_subtitle)
        self._build_serial_ui()
        self.refresh_ports()

    def _build_serial_ui(self):
        panel = tk.Frame(self, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        controls = tk.Frame(panel, bg=SURFACE)
        controls.pack(fill="x", padx=22, pady=20)
        tk.Label(controls, text="USB PORT", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.port_combo = ttk.Combobox(controls, textvariable=self.port_var, state="readonly", width=42)
        self.port_combo.pack(side="left", padx=12)
        ttk.Button(controls, text="Refresh", style="Dark.TButton", command=self.refresh_ports).pack(side="left")
        self.start_button = ttk.Button(controls, text=self.start_text, style="Gold.TButton", command=self.start)
        self.start_button.pack(side="right")

        info = tk.Frame(panel, bg=CARD)
        info.pack(fill="x", padx=22, pady=(0, 16))
        tk.Label(info, text=self.instructions, bg=CARD, fg=MUTED, justify="left",
                 wraplength=850, font=("Segoe UI", 9), padx=16, pady=13).pack(anchor="w")

        log_header = tk.Frame(panel, bg=SURFACE)
        log_header.pack(fill="x", padx=22)
        tk.Label(log_header, text="ACTIVITY", bg=SURFACE, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.connection_dot = tk.Canvas(log_header, width=16, height=16, bg=SURFACE, highlightthickness=0)
        self.connection_dot.pack(side="left", padx=(10, 4))
        self.connection_state_var = tk.StringVar(value="Disconnected")
        tk.Label(log_header, textvariable=self.connection_state_var, bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left")
        self.update_connection_indicator(False)
        ttk.Button(log_header, text="Clear log", style="Dark.TButton", command=self.clear_log).pack(side="right")
        self.log = tk.Text(panel, bg="#0b0d11", fg="#cbd0d8", insertbackground=TEXT,
                           relief="flat", highlightthickness=1, highlightbackground=BORDER,
                           font=("Consolas", 9), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=22, pady=(10, 22))

    def refresh_ports(self, select_best=True):
        try:
            ports = list_serial_ports()
            values = [format_serial_port(port) for port in ports]
        except ImportError:
            ports = []
            values = []
            self.append_log("PySerial is not installed. Install requirements.txt first.\n")
        self.port_combo["values"] = values
        if values:
            current = self.port_var.get()
            current_device = current.split("  |  ", 1)[0].strip().lower()
            devices = [port.device.lower() for port in ports]
            if select_best or current_device not in devices:
                selected = best_serial_port(ports, current)
                self.port_var.set(format_serial_port(selected) if selected else values[0])
            else:
                self.port_var.set(current)
            self.app.set_status(f"Found {len(values)} serial port(s)")
        else:
            self.port_var.set("")
            self.app.set_status("No serial ports found")

    def selected_port(self):
        return self.port_var.get().split("  |  ", 1)[0].strip()

    def auto_select_port(self):
        current = self.port_var.get()
        detected, ports = auto_detect_ignitron_port(current)
        values = [format_serial_port(port) for port in ports]
        self.port_combo["values"] = values
        if detected:
            selected_value = format_serial_port(detected)
            if selected_value != current:
                self.append_log(f"Auto-selected {selected_value}\n")
            self.port_var.set(selected_value)
            return detected.device
        self.port_var.set("")
        return ""

    def append_log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def start(self):
        port = self.auto_select_port()
        if not port:
            messagebox.showinfo("Ignitron not found", "Connect Ignitron by USB, then try again.")
            return
        if self.running:
            return
        self.app.request_serial_start(self)
        self.running = True
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.update_connection_indicator(True)
        threading.Thread(target=self.run_tool, args=(port,), daemon=True).start()

    def stop_serial(self, reason="another serial tool started"):
        if not self.running:
            return
        self.append_log(f"\nStopping connection: {reason}.\n")
        self.stop_event.set()
        self.start_button.configure(state="normal")
        self.update_connection_indicator(False)

    def finish(self):
        self.running = False
        self.stop_event.set()
        self.start_button.configure(state="normal")
        self.update_connection_indicator(False)
        self.app.release_serial_page(self)

    def update_connection_indicator(self, connected):
        if not hasattr(self, "connection_dot"):
            return
        self.connection_dot.delete("all")
        color = GREEN if connected else RED
        self.connection_dot.create_oval(4, 4, 12, 12, fill=color, outline="")
        self.connection_state_var.set("Connected" if connected else "Disconnected")


class TunerPage(SerialPage):
    tool_title = "Visual Guitar Tuner"
    tool_subtitle = "Listen for tuner readings from Ignitron over USB."
    start_text = "Start tuner"
    instructions = (
        "Start tuner mode on firmware that streams lines like "
        "TUNER frequency=82.41 note=E2 cents=-4. The app displays the latest note and cents offset."
    )

    def __init__(self, parent, app):
        self.note_var = tk.StringVar(value="--")
        self.freq_var = tk.StringVar(value="Waiting for tuner data")
        self.cents_var = tk.DoubleVar(value=0.0)
        super().__init__(parent, app)

    def _build_serial_ui(self):
        super()._build_serial_ui()
        tuner = tk.Frame(self.log.master, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        tuner.pack(fill="x", padx=22, pady=(0, 16), before=self.log)
        readout = tk.Frame(tuner, bg=CARD)
        readout.pack(side="left", fill="y", padx=22, pady=18)
        tk.Label(readout, textvariable=self.note_var, bg=CARD, fg=GOLD,
                 font=("Segoe UI Black", 42)).pack(anchor="w")
        tk.Label(readout, textvariable=self.freq_var, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.tuner_canvas = tk.Canvas(tuner, height=132, bg="#0b0d11", highlightthickness=0)
        self.tuner_canvas.pack(side="left", fill="both", expand=True, padx=(0, 22), pady=18)
        self.tuner_canvas.bind("<Configure>", lambda _event: self.draw_tuner())
        self.draw_tuner()
        self.stop_button = ttk.Button(
            self.start_button.master,
            text="End connection",
            style="Danger.TButton",
            command=self.stop_serial,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 10))

    def start(self):
        super().start()
        if self.running:
            self.stop_button.configure(state="normal")

    def stop_serial(self, reason="user stopped tuner"):
        super().stop_serial(reason)
        self.stop_button.configure(state="disabled")

    def finish(self):
        super().finish()
        self.stop_button.configure(state="disabled")

    def parse_tuner_line(self, line):
        if "TUNER" not in line.upper():
            return None
        try:
            if line.strip().startswith("{"):
                data = json.loads(line)
                return (
                    str(data.get("note", "--")),
                    float(data.get("frequency", data.get("freq", 0.0))),
                    float(data.get("cents", 0.0)),
                )
        except Exception:
            pass
        note_match = re.search(r"\bnote\s*[:=]\s*([A-G](?:#|b)?\d?)", line, re.I)
        freq_match = re.search(r"\b(?:frequency|freq|hz)\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, re.I)
        cents_match = re.search(r"\bcents?\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, re.I)
        if not (note_match or freq_match or cents_match):
            return None
        return (
            note_match.group(1).upper() if note_match else "--",
            float(freq_match.group(1)) if freq_match else 0.0,
            float(cents_match.group(1)) if cents_match else 0.0,
        )

    def update_tuner(self, note, frequency, cents):
        cents = max(-50.0, min(50.0, cents))
        self.note_var.set(note or "--")
        if frequency > 0:
            self.freq_var.set(f"{frequency:.2f} Hz  |  {cents:+.1f} cents")
        else:
            self.freq_var.set(f"{cents:+.1f} cents")
        self.cents_var.set(cents)
        self.draw_tuner()

    def draw_tuner(self):
        canvas = getattr(self, "tuner_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 132)
        center = width / 2
        y = height / 2
        canvas.create_line(24, y, width - 24, y, fill=BORDER, width=3)
        for cents in range(-50, 51, 10):
            x = 24 + ((cents + 50) / 100) * (width - 48)
            tick_h = 22 if cents in (-50, 0, 50) else 13
            canvas.create_line(x, y - tick_h, x, y + tick_h, fill=GOLD if cents == 0 else "#56606f", width=2)
            if cents in (-50, -25, 0, 25, 50):
                canvas.create_text(x, y + 38, text=str(cents), fill=MUTED, font=("Segoe UI", 8))
        cents = self.cents_var.get()
        needle_x = 24 + ((cents + 50) / 100) * (width - 48)
        color = GREEN if abs(cents) <= 3 else GOLD if abs(cents) <= 12 else RED
        canvas.create_polygon(needle_x, y - 36, needle_x - 11, y - 12, needle_x + 11, y - 12,
                              fill=color, outline="")
        canvas.create_line(needle_x, y - 10, needle_x, y + 28, fill=color, width=4)
        canvas.create_text(center, 18, text="FLAT" if cents < -3 else "SHARP" if cents > 3 else "IN TUNE",
                           fill=color, font=("Segoe UI Semibold", 12))

    def run_tool(self, port):
        self.append_log(f"Listening for tuner data on {port} at 115200 baud...\n")
        connection = None
        try:
            connection = open_serial_no_reset(port, 115200, timeout=0.25)
            connection.write(b"TUNERSTREAM ON\n")
            while self.winfo_exists() and not self.stop_event.is_set():
                line = connection.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                self.append_log(line + "\n")
                parsed = self.parse_tuner_line(line)
                if parsed:
                    self.after(0, lambda values=parsed: self.update_tuner(*values))
            self.append_log("\nTuner connection ended.\n")
            self.app.set_status("Tuner stopped")
        except Exception as exc:
            self.append_log(f"\nTuner failed: {exc}\n")
            self.app.set_status("Tuner failed")
        finally:
            try:
                if connection:
                    try:
                        connection.write(b"TUNERSTREAM OFF\n")
                    except Exception:
                        pass
                    connection.close()
            except Exception:
                pass
            self.after(0, self.finish)


class DisplayMirrorPage(SerialPage):
    tool_title = "Display Mirror"
    tool_subtitle = "Duplicate firmware display output on the PC."
    start_text = "Start mirror"
    instructions = (
        "Firmware can stream display text as DISPLAY line=0 text=Preset Name, "
        "OLED|line 1|line 2|line 3, JSON {\"display\":[...]}, or raw OLED_HEX data for a 128x64 monochrome frame."
    )

    def __init__(self, parent, app):
        self.display_lines = ["", "", "", ""]
        self.raw_pixels = None
        self.screen_glow = "#f7fbff"
        super().__init__(parent, app)

    def _build_serial_ui(self):
        super()._build_serial_ui()
        mirror = tk.Frame(self.log.master, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        mirror.pack(fill="x", padx=22, pady=(0, 16), before=self.log)
        tk.Label(mirror, text="OLED MIRROR", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22, pady=(16, 8))
        self.display_canvas = tk.Canvas(mirror, width=768, height=384, bg="#05070a", highlightthickness=0)
        self.display_canvas.pack(fill="x", padx=22, pady=(0, 18))
        self.display_canvas.bind("<Configure>", lambda _event: self.draw_display())
        self.draw_display()
        self.stop_button = ttk.Button(
            self.start_button.master,
            text="End connection",
            style="Danger.TButton",
            command=self.stop_serial,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 10))

    def start(self):
        super().start()
        if self.running:
            self.stop_button.configure(state="normal")

    def stop_serial(self, reason="user stopped mirror"):
        super().stop_serial(reason)
        self.stop_button.configure(state="disabled")

    def finish(self):
        super().finish()
        self.stop_button.configure(state="disabled")

    def parse_display_line(self, line):
        stripped = line.strip()
        if not stripped:
            return None
        try:
            if stripped.startswith("{"):
                data = json.loads(stripped)
                lines = data.get("display") or data.get("oled") or data.get("lines")
                if isinstance(lines, list):
                    return ("text", [str(item) for item in lines[:8]])
        except Exception:
            pass
        upper = stripped.upper()
        if upper.startswith("OLED_HEX"):
            payload = re.sub(r"[^0-9A-Fa-f]", "", stripped.split(None, 1)[-1] if " " in stripped else "")
            if len(payload) >= 2048:
                return ("hex", payload[:2048])
        if upper.startswith("OLED|") or upper.startswith("DISPLAY|"):
            return ("text", [part.strip() for part in stripped.split("|")[1:8]])
        if upper.startswith("DISPLAY") or upper.startswith("OLED"):
            line_match = re.search(r"\bline\s*[:=]\s*(\d+)", stripped, re.I)
            text_match = re.search(r"\btext\s*[:=]\s*(.*)$", stripped, re.I)
            if line_match and text_match:
                index = max(0, min(7, int(line_match.group(1))))
                lines = list(self.display_lines)
                while len(lines) <= index:
                    lines.append("")
                lines[index] = text_match.group(1).strip()
                return ("text", lines)
            text = re.sub(r"^(DISPLAY|OLED)\s*[:=-]?\s*", "", stripped, flags=re.I).strip()
            if text:
                return ("text", [text])
        return None

    def update_display_text(self, lines):
        self.raw_pixels = None
        self.display_lines = (lines + ["", "", "", ""])[:8]
        self.draw_display()

    def update_display_hex(self, payload):
        self.raw_pixels = bytes.fromhex(payload)
        self.draw_display()

    def draw_display(self):
        canvas = getattr(self, "display_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 512)
        height = max(canvas.winfo_height(), 256)
        margin = 10
        body_ratio = 551 / 350
        body_w = min(width - margin * 2, (height - margin * 2) * body_ratio)
        body_h = body_w / body_ratio
        if body_h > height - margin * 2:
            body_h = height - margin * 2
            body_w = body_h * body_ratio
        bx0 = (width - body_w) / 2
        by0 = (height - body_h) / 2
        bx1 = bx0 + body_w
        by1 = by0 + body_h
        scale = body_w / 551

        canvas.create_rectangle(0, 0, width, height, fill="#08090c", outline="")
        canvas.create_rectangle(bx0, by0, bx1, by1, fill="#b5841f", outline="#2a210d", width=max(1, int(2 * scale)))
        canvas.create_rectangle(bx0 + 10 * scale, by0 + 9 * scale, bx1 - 10 * scale, by1 - 10 * scale,
                                fill="#b5841f", outline="#6f5217", width=max(1, int(2 * scale)))
        canvas.create_text((bx0 + bx1) / 2, by0 + 69 * scale, text="IGNITRON",
                           fill="#050506", font=("Segoe UI Black", max(18, int(48 * scale))))

        frame_x0 = bx0 + 78 * scale
        frame_y0 = by0 + 123 * scale
        frame_x1 = bx0 + 465 * scale
        frame_y1 = by0 + 328 * scale
        canvas.create_rectangle(frame_x0, frame_y0, frame_x1, frame_y1,
                                fill="#745417", outline="#e1b957", width=max(1, int(2 * scale)))
        canvas.create_rectangle(frame_x0 + 5 * scale, frame_y0 + 5 * scale, frame_x1 - 5 * scale, frame_y1 - 5 * scale,
                                fill="#161820", outline="#0d0f13", width=max(1, int(2 * scale)))

        x0 = bx0 + 90 * scale
        y0 = by0 + 135 * scale
        screen_w = 363 * scale
        screen_h = 181 * scale
        x1 = x0 + screen_w
        y1 = y0 + screen_h
        canvas.create_rectangle(x0, y0, x1, y1, fill="#020307", outline="#38414c", width=max(1, int(2 * scale)))
        canvas.create_line(x0 + 8 * scale, y0 + 6 * scale, x1 - 9 * scale, y0 + 6 * scale,
                           fill="#2e3646", width=max(1, int(scale)))
        if self.raw_pixels:
            scale_x = screen_w / 128
            scale_y = screen_h / 64
            for page in range(8):
                for col in range(128):
                    byte = self.raw_pixels[page * 128 + col]
                    for bit in range(8):
                        if byte & (1 << bit):
                            px = x0 + col * scale_x
                            py = y0 + (page * 8 + bit) * scale_y
                            canvas.create_rectangle(px, py, px + scale_x, py + scale_y,
                                                    fill=self.screen_glow, outline="")
            return
        lines = (self.display_lines + ["", "", "", ""])[:4]
        line0, line1, line2, line3 = [line.strip() for line in lines]
        font_size = max(10, int(21 * scale))
        font = ("Consolas", font_size, "bold")
        left_x = x0 + 26 * scale
        top_y = y0 + 28 * scale
        mid_y = y0 + 72 * scale
        bottom_y = y0 + 115 * scale
        if line0:
            canvas.create_text(left_x, top_y, text=line0[:13], fill=self.screen_glow, anchor="nw", font=font)
        if line1:
            canvas.create_text(left_x, mid_y, text=line1[:14], fill=self.screen_glow, anchor="nw", font=font)
        if line2:
            canvas.create_text(x0 + 272 * scale, mid_y, text=line2[:5], fill=self.screen_glow, anchor="nw", font=font)
        if line3:
            canvas.create_text(left_x, bottom_y, text=line3[:9], fill=self.screen_glow, anchor="nw", font=font)

    def run_tool(self, port):
        self.append_log(f"Mirroring display data from {port} at 115200 baud...\n")
        connection = None
        try:
            connection = open_serial_no_reset(port, 115200, timeout=0.25)
            connection.write(b"MIRROR ON\n")
            while self.winfo_exists() and not self.stop_event.is_set():
                line = connection.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                self.append_log(line + "\n")
                parsed = self.parse_display_line(line)
                if not parsed:
                    continue
                kind, payload = parsed
                if kind == "hex":
                    self.after(0, lambda value=payload: self.update_display_hex(value))
                else:
                    self.after(0, lambda value=payload: self.update_display_text(value))
            self.append_log("\nDisplay mirror connection ended.\n")
            self.app.set_status("Display mirror stopped")
        except Exception as exc:
            self.append_log(f"\nDisplay mirror failed: {exc}\n")
            self.app.set_status("Display mirror failed")
        finally:
            try:
                if connection:
                    try:
                        connection.write(b"MIRROR OFF\n")
                    except Exception:
                        pass
                    connection.close()
            except Exception:
                pass
            self.after(0, self.finish)


class PedalRemotePage(SerialPage):
    tool_title = "Pedal Remote"
    tool_subtitle = "Click presets and show tuner readings when Ignitron enters tuner mode."
    start_text = "Connect remote"
    instructions = (
        "Connect USB to Ignitron and keep Ignitron connected to the Spark amp. "
        "This tab reads the selected project's PresetList.txt and sends SELECTPRESET commands over USB."
    )

    def __init__(self, parent, app):
        self.remote_status_var = tk.StringVar(value="Load the Ignitron data folder, then connect remote.")
        self.hardware_type_var = tk.StringVar(value="Hardware: not connected")
        self.hardware_detail_var = tk.StringVar(value="Connect remote to identify amp")
        self.remote_note_var = tk.StringVar(value="--")
        self.remote_tuner_var = tk.StringVar(value="Tuner")
        self.remote_cents_var = tk.DoubleVar(value=0.0)
        self.current_preset_var = tk.StringVar(value="No preset selected")
        self.current_slot_var = tk.StringVar(value="--")
        self.hw_save_mode_var = tk.BooleanVar(value=False)
        self.looper_status_var = tk.StringVar(value="Spark 2 looper")
        self.looper_detail_var = tk.StringVar(value="Connect Spark 2 to enable live looper controls.")
        self.connection = None
        self.bank_rows = []
        self.active_cell = None
        self.active_hw_cell = None
        self.preset_cells = {}
        self.bank_row_widgets = {}
        self.hw_preset_cells = {}
        self.hw_bank_widgets = {}
        self.hw_bank_count = 1
        self.pending_hw_store = None
        self.pending_bank = None
        self.pending_bank_flash_job = None
        self.pending_bank_flash_phase = 0
        self.looper_visible = False
        self.looper_mode_active = False
        self.looper_enter_button = None
        self.looper_state = {
            "rec": 0, "available": 0, "playing": 0, "undo": 0, "redo": 0,
            "loops": 0, "bar": 1, "beat": 1, "bars": 4, "bpm": 120,
        }
        self.remote_tuner_visible = False
        self.remote_tuner_hide_job = None
        super().__init__(parent, app)

    def _build_serial_ui(self):
        super()._build_serial_ui()
        self.log.configure(height=3)
        self.log.pack_configure(fill="x", expand=False)
        remote = tk.Frame(self.log.master, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        remote.pack(fill="both", expand=True, padx=18, pady=(0, 10), before=self.log)
        header = tk.Frame(remote, bg=CARD)
        header.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(header, text="PRESET REMOTE", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 11)).pack(side="left")
        ttk.Button(header, text="Reload PresetList", style="Dark.TButton",
                   command=self.reload_preset_grid).pack(side="right")
        info_row = tk.Frame(remote, bg=CARD)
        info_row.pack(fill="x", padx=10, pady=(0, 5))
        tk.Label(info_row, textvariable=self.remote_status_var, bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9), justify="left").pack(side="left", anchor="w", fill="x", expand=True)
        hardware_badge = tk.Frame(info_row, bg="#0b0d11", highlightbackground=BORDER, highlightthickness=1)
        hardware_badge.pack(side="right", padx=(8, 0))
        tk.Label(hardware_badge, textvariable=self.hardware_type_var, bg="#0b0d11", fg=GOLD,
                 font=("Segoe UI Semibold", 9), padx=10, pady=2).pack(anchor="e")
        tk.Label(hardware_badge, textvariable=self.hardware_detail_var, bg="#0b0d11", fg=MUTED,
                 font=("Segoe UI", 9), padx=10, pady=2).pack(anchor="e")

        top_row = tk.Frame(remote, bg=CARD)
        top_row.pack(fill="x", padx=10, pady=(0, 5))
        self.current_display = tk.Canvas(top_row, height=90, bg=CARD, highlightthickness=0)
        self.current_display.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.current_display.bind("<Configure>", lambda _event: self.draw_current_preset_display())
        self.draw_current_preset_display()
        self.hw_frame = tk.Frame(top_row, bg=CARD)
        self.hw_frame.pack(side="right", fill="y")
        self.build_hw_presets()

        self.remote_tuner_frame = tk.Frame(remote, bg="#0b0d11", highlightbackground=BORDER, highlightthickness=1)
        readout = tk.Frame(self.remote_tuner_frame, bg="#0b0d11")
        readout.pack(side="left", fill="y", padx=14, pady=8)
        tk.Label(readout, textvariable=self.remote_note_var, bg="#0b0d11", fg=GOLD,
                 font=("Segoe UI Black", 28), width=4).pack(anchor="w")
        tk.Label(readout, textvariable=self.remote_tuner_var, bg="#0b0d11", fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.remote_tuner_canvas = tk.Canvas(self.remote_tuner_frame, height=72, bg="#0b0d11", highlightthickness=0)
        self.remote_tuner_canvas.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=8)
        self.remote_tuner_canvas.bind("<Configure>", lambda _event: self.draw_remote_tuner())
        self.draw_remote_tuner()

        self.looper_frame = tk.Frame(remote, bg="#0b0d11", highlightbackground=BORDER, highlightthickness=1)
        self.build_looper_panel()

        self.grid_canvas = tk.Canvas(remote, bg=CARD, highlightthickness=0, height=520)
        grid_scroll = ttk.Scrollbar(remote, orient="vertical", command=self.grid_canvas.yview)
        self.grid_canvas.configure(yscrollcommand=grid_scroll.set)
        self.grid_canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        grid_scroll.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
        self.grid_host = tk.Frame(self.grid_canvas, bg=CARD)
        self.grid_window = self.grid_canvas.create_window((0, 0), window=self.grid_host, anchor="nw")
        self.grid_host.bind("<Configure>", lambda _e: self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all")))
        self.grid_canvas.bind("<Configure>", lambda e: self.grid_canvas.itemconfigure(self.grid_window, width=e.width))
        for widget in (remote, self.grid_canvas, self.grid_host):
            widget.bind("<Enter>", self.bind_preset_mousewheel)
            widget.bind("<Leave>", self.unbind_preset_mousewheel)

        self.stop_button = ttk.Button(
            self.start_button.master,
            text="End connection",
            style="Danger.TButton",
            command=self.stop_serial,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 10))
        self.reload_preset_grid()

    def build_hw_presets(self):
        self.hw_preset_cells = {}
        self.hw_bank_widgets = {}
        header = tk.Frame(self.hw_frame, bg=CARD)
        header.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 3))
        tk.Label(header, text="SPARK HW PRESETS", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        tk.Checkbutton(header, text="Save current to clicked HW slot", variable=self.hw_save_mode_var,
                       bg=CARD, fg=MUTED, selectcolor=CARD_ALT,
                       activebackground=CARD, activeforeground=TEXT,
                       font=("Segoe UI", 9)).pack(side="right", padx=(8, 0))
        self.looper_enter_button = ttk.Button(header, text="Enter Looper", style="Gold.TButton",
                                              command=lambda: self.send_looper_command("ENTER"))
        self.looper_enter_button.pack(side="right", padx=(10, 0))
        for bank in range(1, 3):
            bank_widgets = []
            label = tk.Label(self.hw_frame, text=f"HW {bank}", bg=CARD, fg=MUTED,
                             font=("Segoe UI Semibold", 9), width=5, anchor="e")
            label.grid(row=bank, column=0, sticky="e", padx=(0, 6), pady=2)
            bank_widgets.append(label)
            for preset in range(1, 5):
                button_text = ("Rhythm", "Lead", "Solo", "Custom")[preset - 1] if bank == 1 else str(preset)
                cell = tk.Button(
                    self.hw_frame,
                    text=button_text,
                    bg=CARD_ALT,
                    fg=TEXT,
                    activebackground=ORANGE,
                    activeforeground="white",
                    relief="flat",
                    bd=0,
                    width=8 if bank == 1 else 5,
                    height=2,
                    font=("Segoe UI Semibold", 9 if bank == 1 else 10),
                    command=lambda b=bank, p=preset: self.select_hw_preset(b, p),
                )
                cell.grid(row=bank, column=preset, sticky="nsew", padx=1, pady=1)
                cell.default_bg = CARD_ALT
                cell.bind("<Enter>", self.bind_preset_mousewheel)
                self.hw_preset_cells[(bank, preset)] = cell
                bank_widgets.append(cell)
            self.hw_bank_widgets[bank] = bank_widgets
        self.update_hw_bank_visibility(1)

    def update_hw_bank_visibility(self, bank_count):
        try:
            bank_count = int(bank_count)
        except Exception:
            bank_count = 1
        self.hw_bank_count = max(1, min(2, bank_count))
        self.update_hardware_indicator(self.hw_bank_count)
        for bank, widgets in self.hw_bank_widgets.items():
            for widget in widgets:
                if bank <= self.hw_bank_count:
                    widget.grid()
                else:
                    widget.grid_remove()
        if self.looper_enter_button:
            if self.hw_bank_count >= 2 and not self.looper_mode_active:
                self.looper_enter_button.pack(side="right", padx=(10, 0))
            else:
                self.looper_enter_button.pack_forget()
        if self.hw_bank_count < 2:
            self.looper_mode_active = False
            self.hide_looper_panel()

    def update_hardware_indicator(self, bank_count=None, amp_name=""):
        try:
            bank_count = int(bank_count) if bank_count is not None else self.hw_bank_count
        except Exception:
            bank_count = self.hw_bank_count
        amp_name = (amp_name or "").strip()
        if bank_count >= 2 or amp_name.lower() == "spark 2":
            hardware = "Spark 2"
            detail = "2 HW banks, looper available"
        elif amp_name:
            hardware = amp_name
            detail = f"{max(1, bank_count)} HW bank"
        elif self.running:
            hardware = "Unknown Spark"
            detail = f"{max(1, bank_count)} HW bank reported"
        else:
            hardware = "Not connected"
            detail = "Connect remote to identify amp"
        self.hardware_type_var.set(f"Hardware: {hardware}")
        self.hardware_detail_var.set(detail)

    def compact_remote_status(self, amp_name="", bank_count=None):
        data_file = self.app.data_dir / "PresetList.txt"
        parts = [f"{len(self.bank_rows)} bank(s) loaded", str(data_file)]
        if amp_name:
            parts.append(f"{amp_name}: {bank_count} HW bank(s)")
        elif bank_count:
            parts.append(f"{bank_count} HW bank(s)")
        self.remote_status_var.set("  |  ".join(parts))

    def build_looper_panel(self):
        top = tk.Frame(self.looper_frame, bg="#0b0d11")
        top.pack(fill="x", padx=10, pady=(6, 4))
        tk.Label(top, text="SPARK 2 LOOPER", bg="#0b0d11", fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        tk.Label(top, textvariable=self.looper_status_var, bg="#0b0d11", fg=TEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(14, 0))
        ttk.Button(top, text="Exit Looper", style="Danger.TButton",
                   command=lambda: self.send_looper_command("EXIT")).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="Status", style="Dark.TButton",
                   command=lambda: self.send_looper_command("STATUS")).pack(side="right")

        body = tk.Frame(self.looper_frame, bg="#0b0d11")
        body.pack(fill="x", padx=10, pady=(0, 6))
        primary = tk.Frame(body, bg="#0b0d11")
        primary.pack(side="left", fill="y")
        ttk.Button(primary, text="Rec / Dub", style="Gold.TButton",
                   command=lambda: self.send_looper_command("RECDUB")).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=1)
        ttk.Button(primary, text="Play / Stop", style="Dark.TButton",
                   command=lambda: self.send_looper_command("PLAYSTOP")).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=1)
        ttk.Button(primary, text="Stop", style="Danger.TButton",
                   command=lambda: self.send_looper_command("STOP")).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=1)

        secondary = tk.Frame(body, bg="#0b0d11")
        secondary.pack(side="left", fill="y", padx=(4, 10))
        for index, (label, command) in enumerate((
            ("Undo / Redo", "UNDOREDO"),
            ("Retry", "RETRY"),
            ("Delete", "DELETE"),
        )):
            ttk.Button(secondary, text=label, style="Dark.TButton",
                       command=lambda cmd=command: self.send_looper_command(cmd)).grid(
                           row=index, column=0, sticky="ew", pady=1
                       )

        visual = tk.Frame(body, bg="#0b0d11")
        visual.pack(side="left", fill="both", expand=True)
        self.looper_canvas = tk.Canvas(visual, height=48, bg="#0b0d11", highlightthickness=0)
        self.looper_canvas.pack(fill="both", expand=True)
        self.looper_canvas.bind("<Configure>", lambda _event: self.draw_looper())
        tk.Label(visual, textvariable=self.looper_detail_var, bg="#0b0d11", fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(1, 0))
        self.draw_looper()

    def show_looper_panel(self):
        if self.looper_visible:
            return
        self.looper_visible = True
        self.looper_frame.pack(fill="x", padx=10, pady=(0, 5), before=self.grid_canvas)
        self.draw_looper()

    def hide_looper_panel(self):
        if not self.looper_visible:
            return
        self.looper_visible = False
        self.looper_frame.pack_forget()

    def update_looper_mode(self, active):
        self.looper_mode_active = bool(active)
        if self.looper_mode_active:
            self.show_looper_panel()
            if self.looper_enter_button:
                self.looper_enter_button.pack_forget()
            if not self.looper_status_var.get() or self.looper_status_var.get() == "Spark 2 looper ready":
                self.looper_status_var.set("Looper mode")
            self.app.set_status("Spark 2 looper mode active")
        else:
            self.hide_looper_panel()
            if self.looper_enter_button and self.hw_bank_count >= 2:
                self.looper_enter_button.pack(side="right", padx=(10, 0))
            self.looper_status_var.set("Spark 2 looper ready")
            self.app.set_status("Spark 2 looper mode closed")

    def parse_hwinfo_line(self, line):
        match = re.search(r"\bHWINFO\b.*\bbanks\s*=\s*(\d+)", line, re.I)
        if not match:
            return None
        bank_count = int(match.group(1))
        amp_match = re.search(r'\bamp\s*=\s*"([^"]*)"', line, re.I)
        amp_name = amp_match.group(1).strip() if amp_match else ""
        if len(amp_name) > 24 or amp_name.upper().startswith("HWINFO"):
            amp_name = ""
        return bank_count, amp_name

    def parse_looper_mode_line(self, line):
        if "LOOPER_MODE" not in line.upper():
            return None
        match = re.search(r"\bactive\s*=\s*(0|1|true|false)", line, re.I)
        if not match:
            return None
        value = match.group(1).lower()
        return value in ("1", "true")

    def send_looper_command(self, command):
        if not self.running or not self.connection:
            self.app.set_status("Connect Pedal Remote before using Spark 2 looper")
            self.append_log("Connect remote before using Spark 2 looper.\n")
            return
        if self.hw_bank_count < 2:
            self.app.set_status("Spark 2 looper controls appear after Spark 2 is detected")
            self.append_log("Spark 2 looper controls require a connected Spark 2.\n")
            return
        command = command.upper()
        try:
            line = f"LOOPER {command}\n"
            self.connection.write(line.encode("ascii"))
            self.append_log(f"> {line}")
            self.app.set_status(f"Looper command sent: {command}")
        except Exception as exc:
            self.append_log(f"Could not send looper command: {exc}\n")
            self.app.set_status("Looper command failed")

    def parse_looper_status_line(self, line):
        if "LOOPER_STATUS" not in line.upper():
            return None
        status = {}
        for key, value in re.findall(r"\b(rec|available|playing|undo|redo|loops|bar|beat|bars|bpm)\s*=\s*(-?\d+)", line, re.I):
            status[key.lower()] = int(value)
        if status:
            return status
        mapping = {
            "rec": r"Recording running:\s*(true|false)",
            "available": r"Recording available:\s*(true|false)",
            "playing": r"Is Playing:\s*(true|false)",
            "redo": r"Redo available:\s*(true|false)",
        }
        for key, pattern in mapping.items():
            match = re.search(pattern, line, re.I)
            if match:
                status[key] = 1 if match.group(1).lower() == "true" else 0
        return status or None

    def update_looper_status(self, status):
        self.looper_state.update(status)
        rec = bool(self.looper_state.get("rec"))
        playing = bool(self.looper_state.get("playing"))
        available = bool(self.looper_state.get("available"))
        loops = self.looper_state.get("loops", 0)
        if rec:
            state = "Recording"
        elif playing:
            state = "Playing"
        elif available:
            state = "Loop ready"
        else:
            state = "Idle"
        self.looper_status_var.set(state)
        self.looper_detail_var.set(
            f"Bar {self.looper_state.get('bar', 1)} / {self.looper_state.get('bars', 4)}"
            f"   Beat {self.looper_state.get('beat', 1)}"
            f"   BPM {self.looper_state.get('bpm', 120)}"
            f"   Loops {loops}"
            f"   Undo {'yes' if self.looper_state.get('undo') else 'no'}"
            f"   Redo {'yes' if self.looper_state.get('redo') else 'no'}"
        )
        self.draw_looper()

    def draw_looper(self):
        canvas = getattr(self, "looper_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 48)
        state = self.looper_state
        rec = bool(state.get("rec"))
        playing = bool(state.get("playing"))
        available = bool(state.get("available"))
        bars = max(1, int(state.get("bars", 4) or 4))
        current_bar = max(1, min(bars, int(state.get("bar", 1) or 1)))
        beat = max(1, min(4, int(state.get("beat", 1) or 1)))
        accent = RED if rec else GREEN if playing else GOLD if available else MUTED
        canvas.create_rectangle(0, 0, width, height, fill="#0b0d11", outline="")
        canvas.create_text(12, 11, text=self.looper_status_var.get().upper(), fill=accent,
                           anchor="w", font=("Segoe UI Black", 9))
        meter_x0 = 12
        meter_y = 27
        meter_w = width - 36
        canvas.create_line(meter_x0, meter_y, meter_x0 + meter_w, meter_y, fill=BORDER, width=4)
        for bar in range(1, bars + 1):
            x = meter_x0 + ((bar - 1) / max(1, bars - 1)) * meter_w if bars > 1 else meter_x0 + meter_w / 2
            color = accent if bar == current_bar else "#56606f"
            canvas.create_oval(x - 5, meter_y - 5, x + 5, meter_y + 5, fill=color, outline="")
        beat_w = min(220, meter_w)
        beat_x0 = meter_x0
        beat_y = 41
        for index in range(1, 5):
            x = beat_x0 + (index - 1) * (beat_w / 3)
            color = accent if index == beat else "#303848"
            canvas.create_rectangle(x - 10, beat_y - 5, x + 10, beat_y + 5, fill=color, outline="")

    def bind_preset_mousewheel(self, _event=None):
        self.bind_all("<MouseWheel>", self.on_preset_mousewheel)
        self.bind_all("<Button-4>", self.on_preset_mousewheel)
        self.bind_all("<Button-5>", self.on_preset_mousewheel)

    def unbind_preset_mousewheel(self, _event=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def on_preset_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.grid_canvas.yview_scroll(delta, "units")
        return "break"

    def start(self):
        super().start()
        if self.running:
            self.stop_button.configure(state="normal")

    def stop_serial(self, reason="user stopped remote"):
        super().stop_serial(reason)
        self.stop_button.configure(state="disabled")

    def finish(self):
        super().finish()
        self.connection = None
        self.stop_button.configure(state="disabled")
        self.hide_remote_tuner()
        self.stop_pending_bank_flash()

    def reload_preset_grid(self):
        self.bank_rows = self.load_preset_rows()
        self.render_preset_grid()

    def load_preset_rows(self):
        data_dir = self.app.data_dir
        preset_list = data_dir / "PresetList.txt"
        if not preset_list.exists():
            self.remote_status_var.set(f"PresetList.txt not found: {preset_list}")
            return []

        rows = []
        current = []
        for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("--"):
                if current:
                    rows.append(current)
                    current = []
                continue
            current.append(line)
            if len(current) == 4:
                rows.append(current)
                current = []
        if current:
            rows.append(current)

        self.remote_status_var.set(f"{len(rows)} bank(s) loaded  |  {preset_list}")
        return rows

    def preset_label(self, filename):
        path = self.app.data_dir / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return str(data.get("Name", Path(filename).stem))
        except Exception:
            return Path(filename).stem

    def render_preset_grid(self):
        self.preset_cells = {}
        self.bank_row_widgets = {}
        for child in self.grid_host.winfo_children():
            child.destroy()
        if not self.bank_rows:
            tk.Label(self.grid_host, text="No preset banks loaded.", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=14, pady=14)
            return

        self.grid_host.grid_columnconfigure(0, minsize=90)
        for column in range(1, 5):
            self.grid_host.grid_columnconfigure(column, weight=1, uniform="preset_cols", minsize=150)

        tk.Label(self.grid_host, text="", bg=CARD).grid(row=0, column=0, sticky="ew", padx=(5, 5), pady=(0, 2))
        for preset_index in range(1, 5):
            tk.Label(self.grid_host, text=f"PRESET {preset_index}", bg=CARD, fg=MUTED,
                     font=("Segoe UI Semibold", 9)).grid(row=0, column=preset_index, sticky="ew", padx=2, pady=(0, 4))

        for bank_index, filenames in enumerate(self.bank_rows, start=1):
            bank_widgets = []
            bank_label = tk.Label(self.grid_host, text=f"BANK {bank_index:02d}", bg=CARD, fg=GOLD,
                                  font=("Segoe UI Semibold", 10), anchor="e")
            bank_label.grid(row=bank_index, column=0, sticky="ew", padx=(5, 9), pady=2)
            bank_label.default_bg = CARD
            bank_widgets.append(bank_label)
            for preset_index in range(1, 5):
                filename = filenames[preset_index - 1] if preset_index <= len(filenames) else ""
                label = self.preset_label(filename) if filename else "Empty"
                if len(label) > 40:
                    label = label[:37].rstrip() + "..."
                cell = tk.Button(
                    self.grid_host,
                    text=label,
                    bg=CARD_ALT if filename else "#161922",
                    fg=TEXT if filename else MUTED,
                    activebackground=ORANGE,
                    activeforeground="white",
                    relief="flat",
                    bd=0,
                    height=1,
                    wraplength=180,
                    justify="center",
                    font=("Segoe UI Semibold", 10),
                    command=lambda b=bank_index, p=preset_index, f=filename: self.select_preset(b, p, f),
                )
                cell.grid(row=bank_index, column=preset_index, sticky="ew", padx=2, pady=2, ipady=3)
                cell.bank_index = bank_index
                cell.preset_index = preset_index
                cell.filename = filename
                cell.default_bg = CARD_ALT if filename else "#161922"
                cell.bind("<Enter>", self.bind_preset_mousewheel)
                self.preset_cells[(bank_index, preset_index)] = cell
                bank_widgets.append(cell)
                if not filename:
                    cell.configure(state="disabled")
            self.bank_row_widgets[bank_index] = bank_widgets

    def draw_current_preset_display(self):
        canvas = getattr(self, "current_display", None)
        if not canvas:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 82)
        pad = 6
        screen_w = min(520, width - pad * 2)
        x0 = pad
        y0 = 3
        x1 = x0 + screen_w
        y1 = height - 3
        canvas.create_rectangle(0, 0, width, height, fill=CARD, outline="")
        canvas.create_rectangle(x0, y0, x1, y1, fill="#8b6418", outline="#d0a646", width=2)
        canvas.create_rectangle(x0 + 6, y0 + 6, x1 - 6, y1 - 6, fill="#030407", outline="#202733", width=2)
        canvas.create_text(x0 + 18, y0 + 19, text="CURRENT PRESET", fill=GOLD,
                           anchor="w", font=("Segoe UI Semibold", 9))
        canvas.create_text(x0 + 18, y0 + 52, text=self.current_slot_var.get(), fill="#f7fbff",
                           anchor="w", font=("Consolas", 20, "bold"))
        canvas.create_text(x0 + 108, y0 + 52, text=self.current_preset_var.get()[:36], fill="#f7fbff",
                           anchor="w", font=("Consolas", 20, "bold"))

    def parse_tuner_line(self, line):
        if "TUNER" not in line.upper():
            return None
        try:
            if line.strip().startswith("{"):
                data = json.loads(line)
                return (
                    str(data.get("note", "--")),
                    float(data.get("frequency", data.get("freq", 0.0))),
                    float(data.get("cents", 0.0)),
                )
        except Exception:
            pass
        note_match = re.search(r"\bnote\s*[:=]\s*([A-G](?:#|b)?\d?)", line, re.I)
        freq_match = re.search(r"\b(?:frequency|freq|hz)\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, re.I)
        cents_match = re.search(r"\bcents?\s*[:=]\s*(-?\d+(?:\.\d+)?)", line, re.I)
        if not (note_match or freq_match or cents_match):
            return None
        return (
            note_match.group(1).upper() if note_match else "--",
            float(freq_match.group(1)) if freq_match else 0.0,
            float(cents_match.group(1)) if cents_match else 0.0,
        )

    def show_remote_tuner(self):
        if self.remote_tuner_visible:
            return
        self.remote_tuner_visible = True
        self.remote_tuner_frame.pack(fill="x", padx=14, pady=(0, 8), before=self.grid_canvas)
        self.draw_remote_tuner()

    def hide_remote_tuner(self):
        if self.remote_tuner_hide_job:
            try:
                self.after_cancel(self.remote_tuner_hide_job)
            except Exception:
                pass
            self.remote_tuner_hide_job = None
        if not getattr(self, "remote_tuner_visible", False):
            return
        self.remote_tuner_visible = False
        self.remote_tuner_frame.pack_forget()
        self.remote_note_var.set("--")
        self.remote_tuner_var.set("Tuner")
        self.remote_cents_var.set(0.0)

    def update_remote_tuner(self, note, frequency, cents):
        cents = max(-50.0, min(50.0, cents))
        self.show_remote_tuner()
        self.remote_note_var.set(note or "--")
        if frequency > 0:
            self.remote_tuner_var.set(f"{frequency:.2f} Hz  |  {cents:+.1f} cents")
        else:
            self.remote_tuner_var.set(f"{cents:+.1f} cents")
        self.remote_cents_var.set(cents)
        self.draw_remote_tuner()
        if self.remote_tuner_hide_job:
            self.after_cancel(self.remote_tuner_hide_job)
        self.remote_tuner_hide_job = self.after(1800, self.hide_remote_tuner)

    def draw_remote_tuner(self):
        canvas = getattr(self, "remote_tuner_canvas", None)
        if not canvas:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 72)
        y = height / 2 + 2
        canvas.create_line(18, y, width - 18, y, fill=BORDER, width=3)
        for cents in range(-50, 51, 10):
            x = 18 + ((cents + 50) / 100) * (width - 36)
            tick_h = 16 if cents in (-50, 0, 50) else 9
            canvas.create_line(x, y - tick_h, x, y + tick_h, fill=GOLD if cents == 0 else "#56606f", width=2)
        cents = self.remote_cents_var.get()
        needle_x = 18 + ((cents + 50) / 100) * (width - 36)
        color = GREEN if abs(cents) <= 3 else GOLD if abs(cents) <= 12 else RED
        label = "IN TUNE" if abs(cents) <= 3 else "FLAT" if cents < 0 else "SHARP"
        canvas.create_polygon(needle_x, y - 28, needle_x - 9, y - 9, needle_x + 9, y - 9,
                              fill=color, outline="")
        canvas.create_line(needle_x, y - 7, needle_x, y + 22, fill=color, width=4)
        canvas.create_text(width / 2, 13, text=label, fill=color, font=("Segoe UI Semibold", 10))

    def select_preset(self, bank, preset, filename):
        if not self.running or not self.connection:
            self.app.set_status("Connect Pedal Remote before selecting presets")
            self.append_log("Connect remote before selecting presets.\n")
            return
        command = f"SELECTPRESET {bank} {preset}\n"
        try:
            self.connection.write(command.encode("ascii"))
            label = self.preset_label(filename)
            self.flash_pending_bank(bank)
            self.app.set_status(f"Selecting Bank {bank:02d}, Preset {preset}: {label}")
            self.append_log(f"> {command}")
        except Exception as exc:
            self.append_log(f"Could not send preset change: {exc}\n")
            self.app.set_status("Preset remote command failed")

    def select_hw_preset(self, bank, preset):
        if not self.running or not self.connection:
            self.app.set_status("Connect Pedal Remote before selecting amp hardware presets")
            self.append_log("Connect remote before selecting amp hardware presets.\n")
            return
        if bank > self.hw_bank_count:
            self.app.set_status("HW bank 2 is only shown/enabled after Spark 2 is detected")
            self.append_log("HW bank 2 is only available when connected to a Spark 2.\n")
            return
        saving = self.hw_save_mode_var.get()
        command = f"{'STOREHW' if saving else 'SELECTHW'} {bank} {preset}\n"
        try:
            self.connection.write(command.encode("ascii"))
            if saving:
                label = f"Saving current preset to Spark HW Bank {bank}, Preset {preset}"
                self.pending_hw_store = (bank, preset)
                self.hw_save_mode_var.set(False)
            else:
                label = f"Spark HW Bank {bank}, Preset {preset}"
                self.current_slot_var.set(f"HW{bank}-{preset}")
                self.current_preset_var.set(f"Selecting {label}")
                self.draw_current_preset_display()
            self.app.set_status(label)
            self.append_log(f"> {command}")
        except Exception as exc:
            self.append_log(f"Could not send hardware preset command: {exc}\n")
            self.app.set_status("Hardware preset command failed")

    def set_active_preset(self, bank, preset, label):
        self.stop_pending_bank_flash()
        if self.active_hw_cell:
            try:
                self.active_hw_cell.configure(bg=getattr(self.active_hw_cell, "default_bg", CARD_ALT), fg=TEXT)
            except Exception:
                pass
            self.active_hw_cell = None
        if self.active_cell:
            try:
                self.active_cell.configure(bg=getattr(self.active_cell, "default_bg", CARD_ALT), fg=TEXT)
            except Exception:
                pass
        cell = self.preset_cells.get((bank, preset))
        self.active_cell = cell
        if cell:
            cell.configure(bg=ORANGE, fg="white")
            self.grid_canvas.yview_moveto(max(0, (bank - 3) / max(1, len(self.bank_rows))))
        self.current_slot_var.set(f"{bank:02d}-{preset}")
        self.current_preset_var.set(label)
        self.draw_current_preset_display()

    def set_active_hw_preset(self, bank, preset, label):
        self.stop_pending_bank_flash()
        if self.active_cell:
            try:
                self.active_cell.configure(bg=getattr(self.active_cell, "default_bg", CARD_ALT), fg=TEXT)
            except Exception:
                pass
            self.active_cell = None
        if self.active_hw_cell:
            try:
                self.active_hw_cell.configure(bg=getattr(self.active_hw_cell, "default_bg", CARD_ALT), fg=TEXT)
            except Exception:
                pass
        cell = self.hw_preset_cells.get((bank, preset))
        self.active_hw_cell = cell
        if cell:
            cell.configure(bg=ORANGE, fg="white")
        self.current_slot_var.set(f"HW{bank}-{preset}")
        self.current_preset_var.set(label)
        self.draw_current_preset_display()

    def preset_label_for_slot(self, bank, preset):
        if 1 <= bank <= len(self.bank_rows):
            filenames = self.bank_rows[bank - 1]
            if 1 <= preset <= len(filenames):
                return self.preset_label(filenames[preset - 1])
        return f"Bank {bank:02d}, Preset {preset}"

    def hw_preset_label(self, bank, preset):
        if bank == 1 and 1 <= preset <= 4:
            name = ("Rhythm", "Lead", "Solo", "Custom")[preset - 1]
            return f"Spark HW {name}"
        return f"Spark HW Bank {bank}, Preset {preset}"

    def parse_remote_event_line(self, line):
        if not line.upper().startswith("REMOTE_"):
            return None
        values = {}
        for key, value in re.findall(r"\b(bank|preset|hwbank)\s*=\s*(-?\d+)", line, re.I):
            values[key.lower()] = int(value)
        upper = line.upper()
        if upper.startswith("REMOTE_BANK") and "bank" in values:
            return ("bank", values)
        if upper.startswith("REMOTE_PRESET") and "bank" in values and "preset" in values:
            return ("preset", values)
        return None

    def flash_pending_bank(self, bank):
        if bank <= 0:
            return
        self.stop_pending_bank_flash()
        self.pending_bank = bank
        self.pending_bank_flash_phase = 0
        self._flash_pending_bank()

    def stop_pending_bank_flash(self, restore=True):
        if self.pending_bank_flash_job:
            try:
                self.after_cancel(self.pending_bank_flash_job)
            except Exception:
                pass
            self.pending_bank_flash_job = None
        if restore and self.pending_bank:
            for widget in self.bank_row_widgets.get(self.pending_bank, []):
                try:
                    widget.configure(bg=getattr(widget, "default_bg", CARD))
                except Exception:
                    pass
        self.pending_bank = None

    def _flash_pending_bank(self):
        bank = self.pending_bank
        if not bank:
            return
        flash_on = self.pending_bank_flash_phase % 2 == 0
        for widget in self.bank_row_widgets.get(bank, []):
            try:
                if widget is self.active_cell:
                    continue
                widget.configure(bg="#5a4518" if flash_on else getattr(widget, "default_bg", CARD))
            except Exception:
                pass
        self.pending_bank_flash_phase += 1
        self.pending_bank_flash_job = self.after(180, self._flash_pending_bank)

    def handle_remote_event(self, event):
        kind, values = event
        if kind == "bank":
            bank = values.get("bank", 0)
            hwbank = values.get("hwbank", 1)
            if bank == 0:
                self.app.set_status(f"Pending Spark HW bank {hwbank}")
            else:
                self.flash_pending_bank(bank)
                self.app.set_status(f"Pending Bank {bank:02d}")
            return
        bank = values.get("bank", 0)
        preset = values.get("preset", 0)
        hwbank = values.get("hwbank", 1)
        if bank == 0:
            label = self.hw_preset_label(hwbank, preset)
            self.set_active_hw_preset(hwbank, preset, label)
            self.app.set_status(f"Selected {label}")
        else:
            label = self.preset_label_for_slot(bank, preset)
            self.set_active_preset(bank, preset, label)
            self.app.set_status(f"Selected Bank {bank:02d}, Preset {preset}: {label}")

    def run_tool(self, port):
        self.append_log(f"Connecting Pedal Remote on {port} at 115200 baud...\n")
        connection = None
        try:
            connection = open_serial_no_reset(port, 115200, timeout=0.25)
            self.connection = connection
            self.update_hw_bank_visibility(1)
            self.update_hardware_indicator(1, "")
            connection.write(b"HWINFO\n")
            self.app.set_status("Pedal Remote connected")
            while self.winfo_exists() and not self.stop_event.is_set():
                line = connection.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                hwinfo = self.parse_hwinfo_line(line)
                if hwinfo:
                    bank_count, amp_name = hwinfo
                    self.after(0, lambda count=bank_count, name=amp_name: (
                        self.update_hw_bank_visibility(count),
                        self.update_hardware_indicator(count, name),
                        self.compact_remote_status(name, count)
                    ))
                    if bank_count >= 2:
                        try:
                            connection.write(b"LOOPER STATUS\n")
                        except Exception:
                            pass
                    self.append_log(line + "\n")
                    continue
                if line.startswith("OK STOREHW"):
                    pending = self.pending_hw_store
                    self.pending_hw_store = None
                    if pending:
                        bank, preset = pending
                        self.after(0, lambda b=bank, p=preset: self.app.set_status(
                            f"Spark hardware preset save confirmed: HW {b}-{p}"
                        ))
                    else:
                        self.after(0, lambda: self.app.set_status("Spark hardware preset save confirmed"))
                    self.append_log(line + "\n")
                    continue
                if line.startswith("PENDING STOREHW"):
                    self.after(0, lambda: self.app.set_status("Spark hardware preset save sent; waiting for amp confirmation"))
                    self.append_log(line + "\n")
                    continue
                if line.startswith("ERR") and "STOREHW" in line:
                    self.pending_hw_store = None
                    self.after(0, lambda value=line: self.app.set_status(value))
                    self.append_log(line + "\n")
                    continue
                remote_event = self.parse_remote_event_line(line)
                if remote_event:
                    self.after(0, lambda value=remote_event: self.handle_remote_event(value))
                    self.append_log(line + "\n")
                    continue
                looper_mode = self.parse_looper_mode_line(line)
                if looper_mode is not None:
                    self.after(0, lambda active=looper_mode: self.update_looper_mode(active))
                    self.append_log(line + "\n")
                    continue
                looper_status = self.parse_looper_status_line(line)
                if looper_status:
                    self.after(0, lambda value=looper_status: self.update_looper_status(value))
                    self.append_log(line + "\n")
                    continue
                parsed = self.parse_tuner_line(line)
                if parsed:
                    self.after(0, lambda values=parsed: self.update_remote_tuner(*values))
                    continue
                self.append_log(line + "\n")
            self.append_log("\nPedal Remote connection ended.\n")
            self.app.set_status("Pedal Remote stopped")
        except Exception as exc:
            self.append_log(f"\nPedal Remote failed: {exc}\n")
            self.app.set_status("Pedal Remote failed")
        finally:
            self.connection = None
            try:
                if connection:
                    connection.close()
            except Exception:
                pass
            self.after(0, lambda: self.update_hardware_indicator(None, ""))
            self.after(0, self.finish)


class CapturePage(SerialPage):
    tool_title = "Spark Capture"
    tool_subtitle = "Capture Spark app presets or back up presets stored on your Ignitron pedal."
    start_text = "Start capture"
    instructions = "Connect Ignitron by USB. For live capture, keep it connected to the Spark app over Bluetooth and send presets from the app. For a pedal backup, put Ignitron in AMP mode and choose one of the pull buttons below."

    def _build_serial_ui(self):
        super()._build_serial_ui()
        self.stop_button = ttk.Button(
            self.start_button.master,
            text="End connection",
            style="Danger.TButton",
            command=self.stop_capture,
            state="disabled",
        )
        self.stop_button.pack(side="right", padx=(0, 10))

        backup = tk.Frame(self.log.master, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        backup.pack(fill="x", padx=22, pady=(0, 16), before=self.log)
        backup_copy = tk.Frame(backup, bg=CARD)
        backup_copy.pack(side="left", fill="x", expand=True, padx=16, pady=13)
        tk.Label(backup_copy, text="PEDAL PRESET BACKUP", bg=CARD, fg=GOLD,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(backup_copy, text="Pull presets from the connected pedal into a timestamped folder under backups.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))
        actions = tk.Frame(backup, bg=CARD)
        actions.pack(side="right", padx=16, pady=13)
        self.pull_active_button = ttk.Button(actions, text="Pull active bank", style="Dark.TButton",
                                             command=lambda: self.start_backup(True))
        self.pull_active_button.pack(side="left", padx=(0, 8))
        self.pull_all_button = ttk.Button(actions, text="Pull full library", style="Gold.TButton",
                                          command=lambda: self.start_backup(False))
        self.pull_all_button.pack(side="left")

    def set_action_state(self, state):
        self.pull_active_button.configure(state=state)
        self.pull_all_button.configure(state=state)

    def start(self):
        super().start()
        if self.running:
            self.stop_button.configure(state="normal")
            self.set_action_state("disabled")

    def start_backup(self, active_only):
        port = self.auto_select_port()
        if not port:
            messagebox.showinfo("Ignitron not found", "Connect Ignitron by USB, then try again.")
            return
        if self.running:
            return
        self.app.request_serial_start(self)
        self.running = True
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.set_action_state("disabled")
        self.update_connection_indicator(True)
        threading.Thread(target=self.run_backup, args=(port, active_only), daemon=True).start()

    def stop_capture(self):
        if not self.running:
            return
        self.append_log("\nStopping current Spark Capture task...\n")
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.app.set_status("Stopping Spark Capture task...")

    def stop_serial(self, reason="another serial tool started"):
        super().stop_serial(reason)
        self.stop_button.configure(state="disabled")

    def finish(self):
        super().finish()
        self.stop_button.configure(state="disabled")
        self.set_action_state("normal")

    def run_backup(self, port, active_only):
        scope = "active bank" if active_only else "full preset library"
        self.append_log(f"Starting {scope} backup from {port}...\n")
        try:
            backup_root = self.app.project_dir / "backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            self.append_log(f"Saving backups to {backup_root}\n")
            module_path = app_dir() / "preset_puller.py"
            spec = importlib.util.spec_from_file_location("ignitron_puller", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            stream = StdoutQueue(self.append_log)
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                module.pull_presets(port, 115200, active_only, False, backup_root, self.stop_event)
            if self.stop_event.is_set():
                self.append_log("\nBackup stopped.\n")
                self.app.set_status("Pedal backup stopped")
            else:
                self.append_log("\nBackup complete.\n")
                open_folder(backup_root)
                self.app.set_status("Pedal backup completed")
        except Exception as exc:
            self.append_log(f"\nBackup failed: {exc}\n")
            self.app.set_status("Pedal backup failed")
        finally:
            self.after(0, self.finish)

    def run_tool(self, port):
        self.append_log(f"Listening on {port} at 115200 baud...\n")
        session = self.app.project_dir / "captures" / time.strftime("presets_%Y%m%d_%H%M%S")
        session.mkdir(parents=True, exist_ok=True)
        self.append_log(f"Saving captures to {session}\n\n")
        connection = None
        try:
            connection = open_serial_no_reset(port, 115200, timeout=0.5)
            buffer = ""
            capturing = False
            last_uuid = None
            while self.winfo_exists() and not self.stop_event.is_set():
                line = connection.readline().decode(errors="ignore").rstrip()
                if not line:
                    continue
                self.append_log(line + "\n")
                if line.startswith("received from app:") or line.startswith("JSON STRING:"):
                    buffer = ""
                    capturing = True
                    continue
                if capturing:
                    buffer += line + "\n"
                    if line.strip().endswith("}"):
                        capturing = False
                        try:
                            preset = json.loads(buffer)
                            uuid = preset.get("UUID")
                            if uuid == last_uuid:
                                continue
                            last_uuid = uuid
                            name = re.sub(r"[^A-Za-z0-9_-]+", "", str(preset.get("Name", "preset"))) or "preset"
                            output = session / f"{name}.json"
                            output.write_text(json.dumps(preset, indent=2), encoding="utf-8")
                            self.append_log(f"SAVED: {output.name}\n")
                            self.app.set_status(f"Captured {output.name}")
                        except Exception as exc:
                            self.append_log(f"Could not parse preset: {exc}\n")
            self.append_log("\nSpark capture connection ended.\n")
            self.app.set_status("Spark capture stopped")
        except Exception as exc:
            self.append_log(f"\nCapture failed: {exc}\n")
            self.app.set_status("Spark capture failed")
        finally:
            try:
                if connection:
                    connection.close()
            except Exception:
                pass
            self.after(0, self.finish)


if __name__ == "__main__":
    IgnitronApp().mainloop()
