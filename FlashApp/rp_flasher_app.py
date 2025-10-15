#!/usr/bin/env python3
"""
RPFlasher_UI_final.py
Minimal, pragmatic GUI-only frontend for RP_flasher.py / flasher_core.py

- No flashing logic here. Only shells out to your existing CLI.
- Clean sidebar groups: Project, Flash, Production
- Terminal takes the whole right side
- Persists user inputs (except the hardcoded paths) to ~/.rpflasher_ui.json
"""

import os
import sys
import json
import threading
import subprocess
import queue
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

APP_TITLE = "RP2040 Programmer"
PYTHON = sys.executable
SETTINGS_PATH = Path.home() / ".rpflasher_ui.json"

CONFIG_PATH_FIXED = r"G:\_GitHub\SW_RP2040-ProductionFlasher\FlashApp\flasher_config.py"
SERIAL_TEMPLATE_FIXED = r"G:\_GitHub\SW_RP2040-ProductionFlasher\FlashApp\Templates\serial_number.h.template"

def which_cli():
    here = Path(__file__).resolve().parent
    rp = here / "RP_flasher.py"
    if rp.exists():
        return str(rp)
    fc = here / "flasher_core.py"
    if fc.exists():
        return str(fc)
    return "RP_flasher.py"

def load_settings():
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_settings(data: dict):
    try:
        SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

