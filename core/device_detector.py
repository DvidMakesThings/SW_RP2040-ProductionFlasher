"""
RP2040 device detection module.

Detects unprogrammed RP2040 devices appearing as USB mass storage (RPI-RP2).
Also detects programmed devices appearing as serial ports.
"""
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

import psutil
import serial.tools.list_ports

from config.settings import CONFIG
from utils.logger import get_logger


class DeviceState(Enum):
    """State of detected device."""
    BOOTSEL = "bootsel"  # In BOOTSEL mode (mass storage)
    SERIAL = "serial"    # Programmed, appearing as serial port
    UNKNOWN = "unknown"


@dataclass
class DetectedDevice:
    """Represents a detected RP2040 device."""
    device_id: str
    state: DeviceState
    path: str  # Mount path or serial port
    vid: Optional[int] = None
    pid: Optional[int] = None
    serial: Optional[str] = None
    description: str = ""
    
    def __str__(self) -> str:
        if self.state == DeviceState.BOOTSEL:
            return f"RP2040 [BOOTSEL] at {self.path}"
        elif self.state == DeviceState.SERIAL:
            return f"RP2040 [Serial] at {self.path}"
        return f"RP2040 [Unknown] at {self.path}"

# Backward-compatibility alias for GUI import
DeviceInfo = DetectedDevice


