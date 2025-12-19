"""
Serial provisioning module for ENERGIS PDU.

Handles serial communication for device provisioning after firmware upload.
"""
import time
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

import serial
from serial.tools import list_ports

from config.settings import CONFIG
from utils.logger import get_logger
from core.device_detector import DeviceDetector


class ProvisioningStatus(Enum):
    """Provisioning operation status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PORT_ERROR = "port_error"
    COMMAND_ERROR = "command_error"
    VERIFICATION_FAILED = "verification_failed"


@dataclass
class ProvisioningResult:
    """Result of provisioning operation."""
    status: ProvisioningStatus
    message: str
    serial_number: str = ""
    region: str = ""
    details: dict = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.status == ProvisioningStatus.SUCCESS
    
    # Compatibility alias
    @property
    def responses(self):
        return self.details


class SerialProvisioner:
    """
    Handles serial communication for device provisioning.
    
    Manages connection, command sending, and response parsing.
    """
    
    def __init__(self, logger=None):
        # Allow older call style SerialProvisioner(logger)
        self._logger = logger if logger is not None else get_logger()
        self._serial: Optional[serial.Serial] = None
        self._port: Optional[str] = None
        self._lock = threading.Lock()
        self._rx_buffer: List[str] = []
    
    @property
    def is_connected(self) -> bool:
        """Check if serial connection is active."""
        return self._serial is not None and self._serial.is_open
    
    @property
    def port(self) -> Optional[str]:
        """Get current port name."""
        return self._port
    
    def connect(self, port: str, silence: bool = False) -> bool:
        """
        Connect to serial port.
        
        Args:
            port: Serial port path (e.g., COM3 or /dev/ttyACM0)
            silence: When True, suppress info/success logs (used for quick retries)
        
        Returns:
            True if connection successful
        """
        self.disconnect()
        
        try:
            if not silence:
                self._logger.info("SerialProvisioner", f"Connecting to {port}")
            
            self._serial = serial.Serial(
                port=port,
                baudrate=CONFIG.SERIAL_BAUDRATE,
                timeout=CONFIG.SERIAL_TIMEOUT,
                write_timeout=CONFIG.SERIAL_WRITE_TIMEOUT
            )
            self._port = port
            self._rx_buffer.clear()
            
            # Small delay for connection stabilization
            time.sleep(0.1)
            
            if not silence:
                self._logger.success("SerialProvisioner", f"Connected to {port}")
            return True
        
        except serial.SerialException as e:
            if not silence:
                self._logger.error("SerialProvisioner", f"Connection failed: {e}")
            self._serial = None
            self._port = None
            return False
    
    def disconnect(self) -> None:
        """Disconnect from serial port."""
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
            self._port = None
    
    def reconnect(self, max_retries: int = None) -> bool:
        """
        Attempt to reconnect to the same port.
        
        Args:
            max_retries: Maximum reconnection attempts
        
        Returns:
            True if reconnection successful
        """
        if not self._port:
            return False
        
        port = self._port
        retries = max_retries or CONFIG.MAX_RESET_RETRIES
        
        for attempt in range(retries):
            self._logger.info(
                "SerialProvisioner",
                f"Reconnect attempt {attempt + 1}/{retries}"
            )
            
            self.disconnect()
            time.sleep(CONFIG.RESET_RETRY_DELAY)
            
            if self.connect(port):
                return True
        
        return False
    
    def send_command(
        self,
        command: str,
        timeout: float = None,
        expect_response: bool = True
    ) -> Optional[List[str]]:
        """
        Send command and optionally wait for response.
        
        Args:
            command: Command string to send
            timeout: Response timeout in seconds
            expect_response: Whether to wait for response
        
        Returns:
            List of response lines or None on error
        """
        if not self.is_connected:
            self._logger.error("SerialProvisioner", "Not connected")
            return None
        
        timeout = timeout or CONFIG.SERIAL_COMMAND_TIMEOUT
        
        with self._lock:
            try:
                # Clear input buffer
                self._serial.reset_input_buffer()
                
                # Send command
                cmd_bytes = (command.strip() + "\r\n").encode('utf-8')
                self._logger.log_serial_tx(command.strip())
                self._serial.write(cmd_bytes)
                self._serial.flush()
                
                if not expect_response:
                    return []
                
                # Read response
                return self._read_response(timeout)
            
            except serial.SerialException as e:
                self._logger.error("SerialProvisioner", f"Serial error: {e}")
                return None
    
    def _read_response(self, timeout: float) -> List[str]:
        """Read response lines until timeout or empty line."""
        lines = []
        start = time.time()
        
        while (time.time() - start) < timeout:
            try:
                if self._serial.in_waiting > 0:
                    line = self._serial.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        self._logger.log_serial_rx(line)
                        lines.append(line)
                        # Reset timeout on data received
                        start = time.time()
                else:
                    time.sleep(0.01)
            except:
                break
        
        return lines
    
    def wait_for_ready(self, timeout: float = None) -> bool:
        """
        Wait for "SYSTEM READY" message from device.
        
        Args:
            timeout: Maximum wait time in seconds
        
        Returns:
            True if ready message received
        """
        timeout = timeout or CONFIG.SERIAL_READY_TIMEOUT
        
        if not self.is_connected:
            return False
        
        self._logger.info("SerialProvisioner", "Waiting for SYSTEM READY...")
        start = time.time()
        
        while (time.time() - start) < timeout:
            try:
                if self._serial.in_waiting > 0:
                    line = self._serial.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        self._logger.log_serial_rx(line)
                        # Accept multiple readiness markers
                        if (CONFIG.SYSTEM_READY_MARKER in line) or ("CONSOLE READY" in line.upper()):
                            self._logger.success(
                                "SerialProvisioner",
                                "Device ready"
                            )
                            return True
                else:
                    time.sleep(0.05)
            except serial.SerialException:
                # Port may disconnect during reset
                time.sleep(0.1)
                if not self.reconnect(max_retries=1):
                    break
        
        self._logger.error("SerialProvisioner", "Timeout waiting for SYSTEM READY")
        return False

    def peek_for_ready(self, timeout: float = 2.0, silence: bool = False) -> bool:
        """Quickly read for readiness markers without logging errors on timeout.

        Intended for immediately after reconnect, to avoid missing early boot banners.
        Returns True if a readiness marker is observed within the timeout.

        Args:
            timeout: Max seconds to peek for readiness
            silence: When True, suppress success logging (used to avoid duplicate messages)
        """
        if not self.is_connected:
            return False
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                if self._serial.in_waiting > 0:
                    line = self._serial.readline().decode('utf-8', errors='replace').strip()
                    if line:
                        self._logger.log_serial_rx(line)
                        if (CONFIG.SYSTEM_READY_MARKER in line) or ("CONSOLE READY" in line.upper()):
                            if not silence:
                                self._logger.success("SerialProvisioner", "Device ready")
                            return True
                else:
                    time.sleep(0.02)
            except serial.SerialException:
                break
        return False
    
    def provision_device(
        self,
        serial_number: str,
        region: str
    ) -> ProvisioningResult:
        """
        Run full provisioning sequence on device.
        
        Args:
            serial_number: Device serial number
            region: Region code (EU/US)
        
        Returns:
            ProvisioningResult with status and details
        """
        self._logger.info(
            "SerialProvisioner",
            f"Starting provisioning: SN={serial_number}, Region={region}"
        )
        
        if not self.is_connected:
            return ProvisioningResult(
                status=ProvisioningStatus.PORT_ERROR,
                message="Not connected to device"
            )
        
        # Step 1: Unlock provisioning
        self._logger.info("SerialProvisioner", "Unlocking provisioning mode...")
        response = self.send_command(f"PROV UNLOCK {CONFIG.PROV_UNLOCK_CODE}")
        if not self._check_response_ok(response):
            return ProvisioningResult(
                status=ProvisioningStatus.COMMAND_ERROR,
                message="Failed to unlock provisioning mode"
            )
        
        # Step 2: Set serial number
        self._logger.info("SerialProvisioner", f"Setting serial number: {serial_number}")
        response = self.send_command(f"PROV SET_SN {serial_number}")
        if not self._check_response_ok(response):
            return ProvisioningResult(
                status=ProvisioningStatus.COMMAND_ERROR,
                message="Failed to set serial number"
            )
        
        # Step 3: Set region
        self._logger.info("SerialProvisioner", f"Setting region: {region}")
        response = self.send_command(f"PROV SET_REGION {region}")
        if not self._check_response_ok(response):
            return ProvisioningResult(
                status=ProvisioningStatus.COMMAND_ERROR,
                message="Failed to set region"
            )
        
        # Step 4: Verify provisioning status (allow brief settle time)
        self._logger.info("SerialProvisioner", "Verifying provisioning status...")
        status_info = {}
        attempts = 3
        for i in range(attempts):
            response = self.send_command("PROV STATUS")
            if response:
                status_info = self._parse_status(response)
                if status_info.get('serial_number') and status_info.get('region'):
                    break
            if i < attempts - 1:
                time.sleep(0.5)
        if not status_info:
            return ProvisioningResult(
                status=ProvisioningStatus.COMMAND_ERROR,
                message="Failed to get provisioning status"
            )
        if status_info.get('serial_number') != serial_number:
            return ProvisioningResult(
                status=ProvisioningStatus.VERIFICATION_FAILED,
                message=f"Serial number mismatch: expected {serial_number}, "
                        f"got {status_info.get('serial_number')}"
            )
        
        if status_info.get('region') != region:
            return ProvisioningResult(
                status=ProvisioningStatus.VERIFICATION_FAILED,
                message=f"Region mismatch: expected {region}, "
                        f"got {status_info.get('region')}"
            )
        
        self._logger.success("SerialProvisioner", "Provisioning successful")
        return ProvisioningResult(
            status=ProvisioningStatus.SUCCESS,
            message="Provisioning completed successfully",
            serial_number=serial_number,
            region=region,
            details=status_info
        )

    # Compatibility wrapper expected by GUI
    def provision(self, port: str, serial_number: str, region_code: str) -> ProvisioningResult:
        # Try to connect with brief retries to avoid udev permission race
        connected = False
        for attempt in range(10):
            if self.connect(port, silence=(attempt > 0)):
                connected = True
                break
            time.sleep(0.2)
        if not connected:
            return ProvisioningResult(status=ProvisioningStatus.PORT_ERROR, message="Failed to open port")
        # Consolidated success if connected during a silent attempt
        if attempt > 0:
            self._logger.success("SerialProvisioner", f"Connected to {port}")
        self.wait_for_ready()
        result = self.provision_device(serial_number=serial_number, region=region_code)
        # Perform robust reboot → reappear → reconnect → ready sequence
        _ = self.reboot_and_reconnect_wait_ready()
        return result
    
    def reboot_device(self) -> bool:
        """
        Send reboot command to device.
        
        Returns:
            True if command was sent
        """
        self._logger.info("SerialProvisioner", "Sending reboot command...")
        response = self.send_command("REBOOT", expect_response=False)
        time.sleep(CONFIG.SERIAL_REBOOT_WAIT)
        return response is not None

    def reboot_and_reconnect_wait_ready(self, timeout: float = None) -> Optional[str]:
        """Reboot device, wait for new RP2040 serial port, reconnect, and wait for readiness.

        Args:
            timeout: Max seconds to wait for a new serial port. Defaults to `CONFIG.SERIAL_RECONNECT_TIMEOUT`.

        Returns:
            The new serial port path on success, or None on failure.
        """
        timeout = timeout or CONFIG.SERIAL_RECONNECT_TIMEOUT

        old_port = self._port
        try:
            self._logger.info("SerialProvisioner", "Rebooting device...")
            # Send reboot without waiting; the port will drop shortly
            _ = self.send_command("REBOOT", expect_response=False)
        except Exception:
            pass

        # Wait for any new RP2040 serial port, excluding the previous one
        detector = DeviceDetector()
        exclude = [old_port] if old_port else None
        new_port = detector.wait_for_serial_port(timeout=timeout, exclude_ports=exclude)
        if not new_port:
            self._logger.error("SerialProvisioner", "Serial port did not reappear after reboot")
            return None

        # Suppress noisy port-change logs; proceed to clean connect sequence

        # Connect immediately and wait for readiness (retry briefly to avoid race with udev permissions)
        connected = False
        for attempt in range(10):
            # Suppress per-attempt logs; we will log once upon success
            if self.connect(new_port, silence=True):
                connected = True
                break
            time.sleep(0.2)
        if not connected:
            self._logger.error("SerialProvisioner", f"Unable to open serial port: {new_port}")
            return None
        # Single consolidated connection logs to match desired order
        self._logger.info("SerialProvisioner", f"Connecting to {new_port}")
        self._logger.success("SerialProvisioner", f"Connected to {new_port}")

        # Catch early banners; if seen, emit a single success and skip the extra wait
        if self.peek_for_ready(timeout=1.0, silence=True):
            self._logger.success("SerialProvisioner", "Device ready")
        else:
            if not self.wait_for_ready(timeout=CONFIG.SERIAL_READY_TIMEOUT):
                self._logger.error("SerialProvisioner", "Device did not signal SYSTEM READY after reboot")
                self.disconnect()
                return None

        return new_port

    def enter_boot_mode(self) -> bool:
        """Send BOOTSEL command to force device into BOOTSEL (USB mass storage) mode.

        Returns:
            True if command was sent successfully (write succeeded)
        """
        self._logger.info("SerialProvisioner", "Sending BOOTSEL command...")
        response = self.send_command("BOOTSEL", expect_response=False)
        # Device typically drops serial immediately; caller should handle disappearance
        return response is not None
    
    def get_system_info(self) -> Optional[dict]:
        """
        Get system information from device.
        
        Returns:
            Dict with system info or None on error
        """
        response = self.send_command("SYSINFO", timeout=3.0)
        if not response:
            return None
        return self._parse_info_response(response)
    
    def get_network_info(self) -> Optional[dict]:
        """
        Get network information from device.
        
        Returns:
            Dict with network info or None on error
        """
        response = self.send_command("NETINFO", timeout=3.0)
        if not response:
            return None
        return self._parse_info_response(response)
    
    def _check_response_ok(self, response: Optional[List[str]]) -> bool:
        """Check if response indicates success."""
        if not response:
            return False
        
        for line in response:
            if "OK" in line.upper() or "SUCCESS" in line.upper():
                return True
            if "ERROR" in line.upper() or "FAIL" in line.upper():
                return False
        
        # Assume OK if no explicit error
        return True
    
    def _parse_status(self, response: List[str]) -> dict:
        """Parse PROV STATUS response into dict with normalized keys."""
        result = {'raw': response}
        for line in response:
            # Strip optional log prefix tags like [ECHO], [INFO]
            line = re.sub(r"^\[[^\]]+\]\s*", "", line)
            if ':' in line:
                key, value = line.split(':', 1)
                # Normalize keys: lowercase and replace non-alnum with underscores
                key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower())
                value = value.strip()
                result[key] = value
        # Map common aliases
        if 'serial_number' not in result:
            if 'device_serial' in result:
                result['serial_number'] = result['device_serial']
            elif 'sn' in result:
                result['serial_number'] = result['sn']
            elif 's_n' in result:
                result['serial_number'] = result['s_n']
            elif 'serial' in result:
                result['serial_number'] = result['serial']
        # Normalize region value to code (EU/US)
        if 'region' not in result and 'region_code' in result:
            result['region'] = result['region_code']
        if 'region' in result:
            val = result['region']
            for code in CONFIG.REGION_CODES:
                if code in val:
                    result['region'] = code
                    break
        return result
    
    def _parse_info_response(self, response: List[str]) -> dict:
        """Parse SYSINFO/NETINFO response into dict with normalized keys."""
        result = {'raw': response}
        for line in response:
            # Strip optional log prefix tags
            line = re.sub(r"^\[[^\]]+\]\s*", "", line)
            if ':' in line:
                key, value = line.split(':', 1)
                key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower())
                result[key] = value.strip()
            elif '=' in line:
                key, value = line.split('=', 1)
                key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower())
                result[key] = value.strip()
        # Common aliases for callers
        if 'serial_number' not in result:
            if 'device_serial' in result:
                result['serial_number'] = result['device_serial']
            elif 'sn' in result:
                result['serial_number'] = result['sn']
            elif 's_n' in result:
                result['serial_number'] = result['s_n']
            elif 'serial' in result:
                result['serial_number'] = result['serial']
        if 'region' not in result and 'region_code' in result:
            result['region'] = result['region_code']
        if 'region' in result:
            val = result['region']
            for code in CONFIG.REGION_CODES:
                if code in val:
                    result['region'] = code
                    break
        return result