"""
Report and artefact generation module.

Generates process reports, archives logs, and manages artefact directories.
"""
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from config.settings import CONFIG
from utils.logger import get_logger, LogEntry
from core.verification import VerificationResult


@dataclass
class StepResult:
    """Compatibility: single workflow step result."""
    name: str
    success: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingReport:
    """Complete processing report for a device."""
    serial_number: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Device info
    firmware_version: str = ""
    hardware_version: str = ""
    region_code: str = ""
    batch_id: str = ""
    
    # Status
    success: bool = False
    error_message: str = ""
    
    # Step results
    firmware_upload_success: bool = False
    firmware_upload_time: float = 0.0
    
    provisioning_success: bool = False
    provisioning_time: float = 0.0
    
    verification_success: bool = False
    verification_result: Optional[VerificationResult] = None
    
    label_generated: bool = False
    label_printed: bool = False
    label_path: str = ""
    
    # Timing
    total_time: float = 0.0
    end_time: Optional[datetime] = None
    
    # Notes
    notes: str = ""
    operator_notes: str = ""
    
    # Compatibility fields
    overall_success: bool = False
    steps: List[StepResult] = field(default_factory=list)

    # Compatibility helper
    def add_step(self, step: StepResult) -> None:
        self.steps.append(step)


class ReportGenerator:
    """
    Generates reports and manages artefact directories.
    
    Creates structured artefact folders with logs, reports, and labels.
    """
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """
        Initialize report generator.
        
        Args:
            base_dir: Base artefacts directory
        """
        # Allow older call style ReportGenerator(logger)
        if base_dir is not None and not isinstance(base_dir, (str, Path)):
            # Treat as logger instance
            self._logger = base_dir  # type: ignore[assignment]
            self._base_dir = Path(CONFIG.ARTEFACTS_BASE)
        else:
            self._logger = get_logger()
            self._base_dir = Path(base_dir) if base_dir else Path(CONFIG.ARTEFACTS_BASE)
    
    @property
    def base_dir(self) -> Path:
        """Get base artefacts directory."""
        return self._base_dir
    
    @base_dir.setter
    def base_dir(self, path: str) -> None:
        """Set base artefacts directory."""
        self._base_dir = Path(path)
    
    def get_device_dir(self, serial_number: str) -> Path:
        """Get artefact directory for specific device."""
        return self._base_dir / serial_number
    
    def create_device_directory(self, serial_number: str) -> Path:
        """
        Create artefact directory structure for device.
        
        Args:
            serial_number: Device serial number
        
        Returns:
            Path to device directory
        """
        device_dir = self.get_device_dir(serial_number)
        
        # Create subdirectories
        subdirs = [
            "logs",
            "reports",
            "labels",
            "calibration",      # Placeholder for sensor calibration
            "measurements",     # Placeholder for measurement calibration
            "tests"            # Placeholder for UTFW tests
        ]
        
        for subdir in subdirs:
            (device_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        self._logger.info(
            "ReportGenerator",
            f"Created artefact directory: {device_dir}"
        )
        return device_dir
    
    def generate_report(
        self,
        report: ProcessingReport,
        log_entries: List[LogEntry]
    ) -> Dict[str, Path]:
        """
        Generate all report files for a processing session.
        
        Args:
            report: ProcessingReport with session data
            log_entries: List of log entries
        
        Returns:
            Dict of generated file paths
        """
        device_dir = self.create_device_directory(report.serial_number)
        timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
        
        generated_files = {}
        
        # Generate Markdown report
        md_path = device_dir / "reports" / f"report_{timestamp}.md"
        self._generate_markdown_report(report, md_path)
        generated_files['markdown'] = md_path
        
        # Generate HTML report
        html_path = device_dir / "reports" / f"report_{timestamp}.html"
        self._generate_html_report(report, html_path)
        generated_files['html'] = html_path
        
        # Save log entries
        log_path = device_dir / "logs" / f"session_{timestamp}.log"
        self._save_log_entries(log_entries, log_path)
        generated_files['log'] = log_path
        
        # Generate summary JSON
        summary_path = device_dir / f"summary_{timestamp}.json"
        self._generate_summary(report, summary_path)
        generated_files['summary'] = summary_path
        
        self._logger.info(
            "ReportGenerator",
            f"Generated {len(generated_files)} artefact files"
        )
        return generated_files

    # Compatibility wrapper expected by GUI
    def generate(
        self,
        report: ProcessingReport,
        label_path: Optional[Union[str, Path]] = None,
        serial_log_path: Optional[Union[str, Path]] = None
    ) -> Path:
        """Generate artefacts and return device directory path (compat)."""
        device_dir = self.create_device_directory(report.serial_number)
        if label_path:
            report.label_path = str(label_path)

        # Use current logger entries if available
        entries = get_logger().get_entries()
        timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")

        # Generate files similar to generate_report
        md_path = device_dir / "reports" / f"report_{timestamp}.md"
        self._generate_markdown_report(report, md_path)

        html_path = device_dir / "reports" / f"report_{timestamp}.html"
        self._generate_html_report(report, html_path)

        # Save session log (GUI log)
        log_path = device_dir / "logs" / f"session_{timestamp}.log"
        self._save_log_entries(entries, log_path)

        # Copy label PNG into artefacts/labels if provided
        if label_path:
            try:
                lp = Path(label_path)
                copied_label = self.copy_label_to_artefacts(report.serial_number, lp)
                if copied_label:
                    self._logger.info("ReportGenerator", f"Label archived: {copied_label}")
            except Exception:
                pass

        # Copy serial log file if provided
        if serial_log_path:
            try:
                slp = Path(serial_log_path)
                copied_serial = self.copy_serial_log(report.serial_number, slp)
                if copied_serial:
                    self._logger.info("ReportGenerator", f"Serial log archived: {copied_serial}")
            except Exception:
                pass

        summary_path = device_dir / f"summary_{timestamp}.json"
        self._generate_summary(report, summary_path)

        self._logger.info(
            "ReportGenerator",
            f"Generated artefacts at: {device_dir}"
        )
        return device_dir
    
    def _generate_markdown_report(
        self,
        report: ProcessingReport,
        path: Path
    ) -> None:
        """Generate Markdown format report."""
        status_emoji = "✅" if report.success else "❌"
        
        content = f"""# ENERGIS PDU Processing Report

## Device Information

| Field | Value |
|-------|-------|
| Serial Number | {report.serial_number} |
| Firmware Version | {report.firmware_version} |
| Hardware Version | {report.hardware_version} |
| Region Code | {report.region_code} |
| Batch ID | {report.batch_id} |

## Processing Summary

- **Status**: {status_emoji} {'SUCCESS' if report.success else 'FAILED'}
- **Timestamp**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **Total Time**: {report.total_time:.2f} seconds

## Step Results

### Firmware Upload
- Status: {'✅ Success' if report.firmware_upload_success else '❌ Failed'}
- Time: {report.firmware_upload_time:.2f} seconds

### Provisioning
- Status: {'✅ Success' if report.provisioning_success else '❌ Failed'}
- Time: {report.provisioning_time:.2f} seconds

### Verification
- Status: {'✅ Passed' if report.verification_success else '❌ Failed'}
"""
        
        # Add verification details
        if report.verification_result:
            content += "\n#### Verification Checks\n\n"
            content += "| Check | Expected | Actual | Result |\n"
            content += "|-------|----------|--------|--------|\n"
            for check in report.verification_result.checks:
                result = "✅" if check.passed else "❌"
                content += f"| {check.name} | {check.expected} | {check.actual} | {result} |\n"
        
        content += f"""
### Label
- Generated: {'✅ Yes' if report.label_generated else '❌ No'}
- Printed: {'✅ Yes' if report.label_printed else '❌ No'}
"""
        
        if report.label_path:
            content += f"- Path: {report.label_path}\n"
        
        if report.error_message:
            content += f"""
## Error Details

```
{report.error_message}
```
"""
        
        if report.notes:
            content += f"""
## Notes

{report.notes}
"""
        
        content += f"""
---
*Generated by RP2040 Programmer v{CONFIG.APP_VERSION}*
"""
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    
    def _generate_html_report(
        self,
        report: ProcessingReport,
        path: Path
    ) -> None:
        """Generate HTML format report."""
        status_class = "success" if report.success else "error"
        status_text = "SUCCESS" if report.success else "FAILED"
        
        # Build verification rows
        verification_rows = ""
        if report.verification_result:
            for check in report.verification_result.checks:
                result_class = "pass" if check.passed else "fail"
                verification_rows += f"""
                <tr class="{result_class}">
                    <td>{check.name}</td>
                    <td>{check.expected}</td>
                    <td>{check.actual}</td>
                    <td>{'✓' if check.passed else '✗'}</td>
                </tr>
                """
        
        content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Processing Report - {report.serial_number}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .status {{ padding: 15px; border-radius: 4px; margin: 20px 0; font-size: 18px; font-weight: bold; }}
        .status.success {{ background: #d4edda; color: #155724; }}
        .status.error {{ background: #f8d7da; color: #721c24; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; }}
        tr.pass {{ background: #d4edda; }}
        tr.fail {{ background: #f8d7da; }}
        .step {{ display: flex; align-items: center; padding: 10px 0; }}
        .step-icon {{ font-size: 20px; margin-right: 10px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>ENERGIS PDU Processing Report</h1>
        
        <div class="status {status_class}">
            Status: {status_text}
        </div>
        
        <h2>Device Information</h2>
        <table>
            <tr><th>Serial Number</th><td>{report.serial_number}</td></tr>
            <tr><th>Firmware Version</th><td>{report.firmware_version}</td></tr>
            <tr><th>Hardware Version</th><td>{report.hardware_version}</td></tr>
            <tr><th>Region Code</th><td>{report.region_code}</td></tr>
            <tr><th>Batch ID</th><td>{report.batch_id}</td></tr>
            <tr><th>Timestamp</th><td>{report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            <tr><th>Total Time</th><td>{report.total_time:.2f} seconds</td></tr>
        </table>
        
        <h2>Processing Steps</h2>
        <div class="step">
            <span class="step-icon">{'✅' if report.firmware_upload_success else '❌'}</span>
            <span>Firmware Upload ({report.firmware_upload_time:.2f}s)</span>
        </div>
        <div class="step">
            <span class="step-icon">{'✅' if report.provisioning_success else '❌'}</span>
            <span>Provisioning ({report.provisioning_time:.2f}s)</span>
        </div>
        <div class="step">
            <span class="step-icon">{'✅' if report.verification_success else '❌'}</span>
            <span>Verification</span>
        </div>
        <div class="step">
            <span class="step-icon">{'✅' if report.label_generated else '❌'}</span>
            <span>Label Generated</span>
        </div>
        <div class="step">
            <span class="step-icon">{'✅' if report.label_printed else '❌'}</span>
            <span>Label Printed</span>
        </div>
        
        {'<h2>Verification Details</h2><table><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr>' + verification_rows + '</table>' if verification_rows else ''}
        
        {'<h2>Error</h2><pre style="background:#f8d7da;padding:15px;border-radius:4px;">' + report.error_message + '</pre>' if report.error_message else ''}
        
        {'<h2>Notes</h2><p>' + report.notes + '</p>' if report.notes else ''}
        
        <div class="footer">
            Generated by RP2040 Programmer v{CONFIG.APP_VERSION}
        </div>
    </div>
</body>
</html>
"""
        
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    
    def _save_log_entries(
        self,
        entries: List[LogEntry],
        path: Path
    ) -> None:
        """Save log entries to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Session Log - {datetime.now().isoformat()}\n")
            f.write("-" * 60 + "\n\n")
            
            for entry in entries:
                f.write(entry.format() + "\n")
    
    def _generate_summary(
        self,
        report: ProcessingReport,
        path: Path
    ) -> None:
        """Generate JSON summary file."""
        import json
        
        summary = {
            'serial_number': report.serial_number,
            'timestamp': report.timestamp.isoformat(),
            'success': report.success,
            'firmware_version': report.firmware_version,
            'hardware_version': report.hardware_version,
            'region_code': report.region_code,
            'batch_id': report.batch_id,
            'label': {
                'generated': report.label_generated,
                'printed': report.label_printed,
                'path': report.label_path or None
            },
            'steps': {
                'firmware_upload': report.firmware_upload_success,
                'provisioning': report.provisioning_success,
                'verification': report.verification_success,
                'label_generated': report.label_generated,
                'label_printed': report.label_printed
            },
            'timing': {
                'firmware_upload': report.firmware_upload_time,
                'provisioning': report.provisioning_time,
                'total': report.total_time
            },
            'error': report.error_message or None
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
    
    def copy_label_to_artefacts(
        self,
        serial_number: str,
        label_path: Path
    ) -> Optional[Path]:
        """
        Copy label PNG to device artefact directory.
        
        Args:
            serial_number: Device serial number
            label_path: Source label PNG path
        
        Returns:
            Destination path or None on error
        """
        if not label_path.exists():
            return None
        
        device_dir = self.get_device_dir(serial_number)
        dest_dir = device_dir / "labels"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = dest_dir / f"label_{timestamp}.png"
        
        try:
            shutil.copy2(label_path, dest_path)
            return dest_path
        except Exception as e:
            self._logger.error("ReportGenerator", f"Failed to copy label: {e}")
            return None
    
    def copy_serial_log(
        self,
        serial_number: str,
        log_path: Path
    ) -> Optional[Path]:
        """
        Copy serial communication log to device artefact directory.
        
        Args:
            serial_number: Device serial number  
            log_path: Source serial log path
        
        Returns:
            Destination path or None on error
        """
        if not log_path.exists():
            return None
        
        device_dir = self.get_device_dir(serial_number)
        dest_dir = device_dir / "logs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = dest_dir / f"serial_{timestamp}.log"
        
        try:
            shutil.copy2(log_path, dest_path)
            return dest_path
        except Exception as e:
            self._logger.error("ReportGenerator", f"Failed to copy serial log: {e}")
            return None