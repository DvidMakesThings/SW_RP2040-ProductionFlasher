"""
CSV management module for factory artefact tracking.

Handles loading, saving, and managing the provisioning CSV database.
"""
import csv
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import CONFIG
from utils.logger import get_logger


@dataclass
class CSVRow:
    """Represents a single row in the provisioning CSV."""
    serial_number: str
    date_programmed: str = ""
    firmware_version: str = ""
    hardware_version: str = ""
    region_code: str = ""
    batch_id: str = ""
    notes: str = ""
    # Dynamic reprogramming columns stored as dict
    extra_columns: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_programmed(self) -> bool:
        """Check if this row has been programmed."""
        return bool(self.date_programmed.strip())
    
    @property
    def reprogram_count(self) -> int:
        """Count number of reprogramming events."""
        return sum(
            1 for k in self.extra_columns.keys()
            if k.startswith(CONFIG.CSV_REPROGRAM_PREFIX)
        )
    
    def to_dict(self, all_columns: List[str]) -> Dict[str, str]:
        """Convert to dict for CSV writing."""
        result = {
            'serial_number': self.serial_number,
            'date_programmed': self.date_programmed,
            'firmware_version': self.firmware_version,
            'hardware_version': self.hardware_version,
            'region_code': self.region_code,
            'batch_id': self.batch_id,
            'notes': self.notes
        }
        # Add extra columns
        for col in all_columns:
            if col not in result:
                result[col] = self.extra_columns.get(col, "")
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'CSVRow':
        """Create CSVRow from dict."""
        base_cols = CONFIG.CSV_COLUMNS
        extra = {k: v for k, v in data.items() if k not in base_cols}
        
        return cls(
            serial_number=data.get('serial_number', ''),
            date_programmed=data.get('date_programmed', ''),
            firmware_version=data.get('firmware_version', ''),
            hardware_version=data.get('hardware_version', ''),
            region_code=data.get('region_code', ''),
            batch_id=data.get('batch_id', ''),
            notes=data.get('notes', ''),
            extra_columns=extra
        )


