"""
Provisioning panel for RP2040 Programmer GUI.

Contains input fields and controls for the provisioning process.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Callable, Dict, Optional

from config.settings import CONFIG
from utils.persistence import PersistenceManager


class ProvisioningPanel(ttk.LabelFrame):
    """
    Panel containing provisioning inputs and controls.
    
    Manages firmware selection, version inputs, and action buttons.
    """
    
    def __init__(
        self,
        parent: tk.Widget,
        persistence: PersistenceManager,
        on_start_programming: Optional[Callable[[], None]] = None
    ):
        """
        Initialize provisioning panel.
        
        Args:
            parent: Parent widget
            persistence: PersistenceManager for value persistence
            on_start_programming: Callback when Start button clicked
        """
        super().__init__(parent, text="Provisioning Settings", padding=10)
        
        self._persistence = persistence
        # Public callbacks for compatibility with MainWindow
        self.on_start: Optional[Callable[[], None]] = on_start_programming
        self.on_stop: Optional[Callable[[], None]] = None
        
        self._create_widgets()
        self._load_persisted_values()
    
    def _create_widgets(self) -> None:
        """Create panel widgets."""
        # Firmware selection
        fw_frame = ttk.LabelFrame(self, text="Firmware", padding=5)
        fw_frame.pack(fill=tk.X, pady=(0, 10))
        
        fw_path_frame = ttk.Frame(fw_frame)
        fw_path_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(fw_path_frame, text="File:").pack(side=tk.LEFT)
        
        self._firmware_path_var = tk.StringVar()
        self._firmware_entry = ttk.Entry(
            fw_path_frame,
            textvariable=self._firmware_path_var,
            width=40
        )
        self._firmware_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self._browse_fw_btn = ttk.Button(
            fw_path_frame,
            text="Browse...",
            command=self._browse_firmware
        )
        self._browse_fw_btn.pack(side=tk.LEFT)
        
        # Picotool path (Linux only)
        import sys
        if sys.platform != "win32":
            picotool_frame = ttk.Frame(fw_frame)
            picotool_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(picotool_frame, text="picotool:").pack(side=tk.LEFT)
            
            self._picotool_path_var = tk.StringVar(value=CONFIG.PICOTOOL_LINUX)
            self._picotool_entry = ttk.Entry(
                picotool_frame,
                textvariable=self._picotool_path_var,
                width=40
            )
            self._picotool_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            self._browse_picotool_btn = ttk.Button(
                picotool_frame,
                text="Browse...",
                command=self._browse_picotool
            )
            self._browse_picotool_btn.pack(side=tk.LEFT)
        else:
            self._picotool_path_var = tk.StringVar(value=CONFIG.PICOTOOL_WINDOWS)
        
        # Version and settings
        settings_frame = ttk.LabelFrame(self, text="Settings", padding=5)
        settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid layout for settings
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)
        
        # Firmware version
        ttk.Label(settings_grid, text="Firmware Version:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        self._fw_version_var = tk.StringVar()
        self._fw_version_entry = ttk.Entry(
            settings_grid,
            textvariable=self._fw_version_var,
            width=20
        )
        self._fw_version_entry.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        
        # Hardware version
        ttk.Label(settings_grid, text="Hardware Version:").grid(
            row=0, column=2, sticky=tk.W, pady=2, padx=(20, 0)
        )
        self._hw_version_var = tk.StringVar()
        self._hw_version_entry = ttk.Entry(
            settings_grid,
            textvariable=self._hw_version_var,
            width=20
        )
        self._hw_version_entry.grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
        
        # Region code
        ttk.Label(settings_grid, text="Region:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        self._region_var = tk.StringVar()
        self._region_combo = ttk.Combobox(
            settings_grid,
            textvariable=self._region_var,
            values=CONFIG.REGION_CODES,
            state="readonly",
            width=17
        )
        self._region_combo.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)
        
        # Batch ID
        ttk.Label(settings_grid, text="Batch ID:").grid(
            row=1, column=2, sticky=tk.W, pady=2, padx=(20, 0)
        )
        self._batch_var = tk.StringVar()
        self._batch_entry = ttk.Entry(
            settings_grid,
            textvariable=self._batch_var,
            width=20
        )
        self._batch_entry.grid(row=1, column=3, padx=5, pady=2, sticky=tk.W)
        
        # Notes
        notes_frame = ttk.Frame(settings_frame)
        notes_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(notes_frame, text="Notes:").pack(side=tk.LEFT)
        
        self._notes_var = tk.StringVar()
        self._notes_entry = ttk.Entry(
            notes_frame,
            textvariable=self._notes_var,
            width=50
        )
        self._notes_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Options
        options_frame = ttk.LabelFrame(self, text="Options", padding=5)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self._auto_print_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Auto-print label after programming",
            variable=self._auto_print_var
        ).pack(side=tk.LEFT, padx=5)
        
        self._auto_next_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Auto-select next unit",
            variable=self._auto_next_var
        ).pack(side=tk.LEFT, padx=20)
        
        # Action buttons
        action_frame = ttk.Frame(self)
        action_frame.pack(fill=tk.X)
        
        self._start_btn = ttk.Button(
            action_frame,
            text="▶ Start Programming",
            command=self._on_start_clicked,
            style="Accent.TButton"
        )
        self._start_btn.pack(side=tk.LEFT, padx=5)
        
        self._stop_btn = ttk.Button(
            action_frame,
            text="⏹ Stop",
            command=self._on_stop_clicked,
            state=tk.DISABLED
        )
        self._stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self._status_var = tk.StringVar(value="Ready")
        self._status_label = ttk.Label(
            action_frame,
            textvariable=self._status_var,
            foreground="gray"
        )
        self._status_label.pack(side=tk.RIGHT, padx=10)
    
    def _load_persisted_values(self) -> None:
        """Load previously used values from persistence."""
        values = self._persistence.get_provisioning_values()
        
        self._fw_version_var.set(values.get('firmware_version', ''))
        self._hw_version_var.set(values.get('hardware_version', ''))
        self._region_var.set(values.get('region_code', 'EU'))
        self._batch_var.set(values.get('batch_id', ''))
        self._notes_var.set(values.get('notes', ''))
        
        # Load paths
        fw_path = self._persistence.get('last_firmware_path', '')
        if fw_path:
            self._firmware_path_var.set(fw_path)
        
        picotool_path = self._persistence.get('last_picotool_path', '')
        if picotool_path:
            self._picotool_path_var.set(picotool_path)
    
    def _save_values(self) -> None:
        """Save current values to persistence."""
        self._persistence.save_provisioning_values(
            firmware_version=self._fw_version_var.get(),
            hardware_version=self._hw_version_var.get(),
            region_code=self._region_var.get(),
            batch_id=self._batch_var.get(),
            notes=self._notes_var.get()
        )
        
        self._persistence.set('last_firmware_path', self._firmware_path_var.get())
        self._persistence.set('last_picotool_path', self._picotool_path_var.get())
    
    def _browse_firmware(self) -> None:
        """Open file browser for firmware selection."""
        filetypes = [
            ("Firmware files", "*.elf *.hex *.uf2"),
            ("ELF files", "*.elf"),
            ("HEX files", "*.hex"),
            ("UF2 files", "*.uf2"),
            ("All files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Select Firmware",
            filetypes=filetypes
        )
        
        if filepath:
            self._firmware_path_var.set(filepath)
            self._persistence.set('last_firmware_path', filepath)
            self._persistence.add_recent_firmware(filepath)
    
    def _browse_picotool(self) -> None:
        """Open file browser for picotool selection."""
        filepath = filedialog.askopenfilename(
            title="Select picotool",
            filetypes=[
                ("Executable", "*"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            self._picotool_path_var.set(filepath)
            self._persistence.set('last_picotool_path', filepath)
    
    def _on_start_clicked(self) -> None:
        """Handle Start button click."""
        self._save_values()
        if self.on_start:
            self.on_start()
    
    def _on_stop_clicked(self) -> None:
        """Handle Stop button click."""
        if self.on_stop:
            self.on_stop()

    # -----------------------------------------------------------------
    # Compatibility shims expected by MainWindow
    # -----------------------------------------------------------------
    def get_parameters(self) -> Dict[str, str]:
        values = self.get_values()
        opts = self.get_options()
        # Map to expected keys
        return {
            **values,
            'auto_print_label': opts.get('auto_print', False),
            'auto_select_next': opts.get('auto_next', False)
        }
    
    def set_programming_active(self, active: bool) -> None:
        self.set_programming_state(active)
    
    def set_device_ready(self, ready: bool) -> None:
        self.set_status("Device ready" if ready else "Waiting for device", "green" if ready else "gray")
    
    def set_csv_ready(self, ready: bool) -> None:
        # Simple status hint; could be expanded
        if ready:
            self.set_status("CSV loaded", "blue")
    
    def set_serial_number(self, serial: str) -> None:
        # No serial field in panel; noop for compatibility
        return
    
    def browse_firmware(self) -> None:
        self._browse_firmware()
    
    def get_values(self) -> Dict[str, str]:
        """Get all current input values."""
        return {
            'firmware_path': self._firmware_path_var.get(),
            'picotool_path': self._picotool_path_var.get(),
            'firmware_version': self._fw_version_var.get(),
            'hardware_version': self._hw_version_var.get(),
            'region_code': self._region_var.get(),
            'batch_id': self._batch_var.get(),
            'notes': self._notes_var.get()
        }
    
    def get_options(self) -> Dict[str, bool]:
        """Get option checkbox states."""
        return {
            'auto_print': self._auto_print_var.get(),
            'auto_next': self._auto_next_var.get()
        }
    
    def set_status(self, text: str, color: str = "gray") -> None:
        """Set status label text and color."""
        self._status_var.set(text)
        self._status_label.config(foreground=color)
    
    def set_programming_state(self, is_programming: bool) -> None:
        """Update UI state during programming."""
        if is_programming:
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
            self._firmware_entry.config(state=tk.DISABLED)
            self._fw_version_entry.config(state=tk.DISABLED)
            self._hw_version_entry.config(state=tk.DISABLED)
            self._region_combo.config(state=tk.DISABLED)
            self._batch_entry.config(state=tk.DISABLED)
            self._notes_entry.config(state=tk.DISABLED)
        else:
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)
            self._firmware_entry.config(state=tk.NORMAL)
            self._fw_version_entry.config(state=tk.NORMAL)
            self._hw_version_entry.config(state=tk.NORMAL)
            self._region_combo.config(state="readonly")
            self._batch_entry.config(state=tk.NORMAL)
            self._notes_entry.config(state=tk.NORMAL)
    
    def validate_inputs(self) -> list[str]:
        """
        Validate all required inputs.
        
        Returns:
            List of error messages (empty if valid)
        """
        values = self.get_values()
        errors: list[str] = []
        if not values['firmware_path']:
            errors.append("Please select a firmware file")
        if not values['firmware_version']:
            errors.append("Please enter firmware version")
        if not values['hardware_version']:
            errors.append("Please enter hardware version")
        if not values['region_code']:
            errors.append("Please select a region")
        return errors