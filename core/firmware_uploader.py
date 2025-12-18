"""
Firmware upload module using picotool.

Handles firmware upload to RP2040 devices using the picotool command.
"""
import subprocess
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Any

from config.settings import CONFIG
from utils.logger import get_logger


class UploadStatus(Enum):
    """Firmware upload status."""
    SUCCESS = "success"
    FAILED = "failed"
    PICOTOOL_NOT_FOUND = "picotool_not_found"
    FIRMWARE_NOT_FOUND = "firmware_not_found"
    NO_DEVICE = "no_device"
    INVALID_FIRMWARE = "invalid_firmware"


@dataclass
class UploadResult:
    """Result of firmware upload operation."""
    status: UploadStatus
    message: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    
    @property
    def success(self) -> bool:
        return self.status == UploadStatus.SUCCESS


class FirmwareUploader:
    """
    Handles firmware upload to RP2040 using picotool.
    
    Supports ELF, HEX, and UF2 firmware formats.
    """
    
    def __init__(self, picotool_path: Optional[Any] = None):
        """
        Initialize firmware uploader.
        
        Args:
            picotool_path: Custom path to picotool. Uses default if not provided.
        """
        # Allow older call style FirmwareUploader(logger)
        if picotool_path is not None and not isinstance(picotool_path, str):
            self._logger = picotool_path  # type: ignore[assignment]
            self._picotool_path = CONFIG.get_picotool_path()
        else:
            self._logger = get_logger()
            self._picotool_path = (picotool_path or CONFIG.get_picotool_path())  # type: ignore[assignment]
    
    @property
    def picotool_path(self) -> str:
        """Get current picotool path."""
        return self._picotool_path
    
    @picotool_path.setter
    def picotool_path(self, path: str) -> None:
        """Set picotool path."""
        self._picotool_path = path
    
    def verify_picotool(self) -> Tuple[bool, str]:
        """
        Verify picotool is available and working.
        
        Returns:
            Tuple of (success, message)
        """
        if not self._picotool_exists():
            return False, f"picotool not found at: {self._picotool_path}"
        
        try:
            result = subprocess.run(
                [self._picotool_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"picotool found: {version}"
            else:
                return False, f"picotool error: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return False, "picotool timed out"
        except Exception as e:
            return False, f"Error running picotool: {e}"
    
    def verify_firmware(self, firmware_path: str) -> Tuple[bool, str]:
        """
        Verify firmware file exists and has valid extension.
        
        Args:
            firmware_path: Path to firmware file
        
        Returns:
            Tuple of (valid, message)
        """
        path = Path(firmware_path)
        
        if not path.exists():
            return False, f"Firmware file not found: {firmware_path}"
        
        if not path.is_file():
            return False, f"Not a file: {firmware_path}"
        
        ext = path.suffix.lower()
        if ext not in CONFIG.FIRMWARE_EXTENSIONS:
            valid_exts = ", ".join(CONFIG.FIRMWARE_EXTENSIONS)
            return False, f"Invalid firmware extension '{ext}'. Expected: {valid_exts}"
        
        # Check file size (should be reasonable for RP2040)
        size = path.stat().st_size
        if size < 100:
            return False, f"Firmware file too small ({size} bytes)"
        if size > 16 * 1024 * 1024:  # 16MB max
            return False, f"Firmware file too large ({size} bytes)"
        
        return True, f"Firmware valid: {path.name} ({size} bytes)"
    
    def upload(self, firmware_path: str, device_path: Optional[str] = None) -> UploadResult:
        """
        Upload firmware to RP2040 device.
        
        Args:
            firmware_path: Path to firmware file (ELF, HEX, or UF2)
            device_path: Optional device path (ignored; for compatibility)
        
        Returns:
            UploadResult with status and details
        """
        self._logger.info("FirmwareUploader", f"Starting upload: {firmware_path}")
        
        # Verify picotool
        if not self._picotool_exists():
            msg = f"picotool not found at: {self._picotool_path}"
            self._logger.error("FirmwareUploader", msg)
            return UploadResult(
                status=UploadStatus.PICOTOOL_NOT_FOUND,
                message=msg
            )
        
        # Verify firmware
        valid, msg = self.verify_firmware(firmware_path)
        if not valid:
            self._logger.error("FirmwareUploader", msg)
            return UploadResult(
                status=UploadStatus.FIRMWARE_NOT_FOUND,
                message=msg
            )
        
        # Build command
        cmd = [self._picotool_path, "load", firmware_path] + CONFIG.PICOTOOL_LOAD_ARGS
        self._logger.info("FirmwareUploader", f"Command: {' '.join(cmd)}")
        
        try:
            # Run picotool
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout for upload
            )
            
            self._logger.debug("FirmwareUploader", f"Exit code: {result.returncode}")
            self._logger.debug("FirmwareUploader", f"stdout: {result.stdout}")
            if result.stderr:
                self._logger.debug("FirmwareUploader", f"stderr: {result.stderr}")
            
            if result.returncode == 0:
                self._logger.success("FirmwareUploader", "Firmware uploaded successfully")
                return UploadResult(
                    status=UploadStatus.SUCCESS,
                    message="Firmware uploaded successfully",
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr
                )
            else:
                # Check for common errors
                error_msg = result.stderr or result.stdout
                
                if "No accessible RP2040" in error_msg:
                    status = UploadStatus.NO_DEVICE
                    msg = "No RP2040 device found in BOOTSEL mode"
                else:
                    status = UploadStatus.FAILED
                    msg = f"Upload failed: {error_msg}"
                
                self._logger.error("FirmwareUploader", msg)
                return UploadResult(
                    status=status,
                    message=msg,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr
                )
        
        except subprocess.TimeoutExpired:
            msg = "Firmware upload timed out (60s)"
            self._logger.error("FirmwareUploader", msg)
            return UploadResult(
                status=UploadStatus.FAILED,
                message=msg
            )
        
        except Exception as e:
            msg = f"Error during upload: {e}"
            self._logger.error("FirmwareUploader", msg)
            return UploadResult(
                status=UploadStatus.FAILED,
                message=msg
            )
    
    def get_device_info(self) -> Optional[dict]:
        """
        Get information about connected RP2040 device using picotool.
        
        Returns:
            Device info dict or None if not available
        """
        if not self._picotool_exists():
            return None
        
        try:
            result = subprocess.run(
                [self._picotool_path, "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return {"info": result.stdout}
            return None
        
        except:
            return None
    
    def reboot_device(self) -> bool:
        """
        Reboot the RP2040 device using picotool.
        
        Returns:
            True if reboot command succeeded
        """
        if not self._picotool_exists():
            return False
        
        try:
            result = subprocess.run(
                [self._picotool_path, "reboot"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _picotool_exists(self) -> bool:
        """Check if picotool executable exists."""
        path = Path(self._picotool_path)
        return path.exists() and path.is_file()