class DeviceDetector:
    """
    Monitors for RP2040 devices in both BOOTSEL and serial modes.
    
    Provides callbacks for device connect/disconnect events.
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._devices: Dict[str, DetectedDevice] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Callbacks
        self._on_device_added: Optional[Callable[[DetectedDevice], None]] = None
        self._on_device_removed: Optional[Callable[[DetectedDevice], None]] = None
        self._on_devices_changed: Optional[Callable[[List[DetectedDevice]], None]] = None
    
    def set_callbacks(
        self,
        on_added: Optional[Callable[[DetectedDevice], None]] = None,
        on_removed: Optional[Callable[[DetectedDevice], None]] = None,
        on_changed: Optional[Callable[[List[DetectedDevice]], None]] = None
    ) -> None:
        """Set device event callbacks."""
        self._on_device_added = on_added
        self._on_device_removed = on_removed
        self._on_devices_changed = on_changed

    # Backward-compatibility properties expected by GUI code
    @property
    def on_device_added(self) -> Optional[Callable[[DetectedDevice], None]]:
        return self._on_device_added

    @on_device_added.setter
    def on_device_added(self, cb: Optional[Callable[[DetectedDevice], None]]) -> None:
        self._on_device_added = cb

    @property
    def on_device_removed(self) -> Optional[Callable[[DetectedDevice], None]]:
        return self._on_device_removed

    @on_device_removed.setter
    def on_device_removed(self, cb: Optional[Callable[[DetectedDevice], None]]) -> None:
        self._on_device_removed = cb

    @property
    def on_device_changed(self) -> Optional[Callable[[List[DetectedDevice]], None]]:
        return self._on_devices_changed

    @on_device_changed.setter
    def on_device_changed(self, cb: Optional[Callable[[List[DetectedDevice]], None]]) -> None:
        self._on_devices_changed = cb
    
    def start(self) -> None:
        """Start device monitoring thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self._logger.info("DeviceDetector", "Started device monitoring")
    
    def stop(self) -> None:
        """Stop device monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._logger.info("DeviceDetector", "Stopped device monitoring")
    
    def get_devices(self) -> List[DetectedDevice]:
        """Get list of currently detected devices."""
        with self._lock:
            return list(self._devices.values())
    
    def get_bootsel_devices(self) -> List[DetectedDevice]:
        """Get devices in BOOTSEL mode only."""
        with self._lock:
            return [d for d in self._devices.values() if d.state == DeviceState.BOOTSEL]
    
    def get_serial_devices(self) -> List[DetectedDevice]:
        """Get devices in serial mode only."""
        with self._lock:
            return [d for d in self._devices.values() if d.state == DeviceState.SERIAL]
    
    def has_bootsel_device(self) -> bool:
        """Check if any BOOTSEL device is connected."""
        return len(self.get_bootsel_devices()) > 0
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._scan_devices()
            except Exception as e:
                self._logger.error("DeviceDetector", f"Scan error: {e}")
            
            time.sleep(CONFIG.DEVICE_SCAN_INTERVAL_MS / 1000.0)
    
    def _scan_devices(self) -> None:
        """Scan for RP2040 devices."""
        current_devices: Dict[str, DetectedDevice] = {}
        
        # Scan for BOOTSEL (mass storage) devices
        bootsel = self._scan_bootsel_devices()
        for dev in bootsel:
            current_devices[dev.device_id] = dev
        
        # Scan for serial port devices
        serial_devs = self._scan_serial_devices()
        for dev in serial_devs:
            current_devices[dev.device_id] = dev
        
        # Compare with previous state
        with self._lock:
            old_ids = set(self._devices.keys())
            new_ids = set(current_devices.keys())
            
            added = new_ids - old_ids
            removed = old_ids - new_ids
            
            # Handle removed devices
            for dev_id in removed:
                dev = self._devices[dev_id]
                self._logger.info("DeviceDetector", f"Device removed: {dev}")
                if self._on_device_removed:
                    self._on_device_removed(dev)
            
            # Handle added devices
            for dev_id in added:
                dev = current_devices[dev_id]
                self._logger.info("DeviceDetector", f"Device added: {dev}")
                if self._on_device_added:
                    self._on_device_added(dev)
            
            # Update state
            self._devices = current_devices
            
            # Notify of any changes
            if (added or removed) and self._on_devices_changed:
                self._on_devices_changed(list(self._devices.values()))
    
    def _scan_bootsel_devices(self) -> List[DetectedDevice]:
        """Scan for RP2040 devices in BOOTSEL mode (USB mass storage)."""
        devices: List[DetectedDevice] = []
        candidates: List[str] = []
        
        # 1) Use mounted partitions
        parts = psutil.disk_partitions(all=False)
        for partition in parts:
            mount = partition.mountpoint
            if sys.platform != "win32":
                # Require FAT-like filesystem for UF2 mass storage
                if partition.fstype and partition.fstype.lower() not in ("vfat", "msdos", "fat", "fat32"):
                    continue
            candidates.append(mount)
        
        # 2) On Linux, also probe common paths directly by volume label
        if sys.platform != "win32":
            try:
                from pathlib import Path as _P
                # Explicit per-user mount path probe
                user = _P.home().name
                explicit = _P("/run/media") / user / CONFIG.RP2040_VOLUME_NAME
                if explicit.exists():
                    candidates.append(str(explicit))
                for root in ("/media", "/run/media", "/mnt"):
                    r = _P(root)
                    if not r.exists():
                        continue
                    # Look for directories named by the expected volume label
                    for p in r.glob(f"**/{CONFIG.RP2040_VOLUME_NAME}"):
                        candidates.append(str(p))
                # Check /dev/disk/by-label symlink to locate mount of RPI-RP2
                by_label = _P("/dev/disk/by-label") / CONFIG.RP2040_VOLUME_NAME
                if by_label.exists():
                    try:
                        dev_path = str(by_label.resolve())
                        # Match mounted partitions for this device
                        mounted = False
                        for partition in parts:
                            if partition.device == dev_path:
                                candidates.append(partition.mountpoint)
                                mounted = True
                                break
                        # If not mounted, still record presence for UI visibility
                        if not mounted:
                            candidates.append(str(by_label))
                    except Exception:
                        # Record symlink path even if resolution fails
                        candidates.append(str(by_label))
            except Exception:
                pass
        
        # Deduplicate candidates
        seen = set()
        for mount in candidates:
            if mount in seen:
                continue
            seen.add(mount)
            # If candidate is a by-label path (not a real mount), accept it directly
            is_by_label = mount.startswith("/dev/disk/by-label/")
            if is_by_label:
                device_id = f"bootsel_{mount}"
                devices.append(DetectedDevice(
                    device_id=device_id,
                    state=DeviceState.BOOTSEL,
                    path=mount,
                    vid=CONFIG.RP2040_USB_VID,
                    pid=CONFIG.RP2040_USB_PID_BOOT,
                    description="RP2040 in BOOTSEL mode (not mounted)"
                ))
                continue

            if self._is_rpi_rp2_mount(mount):
                device_id = f"bootsel_{mount}"
                devices.append(DetectedDevice(
                    device_id=device_id,
                    state=DeviceState.BOOTSEL,
                    path=mount,
                    vid=CONFIG.RP2040_USB_VID,
                    pid=CONFIG.RP2040_USB_PID_BOOT,
                    description="RP2040 in BOOTSEL mode"
                ))
        
        return devices
    
    def _is_rpi_rp2_mount(self, mount_path: str) -> bool:
        """Check if mount point is an RPI-RP2 device."""
        mount = Path(mount_path)
        
        # Check for volume name in path (Windows: E:\\, Linux: /media/user/RPI-RP2)
        if CONFIG.RP2040_VOLUME_NAME.lower() in str(mount).lower():
            return True
        
        # Check for INFO_UF2.TXT file (definitive marker). Be robust to permission issues.
        info_file = mount / "INFO_UF2.TXT"
        try:
            exists = info_file.exists()
        except Exception:
            # Permission denied or other filesystem errors: treat as not present
            exists = False
        
        if exists:
            try:
                content = info_file.read_text(errors="ignore")
                if "RP2040" in content or "RPI-RP2" in content:
                    return True
            except Exception:
                # Ignore unreadable files
                pass
        
        return False
    
    def _scan_serial_devices(self) -> List[DetectedDevice]:
        """Scan for RP2040 devices appearing as serial ports."""
        devices = []
        
        for port in serial.tools.list_ports.comports():
            # Check for Raspberry Pi VID
            if port.vid == CONFIG.RP2040_USB_VID:
                device_id = f"serial_{port.device}"
                devices.append(DetectedDevice(
                    device_id=device_id,
                    state=DeviceState.SERIAL,
                    path=port.device,
                    vid=port.vid,
                    pid=port.pid,
                    serial=port.serial_number,
                    description=port.description or "RP2040 Serial"
                ))
        
        return devices
    
    def scan_once(self) -> List[DetectedDevice]:
        """Perform a single scan and return devices (for manual refresh)."""
        self._scan_devices()
        return self.get_devices()

    # Backward-compatibility alias used by GUI
    def scan_now(self) -> List[DetectedDevice]:
        """Compatibility method that performs a single scan and returns devices."""
        return self.scan_once()
    
    def wait_for_serial_port(
        self,
        timeout: float = None,
        exclude_ports: List[str] = None
    ) -> Optional[str]:
        """
        Wait for a new serial port to appear.
        
        Args:
            timeout: Maximum wait time in seconds
            exclude_ports: Ports to ignore (already known)
        
        Returns:
            New port path or None if timeout
        """
        timeout = timeout or CONFIG.SERIAL_DETECT_TIMEOUT
        exclude = set(exclude_ports or [])
        
        # Get initial ports
        initial_ports = {p.device for p in serial.tools.list_ports.comports()}
        initial_ports |= exclude
        
        start = time.time()
        while (time.time() - start) < timeout:
            current_ports = {p.device for p in serial.tools.list_ports.comports()}
            new_ports = current_ports - initial_ports
            
            # Look for RP2040 ports
            for port in serial.tools.list_ports.comports():
                if port.device in new_ports:
                    if port.vid == CONFIG.RP2040_USB_VID:
                        self._logger.info(
                            "DeviceDetector",
                            f"New serial port detected: {port.device}"
                        )
                        return port.device
            
            time.sleep(0.1)
        
        self._logger.warning("DeviceDetector", "Timeout waiting for serial port")
        return None

    def wait_for_serial_reappearance(self, target_port: str, timeout: float = None) -> Optional[str]:
        """
        Wait for a specific serial port to be present (reappear after reboot).

        Args:
            target_port: The COM port (e.g., COM3) expected after reboot
            timeout: Maximum wait time in seconds

        Returns:
            The target port if detected within timeout, else None.
        """
        timeout = timeout or CONFIG.SERIAL_RECONNECT_TIMEOUT
        start = time.time()
        while (time.time() - start) < timeout:
            for port in serial.tools.list_ports.comports():
                if port.device == target_port and port.vid == CONFIG.RP2040_USB_VID:
                    self._logger.info("DeviceDetector", f"Serial port reappeared: {target_port}")
                    return target_port
            time.sleep(0.1)
        self._logger.warning("DeviceDetector", f"Timeout waiting for serial port reappearance: {target_port}")
        return None