"""
Device detection panel for RP2040 Programmer GUI.

Displays detected RP2040 devices and their states.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, List, Optional

from core.device_detector import DeviceDetector, DetectedDevice, DeviceState


class DevicePanel(ttk.LabelFrame):
    """
    Panel displaying detected RP2040 devices.
    
    Shows devices in BOOTSEL mode and serial port mode.
    """
    
    def __init__(
        self,
        parent: tk.Widget,
        device_detector: DeviceDetector,
        on_device_selected: Optional[Callable[[DetectedDevice], None]] = None,
        on_enter_boot_mode: Optional[Callable[[Optional[DetectedDevice]], None]] = None,
    ):
        """
        Initialize device panel.
        
        Args:
            parent: Parent widget
            device_detector: DeviceDetector instance
            on_device_selected: Callback when device is selected
        """
        super().__init__(parent, text="Device Detection", padding=10)
        
        self._detector = device_detector
        self._on_device_selected = on_device_selected
        self._on_enter_boot_mode = on_enter_boot_mode
        self._devices: List[DetectedDevice] = []
        
        self._create_widgets()
        self._setup_detector_callbacks()
        # Populate immediately with a one-time refresh so devices present at startup are shown
        try:
            self._refresh_devices()
        except Exception:
            pass
    
    def _create_widgets(self) -> None:
        """Create panel widgets."""
        # Status indicator
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, pady=(0, 5))
        
        self._status_label = ttk.Label(
            status_frame,
            text="● Scanning...",
            foreground="orange"
        )
        self._status_label.pack(side=tk.LEFT)
        
        # Enter BOOT Mode button
        self._bootsel_btn = ttk.Button(
            status_frame,
            text="Enter BOOT Mode",
            command=self._on_bootsel_clicked,
            width=16
        )
        self._bootsel_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self._refresh_btn = ttk.Button(
            status_frame,
            text="Refresh",
            command=self._refresh_devices,
            width=10
        )
        self._refresh_btn.pack(side=tk.RIGHT)
        
        # Device list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for devices
        columns = ("state", "path", "description")
        self._tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            height=4,
            selectmode="browse"
        )
        
        self._tree.heading("state", text="State")
        self._tree.heading("path", text="Path")
        self._tree.heading("description", text="Description")
        
        self._tree.column("state", width=80, anchor="center")
        self._tree.column("path", width=150)
        self._tree.column("description", width=200)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient=tk.VERTICAL,
            command=self._tree.yview
        )
        self._tree.configure(yscrollcommand=scrollbar.set)
        
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection
        self._tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        
        # Info label
        self._info_label = ttk.Label(
            self,
            text="Connect RP2040 in BOOTSEL mode to begin",
            foreground="gray"
        )
        self._info_label.pack(fill=tk.X, pady=(5, 0))
    
    def _setup_detector_callbacks(self) -> None:
        """Setup device detector callbacks."""
        self._detector.set_callbacks(
            on_changed=self._on_devices_changed
        )
    
    def _refresh_devices(self) -> None:
        """Manual refresh of device list."""
        devices = self._detector.scan_once()
        self._update_device_list(devices)
    
    def _on_devices_changed(self, devices: List[DetectedDevice]) -> None:
        """Handle device list change from detector."""
        # Schedule GUI update on main thread
        self.after(0, lambda: self._update_device_list(devices))
    
    def _update_device_list(self, devices: List[DetectedDevice]) -> None:
        """Update the device treeview."""
        self._devices = devices
        
        # Clear existing items
        for item in self._tree.get_children():
            self._tree.delete(item)
        
        # Add devices
        for dev in devices:
            state_text = "BOOTSEL" if dev.state == DeviceState.BOOTSEL else "Serial"
            self._tree.insert(
                "",
                tk.END,
                iid=dev.device_id,
                values=(state_text, dev.path, dev.description)
            )
        
        # Update status
        bootsel_count = len([d for d in devices if d.state == DeviceState.BOOTSEL])
        serial_count = len([d for d in devices if d.state == DeviceState.SERIAL])
        
        if bootsel_count > 0:
            self._status_label.config(
                text=f"● {bootsel_count} device(s) ready",
                foreground="green"
            )
            self._info_label.config(
                text=f"BOOTSEL: {bootsel_count}, Serial: {serial_count}"
            )
        elif serial_count > 0:
            self._status_label.config(
                text=f"● {serial_count} serial port(s)",
                foreground="blue"
            )
            self._info_label.config(
                text="No BOOTSEL devices - connect device in boot mode"
            )
        else:
            self._status_label.config(
                text="● No devices",
                foreground="orange"
            )
            self._info_label.config(
                text="Connect RP2040 in BOOTSEL mode to begin"
            )
    
    def _on_selection_changed(self, event) -> None:
        """Handle device selection in treeview."""
        selection = self._tree.selection()
        if selection and self._on_device_selected:
            device_id = selection[0]
            for dev in self._devices:
                if dev.device_id == device_id:
                    self._on_device_selected(dev)
                    break

    def _on_bootsel_clicked(self) -> None:
        """Handle Enter BOOT Mode button click."""
        # Prefer selected device if it is a serial device
        target: Optional[DetectedDevice] = self.get_selected_device()
        if not target or target.state != DeviceState.SERIAL:
            # Fallback to first available serial device
            for d in self._devices:
                if d.state == DeviceState.SERIAL:
                    target = d
                    break
        if not target:
            messagebox.showwarning("Enter BOOT Mode", "No RP2040 serial device detected.")
            return
        if self._on_enter_boot_mode:
            try:
                self._on_enter_boot_mode(target)
            except Exception as e:
                messagebox.showerror("Enter BOOT Mode", f"Failed to send BOOTSEL: {e}")
    
    def get_selected_device(self) -> Optional[DetectedDevice]:
        """Get currently selected device."""
        selection = self._tree.selection()
        if not selection:
            return None
        
        device_id = selection[0]
        for dev in self._devices:
            if dev.device_id == device_id:
                return dev
        return None
    
    def has_bootsel_device(self) -> bool:
        """Check if any BOOTSEL device is available."""
        return any(d.state == DeviceState.BOOTSEL for d in self._devices)
    
    def get_bootsel_device(self) -> Optional[DetectedDevice]:
        """Get first available BOOTSEL device."""
        for dev in self._devices:
            if dev.state == DeviceState.BOOTSEL:
                return dev
        return None

    # -----------------------------------------------------------------
    # Compatibility wrapper expected by MainWindow
    # -----------------------------------------------------------------
    def refresh(self) -> None:
        """Refresh the device list display."""
        try:
            devices = self._detector.get_devices()
            self._update_device_list(devices)
        except Exception:
            pass