class ProcessRunner:
    def __init__(self, on_line, on_done):
        self._proc = None
        self._q = queue.Queue()
        self._on_line = on_line
        self._on_done = on_done

    def run_async(self, cmd, cwd=None):
        def reader(pipe, label):
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    self._q.put((label, line.rstrip("\n")))
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        def worker():
            try:
                self._proc = subprocess.Popen(
                    cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1, universal_newlines=True
                )
            except Exception as e:
                self._on_line("ERR", f"[spawn] {e}")
                self._on_done(-1)
                return

            t_out = threading.Thread(target=reader, args=(self._proc.stdout, "OUT"), daemon=True)
            t_err = threading.Thread(target=reader, args=(self._proc.stderr, "ERR"), daemon=True)
            t_out.start(); t_err.start()

            while True:
                if self._proc.poll() is not None and self._q.empty():
                    break
                try:
                    src, line = self._q.get(timeout=0.1)
                    self._on_line(src, line)
                except queue.Empty:
                    pass

            rc = self._proc.wait()
            self._on_done(rc)

        threading.Thread(target=worker, daemon=True).start()

    def terminate(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

class LabeledEntry(ctk.CTkFrame):
    def __init__(self, master, label, textvariable, button_text=None, button_cmd=None, width=420):
        super().__init__(master)
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.entry = ctk.CTkEntry(self, textvariable=textvariable, width=width)
        self.entry.grid(row=0, column=1, sticky="we", padx=6, pady=4)
        if button_text and button_cmd:
            ctk.CTkButton(self, text=button_text, width=90, command=button_cmd).grid(row=0, column=2, padx=6, pady=4)

class GroupBox(ctk.CTkFrame):
    def __init__(self, master, title):
        super().__init__(master, corner_radius=12)
        ctk.CTkLabel(self, text=title, font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=12, pady=(10,0))

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x760")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.settings = load_settings()

        # Shared state
        self.project_dir = tk.StringVar(value=self.settings.get("project_dir", ""))
        self.verbose = tk.BooleanVar(value=self.settings.get("verbose", False)) 

        # Production state
        self.csv_path = tk.StringVar(value=self.settings.get("csv_path", ""))
        self.programmed_by = tk.StringVar(value=self.settings.get("programmed_by", ""))
        self.fw_version = tk.StringVar(value=self.settings.get("fw_version", "1.0.0"))
        self.prod_force = tk.BooleanVar(value=self.settings.get("prod_force", False))
        self.prod_reprogram = tk.BooleanVar(value=self.settings.get("prod_reprogram", False))
        self.prod_skipverify = tk.BooleanVar(value=self.settings.get("prod_skipverify", False))
        self.prod_units = tk.IntVar(value=self.settings.get("prod_units", 1))
        self.prod_stop_on_error = tk.BooleanVar(value=self.settings.get("prod_stop_on_error", False))
        self.prod_retry = tk.IntVar(value=self.settings.get("prod_retry", 0))

        # Flash state
        self.flash_clean = tk.BooleanVar(value=self.settings.get("flash_clean", False))
        self.flash_configure = tk.BooleanVar(value=self.settings.get("flash_configure", False))
        self.flash_build = tk.BooleanVar(value=self.settings.get("flash_build", False))
        self.flash_rebuild = tk.BooleanVar(value=self.settings.get("flash_rebuild", False))
        self.flash_force = tk.BooleanVar(value=self.settings.get("flash_force", False))
        self.flash_reprogram = tk.BooleanVar(value=self.settings.get("flash_reprogram", False))
        self.flash_skipverify = tk.BooleanVar(value=self.settings.get("flash_skipverify", False))

        self._build_ui()
        self._append("[ready] GUI")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Main layout: left sidebar groups, right terminal full height
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(container, width=360, corner_radius=12)
        sidebar.grid(row=0, column=0, sticky="nswe", padx=(0,10), pady=0)
        sidebar.grid_rowconfigure(99, weight=1)

        # Group: Project
        grp_paths = GroupBox(sidebar, "Project")
        grp_paths.pack(fill="x", padx=10, pady=(10,6))
        LabeledEntry(grp_paths, "Project Dir", self.project_dir, "Browse…", self.pick_project).pack(fill="x", padx=8, pady=4)
        ctk.CTkCheckBox(grp_paths, text="Verbose (-v)", variable=self.verbose).pack(anchor="w", padx=14, pady=(6,10))

        # Group: Flash
        grp_flash = GroupBox(sidebar, "Flash (single)")
        grp_flash.pack(fill="x", padx=10, pady=6)
        grid = ctk.CTkFrame(grp_flash)
        grid.pack(fill="x", padx=8, pady=4)
        ctk.CTkCheckBox(grid, text="Clean", variable=self.flash_clean).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Configure", variable=self.flash_configure).grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Build", variable=self.flash_build).grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Rebuild", variable=self.flash_rebuild).grid(row=1, column=0, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Force", variable=self.flash_force).grid(row=1, column=1, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Reprogram", variable=self.flash_reprogram).grid(row=1, column=2, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(grid, text="Skip Verify", variable=self.flash_skipverify).grid(row=2, column=0, padx=6, pady=4, sticky="w")
        ctk.CTkButton(grp_flash, text="Run Flash", command=self.on_flash_run).pack(fill="x", padx=8, pady=(6,10))

        # Group: Production
        grp_prod = GroupBox(sidebar, "Production Flash")
        grp_prod.pack(fill="x", padx=10, pady=6)
        LabeledEntry(grp_prod, "Serial CSV", self.csv_path, "Browse…", self.pick_csv).pack(fill="x", padx=8, pady=4)
        LabeledEntry(grp_prod, "Programmed By", self.programmed_by).pack(fill="x", padx=8, pady=4)
        LabeledEntry(grp_prod, "Firmware Ver", self.fw_version).pack(fill="x", padx=8, pady=4)

        row2 = ctk.CTkFrame(grp_prod)
        row2.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row2, text="Units").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        self.ent_units = ctk.CTkEntry(row2, textvariable=self.prod_units, width=90)
        self.ent_units.grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(row2, text="Stop on Error", variable=self.prod_stop_on_error).grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ctk.CTkLabel(row2, text="Retries").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        self.ent_retry = ctk.CTkEntry(row2, textvariable=self.prod_retry, width=90)
        self.ent_retry.grid(row=1, column=1, padx=6, pady=4, sticky="w")

        row3 = ctk.CTkFrame(grp_prod)
        row3.pack(fill="x", padx=8, pady=4)
        ctk.CTkCheckBox(row3, text="Force", variable=self.prod_force).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(row3, text="Reprogram", variable=self.prod_reprogram).grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ctk.CTkCheckBox(row3, text="Skip Verify", variable=self.prod_skipverify).grid(row=0, column=2, padx=6, pady=4, sticky="w")

        row4 = ctk.CTkFrame(grp_prod)
        row4.pack(fill="x", padx=8, pady=(4,10))
        ctk.CTkButton(row4, text="Flash Next Unit", command=lambda: self.on_prod_run(count=1)).grid(row=0, column=0, padx=6, pady=4, sticky="we")
        ctk.CTkButton(row4, text="Flash Batch", command=self.on_prod_batch).grid(row=0, column=1, padx=6, pady=4, sticky="we")
        row4.grid_columnconfigure((0,1), weight=1)

        # Right: Terminal full height
        right = ctk.CTkFrame(container, corner_radius=12)
        right.grid(row=0, column=1, sticky="nswe")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right, text="Terminal").grid(row=0, column=0, sticky="w", padx=12, pady=(10,0))

        self.txt = tk.Text(right, height=18, bg="#0d1117", fg="#c9d1d9", insertbackground="#c9d1d9", bd=0, relief="flat")
        self.txt.grid(row=1, column=0, sticky="nswe", padx=10, pady=10)

        btns = ctk.CTkFrame(right)
        btns.grid(row=2, column=0, sticky="e", padx=10, pady=(0,10))
        ctk.CTkButton(btns, text="Stop", command=self.stop_run).pack(side="right", padx=6)

    # Helpers
    def _append(self, line: str):
        self.txt.insert("end", line + "\n")
        self.txt.see("end")

    def _common_flags(self):
        flags = []
        if self.project_dir.get().strip():
            flags += ["--project-dir", self.project_dir.get().strip()]
        # Hardcoded config
        flags += ["--config", CONFIG_PATH_FIXED]
        if self.verbose.get():
            flags += ["-v"]
        return flags

    def _run_cmd(self, args_list, cwd=None):
        cli = which_cli()
        cmd = [PYTHON, cli] + args_list
        self._append(f"$ {' '.join(cmd)}")
        self.runner = ProcessRunner(on_line=self._on_line, on_done=self._on_done)
        self.runner.run_async(cmd, cwd=cwd)

    def _on_line(self, src, line):
        prefix = "" if src == "OUT" else "[ERR] "
        self._append(prefix + line)

    def _on_done(self, rc):
        self._append(f"[done] exit code {rc}")

    def stop_run(self):
        try:
            self.runner.terminate()
        except Exception:
            pass
        self._append("[signal] terminate requested")

    # Browse callbacks
    def pick_project(self):
        d = filedialog.askdirectory(title="Select Project Directory")
        if d:
            self.project_dir.set(d)
            self._persist()

    def pick_csv(self):
        p = filedialog.askopenfilename(title="Select serial CSV", filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if p:
            self.csv_path.set(p)
            self._persist()

    # Actions
    def on_flash_run(self):
        flags = self._common_flags()
        if self.flash_clean.get(): flags += ["--clean"]
        if self.flash_configure.get(): flags += ["--configure"]
        if self.flash_build.get(): flags += ["--build"]
        if self.flash_rebuild.get(): flags += ["--rebuild"]
        if self.flash_force.get(): flags += ["--force"]
        if self.flash_reprogram.get(): flags += ["--reprogram"]
        if self.flash_skipverify.get(): flags += ["--skip-verify"]
        flags += ["--deploy"]
        self._persist()
        self._run_cmd(flags)

    def on_prod_batch(self):
        try:
            n = int(self.prod_units.get())
        except Exception:
            n = 1
        self.on_prod_run(count=max(1, n))

    def on_prod_run(self, count=1):
        csvp = self.csv_path.get().strip()
        if not csvp:
            messagebox.showerror("Missing CSV", "Select a serial numbers CSV.")
            return
        flags = self._common_flags() + ["--production", csvp]
        # Hardcoded serial template
        flags += ["--serial-template", SERIAL_TEMPLATE_FIXED]
        if self.programmed_by.get().strip():
            flags += ["--programmed-by", self.programmed_by.get().strip()]
        if self.fw_version.get().strip():
            flags += ["--firmware-version", self.fw_version.get().strip()]
        if self.prod_force.get(): flags += ["--force"]
        if self.prod_reprogram.get(): flags += ["--reprogram"]
        if self.prod_skipverify.get(): flags += ["--skip-verify"]

        self._persist()

        def run_batch():
            cli = which_cli()
            for i in range(count):
                cmd = [PYTHON, cli] + flags
                self._append(f"$ [{i+1:02d}] {' '.join(cmd)}")
                try:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, bufsize=1, universal_newlines=True
                    )
                except Exception as e:
                    self._append(f"[spawn-error] {e}")
                    break
                for line in proc.stdout:
                    self._on_line("OUT", line.rstrip("\n"))
                for line in proc.stderr:
                    self._on_line("ERR", line.rstrip("\n"))
                rc = proc.wait()
                self._append(f"[unit {i+1}/{count}] exit code {rc}")
                if rc != 0 and self.prod_stop_on_error.get():
                    self._append("[batch] stop on error")
                    break
            self._append("[batch] done")

        threading.Thread(target=run_batch, daemon=True).start()

    def _persist(self):
        data = {
            "project_dir": self.project_dir.get(),
            "verbose": self.verbose.get(),
            "csv_path": self.csv_path.get(),
            "programmed_by": self.programmed_by.get(),
            "fw_version": self.fw_version.get(),
            "prod_force": self.prod_force.get(),
            "prod_reprogram": self.prod_reprogram.get(),
            "prod_skipverify": self.prod_skipverify.get(),
            "prod_units": self.prod_units.get(),
            "prod_stop_on_error": self.prod_stop_on_error.get(),
            "prod_retry": self.prod_retry.get(),
            "flash_clean": self.flash_clean.get(),
            "flash_configure": self.flash_configure.get(),
            "flash_build": self.flash_build.get(),
            "flash_rebuild": self.flash_rebuild.get(),
            "flash_force": self.flash_force.get(),
            "flash_reprogram": self.flash_reprogram.get(),
            "flash_skipverify": self.flash_skipverify.get(),
        }
        save_settings(data)

    def on_close(self):
        self._persist()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
