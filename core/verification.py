"""
Post-reboot verification module.

Verifies device configuration persisted correctly after reboot.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from config.settings import CONFIG
from utils.logger import get_logger
from core.serial_provisioner import SerialProvisioner


class VerificationStatus(Enum):
    """Verification result status."""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass
class VerificationCheck:
    """Single verification check result."""
    name: str
    expected: str
    actual: str
    passed: bool
    message: str = ""


@dataclass
class VerificationResult:
    """Complete verification result."""
    status: VerificationStatus
    message: str
    checks: List[VerificationCheck] = field(default_factory=list)
    sysinfo: Dict[str, str] = field(default_factory=dict)
    netinfo: Dict[str, str] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.status == VerificationStatus.PASSED
    
    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)
    
    def add_check(
        self,
        name: str,
        expected: str,
        actual: str,
        message: str = ""
    ) -> bool:
        """Add a verification check."""
        passed = expected.strip().lower() == actual.strip().lower()
        self.checks.append(VerificationCheck(
            name=name,
            expected=expected,
            actual=actual,
            passed=passed,
            message=message
        ))
        return passed


class Verifier:
    """
    Verifies device configuration after programming and reboot.
    
    Checks that serial number, region, firmware version, and hardware
    version all match expected values.
    """
    
    def __init__(self, provisioner: SerialProvisioner):
        """
        Initialize verifier.
        
        Args:
            provisioner: SerialProvisioner instance for communication
        """
        self._logger = get_logger()
        self._provisioner = provisioner
    
    def verify(
        self,
        serial_number: str,
        region: str,
        firmware_version: str,
        hardware_version: str
    ) -> VerificationResult:
        """
        Run complete verification sequence.
        
        Args:
            serial_number: Expected serial number
            region: Expected region code
            firmware_version: Expected firmware version
            hardware_version: Expected hardware version
        
        Returns:
            VerificationResult with all check results
        """
        self._logger.info("Verifier", "Starting verification sequence")
        
        result = VerificationResult(
            status=VerificationStatus.ERROR,
            message=""
        )
        
        # Get SYSINFO
        self._logger.info("Verifier", "Querying SYSINFO...")
        sysinfo = self._provisioner.get_system_info()
        if not sysinfo:
            result.message = "Failed to get SYSINFO from device"
            self._logger.error("Verifier", result.message)
            return result
        
        result.sysinfo = sysinfo
        self._logger.debug("Verifier", f"SYSINFO: {sysinfo}")
        
        # Get NETINFO
        self._logger.info("Verifier", "Querying NETINFO...")
        netinfo = self._provisioner.get_network_info()
        if netinfo:
            result.netinfo = netinfo
            self._logger.debug("Verifier", f"NETINFO: {netinfo}")
        else:
            self._logger.warning("Verifier", "NETINFO not available")
        
        # Run verification checks
        self._verify_serial_number(result, serial_number, sysinfo)
        self._verify_region(result, region, sysinfo)
        self._verify_firmware(result, firmware_version, sysinfo)
        self._verify_hardware(result, hardware_version, sysinfo)
        
        # Determine overall status
        if result.failed_count == 0:
            result.status = VerificationStatus.PASSED
            result.message = f"All {result.passed_count} checks passed"
            self._logger.success("Verifier", result.message)
        elif result.passed_count > 0:
            result.status = VerificationStatus.PARTIAL
            result.message = (
                f"{result.passed_count} passed, {result.failed_count} failed"
            )
            self._logger.warning("Verifier", result.message)
        else:
            result.status = VerificationStatus.FAILED
            result.message = f"All {result.failed_count} checks failed"
            self._logger.error("Verifier", result.message)
        
        return result
    
    def _verify_serial_number(
        self,
        result: VerificationResult,
        expected: str,
        sysinfo: Dict[str, str]
    ) -> None:
        """Verify serial number matches."""
        # Try different possible key names
        actual = (
            sysinfo.get('serial_number') or
            sysinfo.get('device_serial') or
            sysinfo.get('sn') or
            sysinfo.get('serial') or
            ""
        )
        
        passed = result.add_check(
            name="Serial Number",
            expected=expected,
            actual=actual,
            message="" if actual else "Serial number not found in SYSINFO"
        )
        
        if passed:
            self._logger.info("Verifier", f"✓ Serial number verified: {actual}")
        else:
            self._logger.error(
                "Verifier",
                f"✗ Serial number mismatch: expected '{expected}', got '{actual}'"
            )
    
    def _verify_region(
        self,
        result: VerificationResult,
        expected: str,
        sysinfo: Dict[str, str]
    ) -> None:
        """Verify region code matches."""
        actual = (
            sysinfo.get('region') or
            sysinfo.get('region_code') or
            ""
        )
        
        passed = result.add_check(
            name="Region",
            expected=expected,
            actual=actual,
            message="" if actual else "Region not found in SYSINFO"
        )
        
        if passed:
            self._logger.info("Verifier", f"✓ Region verified: {actual}")
        else:
            self._logger.error(
                "Verifier",
                f"✗ Region mismatch: expected '{expected}', got '{actual}'"
            )
    
    def _verify_firmware(
        self,
        result: VerificationResult,
        expected: str,
        sysinfo: Dict[str, str]
    ) -> None:
        """Verify firmware version matches."""
        actual = (
            sysinfo.get('firmware_version') or
            sysinfo.get('fw_version') or
            sysinfo.get('firmware') or
            sysinfo.get('version') or
            ""
        )
        
        passed = result.add_check(
            name="Firmware Version",
            expected=expected,
            actual=actual,
            message="" if actual else "Firmware version not found in SYSINFO"
        )
        
        if passed:
            self._logger.info("Verifier", f"✓ Firmware version verified: {actual}")
        else:
            self._logger.error(
                "Verifier",
                f"✗ Firmware mismatch: expected '{expected}', got '{actual}'"
            )
    
    def _verify_hardware(
        self,
        result: VerificationResult,
        expected: str,
        sysinfo: Dict[str, str]
    ) -> None:
        """Verify hardware version matches."""
        actual = (
            sysinfo.get('hardware_version') or
            sysinfo.get('hw_version') or
            sysinfo.get('hardware') or
            ""
        )
        
        passed = result.add_check(
            name="Hardware Version",
            expected=expected,
            actual=actual,
            message="" if actual else "Hardware version not found in SYSINFO"
        )
        
        if passed:
            self._logger.info("Verifier", f"✓ Hardware version verified: {actual}")
        else:
            self._logger.error(
                "Verifier",
                f"✗ Hardware mismatch: expected '{expected}', got '{actual}'"
            )
    
    def quick_check(self, serial_number: str) -> bool:
        """
        Quick verification that device has correct serial number.
        
        Args:
            serial_number: Expected serial number
        
        Returns:
            True if serial matches
        """
        sysinfo = self._provisioner.get_system_info()
        if not sysinfo:
            return False
        
        actual = (
            sysinfo.get('serial_number') or
            sysinfo.get('sn') or
            sysinfo.get('serial') or
            ""
        )
        
        return actual.strip().lower() == serial_number.strip().lower()

class ChecksView:
    """Compatibility wrapper that behaves like both a list and a dict view."""
    def __init__(self, checks: List[VerificationCheck]):
        self._checks = checks
        self._map = {c.name: c.passed for c in checks}
    def __iter__(self):
        return iter(self._checks)
    def items(self):
        return self._map.items()
    def keys(self):
        return self._map.keys()
    def values(self):
        return self._map.values()


class DeviceVerifier:
    """Compatibility verifier exposing the older API used by GUI."""
    def __init__(self, logger=None):
        self._logger = logger if logger is not None else get_logger()
    
    def verify(
        self,
        port: str,
        expected_serial: str,
        expected_region: str,
        expected_firmware: str,
        expected_hardware: str
    ) -> VerificationResult:
        prov = SerialProvisioner(self._logger)
        if not prov.connect(port):
            return VerificationResult(status=VerificationStatus.ERROR, message="Unable to open serial port")
        # The main workflow already ensures SYSTEM READY after reboot; avoid redundant waits here.
        # Proceed directly to queries to keep verification fast and avoid consuming the banner twice.
        v = Verifier(prov)
        result = v.verify(
            serial_number=expected_serial,
            region=expected_region,
            firmware_version=expected_firmware,
            hardware_version=expected_hardware
        )
        # Provide a dict-like view for checks while keeping list iteration
        result.checks = ChecksView(result.checks)  # type: ignore[assignment]
        prov.disconnect()
        return result