class CSVManager:
    """
    Manages the factory provisioning CSV file.
    
    Handles row selection, updates, and reprogramming tracking.
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._path: Optional[Path] = None
        self._rows: List[CSVRow] = []
        self._all_columns: List[str] = CONFIG.CSV_COLUMNS.copy()
        self._selected_index: Optional[int] = None
        self._modified = False
    
    @property
    def is_loaded(self) -> bool:
        """Check if CSV is loaded."""
        return self._path is not None
    
    @property
    def path(self) -> Optional[Path]:
        """Get current CSV file path."""
        return self._path
    
    @property
    def rows(self) -> List[CSVRow]:
        """Get all rows."""
        return self._rows.copy()
    
    @property
    def row_count(self) -> int:
        """Get total row count."""
        return len(self._rows)
    
    @property
    def selected_row(self) -> Optional[CSVRow]:
        """Get currently selected row."""
        if self._selected_index is not None and 0 <= self._selected_index < len(self._rows):
            return self._rows[self._selected_index]
        return None
    
    @property
    def selected_index(self) -> Optional[int]:
        """Get selected row index."""
        return self._selected_index
    
    @property
    def is_modified(self) -> bool:
        """Check if CSV has unsaved changes."""
        return self._modified
    
    def load(self, path: str) -> bool:
        """
        Load CSV file.
        
        Args:
            path: Path to CSV file
        
        Returns:
            True if loaded successfully
        """
        file_path = Path(path)
        
        if not file_path.exists():
            self._logger.error("CSVManager", f"File not found: {path}")
            return False
        
        try:
            self._rows.clear()
            self._all_columns = CONFIG.CSV_COLUMNS.copy()
            
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if reader.fieldnames:
                    # Capture all columns including extras
                    for col in reader.fieldnames:
                        if col not in self._all_columns:
                            self._all_columns.append(col)
                
                for row_data in reader:
                    self._rows.append(CSVRow.from_dict(row_data))
            
            self._path = file_path
            self._modified = False
            self._selected_index = None
            
            self._logger.info(
                "CSVManager",
                f"Loaded {len(self._rows)} rows from {file_path.name}"
            )
            
            # Auto-select next unprogrammed row
            self.select_next_unprogrammed()
            
            return True
        
        except Exception as e:
            self._logger.error("CSVManager", f"Failed to load CSV: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save CSV file (overwrites original).
        
        Returns:
            True if saved successfully
        """
        if not self._path:
            self._logger.error("CSVManager", "No file loaded")
            return False
        
        return self._write_csv(self._path)
    
    def save_as(self, path: str) -> bool:
        """
        Save CSV to new location.
        
        Args:
            path: New file path
        
        Returns:
            True if saved successfully
        """
        new_path = Path(path)
        if self._write_csv(new_path):
            self._path = new_path
            return True
        return False
    
    def create_backup(self) -> Optional[Path]:
        """
        Create timestamped backup of current CSV.
        
        Returns:
            Backup file path or None on failure
        """
        if not self._path or not self._path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self._path.stem}_backup_{timestamp}{self._path.suffix}"
        backup_path = self._path.parent / backup_name
        
        try:
            shutil.copy2(self._path, backup_path)
            self._logger.info("CSVManager", f"Created backup: {backup_name}")
            return backup_path
        except Exception as e:
            self._logger.error("CSVManager", f"Backup failed: {e}")
            return None
    
    def _write_csv(self, path: Path) -> bool:
        """Write CSV to file."""
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self._all_columns)
                writer.writeheader()
                for row in self._rows:
                    writer.writerow(row.to_dict(self._all_columns))
            
            self._modified = False
            self._logger.info("CSVManager", f"Saved to {path.name}")
            return True
        
        except Exception as e:
            self._logger.error("CSVManager", f"Failed to save CSV: {e}")
            return False
    
    def select_row(self, index: int) -> bool:
        """
        Select a row by index.
        
        Args:
            index: Row index (0-based)
        
        Returns:
            True if selection successful
        """
        if 0 <= index < len(self._rows):
            # Avoid redundant selection churn
            if self._selected_index == index:
                return True
            self._selected_index = index
            row = self._rows[index]
            self._logger.info(
                "CSVManager",
                f"Selected row {index}: SN={row.serial_number}"
            )
            return True
        return False
    
    def select_next_unprogrammed(self) -> bool:
        """
        Select next row where date_programmed is empty.
        
        Returns:
            True if found and selected
        """
        for i, row in enumerate(self._rows):
            if not row.is_programmed:
                return self.select_row(i)
        
        self._logger.warning("CSVManager", "No unprogrammed rows available")
        return False
    
    def select_by_serial(self, serial_number: str) -> bool:
        """
        Select row by serial number.
        
        Args:
            serial_number: Serial number to find
        
        Returns:
            True if found and selected
        """
        for i, row in enumerate(self._rows):
            if row.serial_number == serial_number:
                return self.select_row(i)
        return False
    
    def update_selected_row(
        self,
        firmware_version: str,
        hardware_version: str,
        region_code: str,
        batch_id: str,
        notes: str,
        mark_programmed: bool = True
    ) -> bool:
        """
        Update the currently selected row.
        
        Args:
            firmware_version: Firmware version string
            hardware_version: Hardware version string
            region_code: Region code (EU/US)
            batch_id: Batch identifier
            notes: Additional notes
            mark_programmed: Set date_programmed to now
        
        Returns:
            True if updated successfully
        """
        if self._selected_index is None:
            self._logger.error("CSVManager", "No row selected")
            return False
        
        row = self._rows[self._selected_index]
        
        # Check if this is a reprogramming event
        if row.is_programmed:
            self._handle_reprogram(row)
        
        # Update fields
        row.firmware_version = firmware_version
        row.hardware_version = hardware_version
        row.region_code = region_code
        row.batch_id = batch_id
        row.notes = notes
        
        if mark_programmed:
            row.date_programmed = datetime.now().strftime(CONFIG.DATE_FORMAT)
        
        self._modified = True
        self._logger.info(
            "CSVManager",
            f"Updated row: SN={row.serial_number}"
        )
        return True
    
    def _handle_reprogram(self, row: CSVRow) -> None:
        """Add reprogramming tracking columns."""
        count = row.reprogram_count + 1
        prefix = CONFIG.CSV_REPROGRAM_PREFIX
        
        # Add new columns if needed
        date_col = f"{prefix}{count}_date"
        fw_col = f"{prefix}{count}_firmware"
        reason_col = f"{prefix}{count}_reason"
        
        for col in [date_col, fw_col, reason_col]:
            if col not in self._all_columns:
                self._all_columns.append(col)
        
        # Save previous values
        row.extra_columns[date_col] = row.date_programmed
        row.extra_columns[fw_col] = row.firmware_version
        row.extra_columns[reason_col] = f"Reprogrammed ({count})"
        
        self._logger.info(
            "CSVManager",
            f"Recording reprogram event #{count} for SN={row.serial_number}"
        )
    
    def get_unprogrammed_rows(self) -> List[CSVRow]:
        """Get all rows that haven't been programmed."""
        return [r for r in self._rows if not r.is_programmed]
    
    def get_programmed_rows(self) -> List[CSVRow]:
        """Get all rows that have been programmed."""
        return [r for r in self._rows if r.is_programmed]
    
    def get_statistics(self) -> Dict[str, int]:
        """Get CSV statistics."""
        total = len(self._rows)
        programmed = len(self.get_programmed_rows())
        return {
            'total': total,
            'programmed': programmed,
            'remaining': total - programmed,
            'progress_percent': int((programmed / total * 100) if total > 0 else 0)
        }

    # Compatibility helper expected by GUI workflow
    def mark_programmed(self, serial_number: str, firmware_version: str, notes: str = "") -> bool:
        """Mark the given serial number as programmed and update basic fields.

        Updates `date_programmed` to now, sets `firmware_version`, and updates `notes`.
        Keeps existing `hardware_version`, `region_code`, and `batch_id` values.
        Returns True on success, False if the row is not found or update fails.
        """
        # Find the row by serial
        for i, row in enumerate(self._rows):
            if row.serial_number == serial_number:
                self._selected_index = i
                return self.update_selected_row(
                    firmware_version=firmware_version,
                    hardware_version=row.hardware_version,
                    region_code=row.region_code,
                    batch_id=row.batch_id,
                    notes=notes,
                    mark_programmed=True
                )
        self._logger.warning("CSVManager", f"Serial not found in CSV: {serial_number}")
        return False