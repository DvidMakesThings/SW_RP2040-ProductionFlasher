"""
Global configuration for RP2040 Programmer.

This module contains all configurable parameters used throughout the application.
Modify values here to adjust behavior without changing code.
"""
import os
import sys
from typing import List
from pathlib import Path


class Settings:
    """Global application settings - class-level constants for easy access."""
    
    # Application metadata
    APP_NAME = "RP2040 MCU Programmer"
    VERSION = "1.0.0"
    
    # Platform detection
    PLATFORM = "Windows" if sys.platform == "win32" else "Linux"
    
    # Paths
    ARTEFACT_BASE_PATH = (
        "X:\\Artefacts\\ENERGIS\\Artefacts"
        if sys.platform == "win32"
        else "/home/tpc/_GitHub/HW_10-In-Rack_PDU/docs/Compliance_Documents/Artefacts/"
    )
    TEMPLATE_DIR = (
        "G:\\_GitHub\\HW_10-In-Rack_PDU\\docs\\Compliance_Documents\\src"
        if sys.platform == "win32"
        else "/home/tpc/_GitHub/HW_10-In-Rack_PDU/docs/Compliance_Documents/src/"
    )
    PERSISTENCE_FILE = (
        "G:\\_GitHub\\SW_RP2040-ProductionFlasher\\.settings\\factory_programmer_state.json"
        if sys.platform == "win32"
        else "/home/tpc/_GitHub/SW_RP2040-ProductionFlasher/.settings/factory_programmer_state.json"
    )
    LOG_FILE_PATH = (
        "G:\\_GitHub\\SW_RP2040-ProductionFlasher\\.settings\\logs\\app.log"
        if sys.platform == "win32"
        else "/home/tpc/_GitHub/SW_RP2040-ProductionFlasher/.settings/logs/app.log"
    )
    
    # RP2040 Detection
    RP2040_USB_VID = 0x2E8A  # Raspberry Pi VID
    RP2040_USB_PID_BOOT = 0x0003  # RP2040 in BOOTSEL mode
    RP2040_VOLUME_NAME = "RPI-RP2"  # USB mass storage name when in boot mode
    DEVICE_SCAN_INTERVAL_MS = 1000  # How often to scan for devices
    
    # Picotool configuration
    PICOTOOL_WINDOWS = "C:\\Users\\sdvid\\.pico-sdk\\picotool\\2.2.0-a4\\picotool\\picotool.exe"
    PICOTOOL_LINUX = "/home/tpc/.pico-sdk/picotool/2.2.0-a4/picotool/picotool"
    PICOTOOL_LOAD_ARGS = ["-fx"]
    FIRMWARE_EXTENSIONS = [".elf", ".hex", ".uf2"]
    
    # Serial communication
    SERIAL_BAUDRATE = 115200
    SERIAL_TIMEOUT = 1.0
    SERIAL_WRITE_TIMEOUT = 1.0
    SERIAL_DETECT_TIMEOUT = 5.0  # Max wait for serial port after flash
    SERIAL_READY_TIMEOUT = 10.0  # Max wait for "SYSTEM READY"
    SERIAL_COMMAND_TIMEOUT = 2.0  # Max wait for command response
    SERIAL_REBOOT_WAIT = 10.0  # Wait time after reboot command (devices may take up to 10s)
    SERIAL_RECONNECT_TIMEOUT = 10.0  # Max wait for serial reconnection
    
    # Provisioning commands
    PROV_UNLOCK_CODE = "6D61676963"
    SYSTEM_READY_MARKER = "SYSTEM READY"
    
    # CSV configuration
    CSV_COLUMNS = [
        "serial_number", "date_programmed", "firmware_version",
        "hardware_version", "region_code", "batch_id", "notes"
    ]
    CSV_REPROGRAM_PREFIX = "reprogram_"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Region codes
    REGION_CODES = ["EU", "US"]
    
    # Label configuration
    LABEL_WIDTH_MM = 75
    LABEL_HEIGHT_MM = 50
    LABEL_DPI = 300
    LABEL_TEMPLATE_EU = "ENERGIS_rating_label_EU.svg"
    LABEL_TEMPLATE_US = "ENERGIS_rating_label_US.svg"
    LABEL_SERIAL_PLACEHOLDER = "SERIAL_NUMBER"
    PRINTER_NAME = "PM-241-BT"
    
    # GUI configuration
    WINDOW_MIN_WIDTH = 1024
    WINDOW_MIN_HEIGHT = 768
    LOG_MAX_LINES = 1000
    
    # Timeouts and retries
    MAX_RESET_RETRIES = 3
    RESET_RETRY_DELAY = 1.0
    FIRMWARE_UPLOAD_TIMEOUT = 60  # seconds
    
    @classmethod
    def get_picotool_path(cls) -> str:
        """Get platform-appropriate picotool path."""
        if sys.platform == "win32":
            return cls.PICOTOOL_WINDOWS
        return cls.PICOTOOL_LINUX
    
    @classmethod
    def get_artefact_dir(cls, serial_number: str) -> Path:
        """Get artefact directory for a specific serial number."""
        return Path(cls.ARTEFACT_BASE_PATH) / serial_number
    
    @classmethod
    def get_label_template_path(cls, region: str) -> str:
        """Get full path to label template for region."""
        if region == "US":
            return str(Path(cls.TEMPLATE_DIR) / cls.LABEL_TEMPLATE_US)
        return str(Path(cls.TEMPLATE_DIR) / cls.LABEL_TEMPLATE_EU)


class _ConfigProxy:
    """
    Backward-compatibility proxy exposing a `CONFIG` object API used across the codebase.

    - For most attributes, forwards to `Settings` class attributes.
    - Provides legacy/aliased names expected by some modules (e.g., APP_VERSION, ARTEFACTS_BASE).
    - Exposes helper methods with legacy names (e.g., get_label_template).
    """

    # Explicit aliases expected elsewhere
    APP_VERSION = Settings.VERSION
    ARTEFACTS_BASE = Settings.ARTEFACT_BASE_PATH

    def __getattr__(self, name):
        # Fallback: read any other attribute directly from Settings
        if hasattr(Settings, name):
            return getattr(Settings, name)
        raise AttributeError(f"CONFIG has no attribute '{name}'")

    # Legacy helper expected by label/artefact modules
    def get_picotool_path(self) -> str:
        return Settings.get_picotool_path()

    def get_label_template(self, region: str) -> str:
        # Return template filename (not full path) as expected by label generator
        return Settings.LABEL_TEMPLATE_US if region == "US" else Settings.LABEL_TEMPLATE_EU


# Public compatibility instance
CONFIG = _ConfigProxy()