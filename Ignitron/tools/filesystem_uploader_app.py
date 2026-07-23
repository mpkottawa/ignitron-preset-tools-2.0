"""Ignitron filesystem uploader GUI.

Builds and uploads the PlatformIO LittleFS image from the project's data folder
without rebuilding or uploading firmware.
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Ignitron Filesystem Uploader"
DEFAULT_ENV = "esp32dev"


def default_project_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_platformio() -> str:
    candidates = [
        Path.home() / ".platformio" / "penv" / "Scripts" / "platformio.exe",
        Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "platformio"


def parse_envs(platformio_ini: Path) -> list[str]:
    if not platformio_ini.exists():
        return [DEFAULT_ENV]

    envs: list[str] = []
    for line in platformio_ini.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\[env:([^\]]+)\]", line.strip())
        if match:
            envs.append(match.group(1))
    return envs or [DEFAULT_ENV]


def parse_upload_port(platformio_ini: Path, env_name: str) -> str:
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


def find_missing_presets(data_dir: Path) -> list[str]:
    preset_list = data_dir / "PresetList.txt"
    if not preset_list.exists():
        return ["PresetList.txt is missing"]

    missing: list[str] = []
    for raw_line in preset_list.read_text(encoding="utf-8", errors="replace").splitlines():
        name = raw_line.strip()
        if not name or name.startswith("--"):
            continue
        if not (data_dir / name).exists():
            missing.append(name)
    return missing


class FilesystemUploaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x620")
        self.minsize(780, 500)

        self.project_var = tk.StringVar(value=str(default_project_dir()))
        self.platformio_var = tk.StringVar(value=default_platformio())
        self.env_var = tk.StringVar(value=DEFAULT_ENV)
        self.port_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.allow_missing_var = tk.BooleanVar(value=True)

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_ui()
        self._load_project_defaults()
        self.after(100, self._drain_output_queue)

    @property
    def project_dir(self) -> Path:
        return Path(self.project_var.get()).expanduser().resolve()

    @property
    def platformio_ini(self) -> Path:
        return self.project_dir / "platformio.ini"

    @property
    def data_dir(self) -> Path:
        return self.project_dir / "data"

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        controls = ttk.Frame(root)
        controls.pack(fill="x")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Project").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(controls, textvariable=self.project_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(controls, text="Browse", command=self._browse_project).grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(controls, text="PlatformIO").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(controls, textvariable=self.platformio_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(controls, text="Browse", command=self._browse_platformio).grid(row=1, column=2, padx=(8, 0), pady=4)

        ttk.Label(controls, text="Environment").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        self.env_combo = ttk.Combobox(controls, textvariable=self.env_var, state="readonly", width=28)
        self.env_combo.grid(row=2, column=1, sticky="w", pady=4)
        self.env_combo.bind("<<ComboboxSelected>>", lambda _event: self._load_env_port())

        ttk.Label(controls, text="Upload port").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        port_row = ttk.Frame(controls)
        port_row.grid(row=3, column=1, sticky="ew", pady=4)
        port_row.columnconfigure(0, weight=1)
        ttk.Entry(port_row, textvariable=self.port_var, width=24).grid(row=0, column=0, sticky="w")
        ttk.Button(port_row, text="Use platformio.ini", command=self._load_env_port).grid(row=0, column=1, padx=(8, 0))

        options = ttk.Frame(root)
        options.pack(fill="x", pady=(12, 8))
        ttk.Checkbutton(
            options,
            text="Allow upload when PresetList.txt references missing JSON files",
            variable=self.allow_missing_var,
        ).pack(side="left")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(4, 10))
        self.validate_button = ttk.Button(buttons, text="Validate Data", command=self.validate_data)
        self.validate_button.pack(side="left")
        self.build_button = ttk.Button(buttons, text="Build Filesystem", command=lambda: self.run_target("buildfs"))
        self.build_button.pack(side="left", padx=(8, 0))
        self.upload_button = ttk.Button(buttons, text="Upload Filesystem", command=lambda: self.run_target("uploadfs"))
        self.upload_button.pack(side="left", padx=(8, 0))
        self.both_button = ttk.Button(buttons, text="Build + Upload", command=self.build_and_upload)
        self.both_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Clear Log", command=self._clear_log).pack(side="right")

        ttk.Label(root, textvariable=self.status_var).pack(anchor="w")

        self.log = tk.Text(root, wrap="word", height=24, state="disabled")
        self.log.pack(fill="both", expand=True, pady=(6, 0))

        scrollbar = ttk.Scrollbar(self.log, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _browse_project(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.project_var.get() or str(Path.home()))
        if folder:
            self.project_var.set(folder)
            self._load_project_defaults()

    def _browse_platformio(self) -> None:
        filetypes = [("Executables", "*.exe"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(initialdir=str(Path.home()), filetypes=filetypes)
        if filename:
            self.platformio_var.set(filename)

    def _load_project_defaults(self) -> None:
        envs = parse_envs(self.platformio_ini)
        self.env_combo.configure(values=envs)
        if self.env_var.get() not in envs:
            self.env_var.set(envs[0])
        self._load_env_port()

    def _load_env_port(self) -> None:
        port = parse_upload_port(self.platformio_ini, self.env_var.get())
        if port:
            self.port_var.set(port)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in [self.validate_button, self.build_button, self.upload_button, self.both_button]:
            button.configure(state=state)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_output_queue(self) -> None:
        try:
            while True:
                item = self.output_queue.get_nowait()
                self._append_log(item)
        except queue.Empty:
            pass
        self.after(100, self._drain_output_queue)

    def validate_data(self) -> bool:
        if not self.project_dir.exists():
            messagebox.showerror(APP_TITLE, f"Project folder does not exist:\n{self.project_dir}")
            return False
        if not self.platformio_ini.exists():
            messagebox.showerror(APP_TITLE, f"platformio.ini was not found:\n{self.platformio_ini}")
            return False
        if not self.data_dir.exists():
            messagebox.showerror(APP_TITLE, f"data folder was not found:\n{self.data_dir}")
            return False

        missing = find_missing_presets(self.data_dir)
        json_count = len(list(self.data_dir.glob("*.json")))
        message = f"Data folder: {self.data_dir}\nJSON presets: {json_count}\n"

        if missing:
            message += "\nMissing files referenced by PresetList.txt:\n" + "\n".join(missing[:40])
            if len(missing) > 40:
                message += f"\n...and {len(missing) - 40} more"
            if not self.allow_missing_var.get():
                messagebox.showerror(APP_TITLE, message)
                return False
            messagebox.showwarning(APP_TITLE, message)
            return True

        messagebox.showinfo(APP_TITLE, message + "\nPresetList.txt references all required files.")
        return True

    def build_and_upload(self) -> None:
        self.run_targets(["buildfs", "uploadfs"])

    def run_target(self, target: str) -> None:
        self.run_targets([target])

    def run_targets(self, targets: list[str]) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "A PlatformIO task is already running.")
            return
        if not self.validate_data():
            return

        self._set_busy(True)
        self.status_var.set("Running PlatformIO...")
        self.output_queue.put("\n")

        self.worker = threading.Thread(target=self._run_targets_worker, args=(targets,), daemon=True)
        self.worker.start()

    def _run_targets_worker(self, targets: list[str]) -> None:
        try:
            for target in targets:
                code = self._run_platformio_target(target)
                if code != 0:
                    self.output_queue.put(f"\n{target} failed with exit code {code}\n")
                    self.after(0, lambda: self.status_var.set(f"{target} failed"))
                    return
            self.output_queue.put("\nDone.\n")
            self.after(0, lambda: self.status_var.set("Done"))
        finally:
            self.after(0, lambda: self._set_busy(False))

    def _run_platformio_target(self, target: str) -> int:
        cmd = [
            self.platformio_var.get(),
            "run",
            "-e",
            self.env_var.get(),
            "-t",
            target,
        ]

        port = self.port_var.get().strip()
        if target == "uploadfs" and port:
            cmd.extend(["--upload-port", port])

        self.output_queue.put(f"> {' '.join(cmd)}\n")

        process = subprocess.Popen(
            cmd,
            cwd=str(self.project_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )

        assert process.stdout is not None
        for line in process.stdout:
            self.output_queue.put(line)
        return process.wait()


def main() -> int:
    app = FilesystemUploaderApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
