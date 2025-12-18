"""
Centralized logging for RP2040 Programmer.

Provides both file and GUI-compatible logging with serial communication capture.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class LogEntry:
    """Single log entry with metadata."""
    timestamp: datetime
    level: str
    source: str
    message: str
    
    def format(self) -> str:
        """Format entry for display."""
        ts = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        return f"[{ts}] [{self.level}] [{self.source}] {self.message}"


class AppLogger:
    """
    Application logger with GUI callback support.
    
    Manages both file logging and real-time GUI updates.
    """
    
    def __init__(self, name: str = "energis"):
        self.name = name
        self.entries: List[LogEntry] = []
        self._gui_callback: Optional[Callable[[LogEntry], None]] = None
        self._file_handler: Optional[logging.FileHandler] = None
        self._serial_log_path: Optional[Path] = None
        self._serial_log_file = None
        
        # Setup standard Python logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)
        # Prevent propagation to root to avoid duplicate outputs
        self._logger.propagate = False
        
        # Add a single console handler only once per process
        if not getattr(self._logger, "_energis_console_configured", False):
            console = logging.StreamHandler(sys.stdout)
            console.setLevel(logging.INFO)
            console.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            ))
            self._logger.addHandler(console)
            setattr(self._logger, "_energis_console_configured", True)
    
    def set_gui_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """Set callback for GUI log updates."""
        self._gui_callback = callback

    # Backward-compatibility alias expected by some GUI code
    def set_callback(self, callback: Callable[[LogEntry], None]) -> None:
        self.set_gui_callback(callback)
    
    def set_file_log(self, path: Path) -> None:
        """Enable file logging to specified path."""
        if self._file_handler:
            self._logger.removeHandler(self._file_handler)
        
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handler = logging.FileHandler(path, encoding='utf-8')
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
        ))
        self._logger.addHandler(self._file_handler)
    
    def start_serial_log(self, path: Path) -> None:
        """Start logging serial communication to file."""
        self.stop_serial_log()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._serial_log_path = path
        self._serial_log_file = open(path, 'w', encoding='utf-8')
        self._serial_log_file.write(f"# Serial Log Started: {datetime.now().isoformat()}\n")
        self._serial_log_file.write("# Direction | Timestamp | Data\n")
        self._serial_log_file.write("-" * 60 + "\n")

    def get_serial_log_path(self) -> Optional[Path]:
        """Get current serial log file path, if active."""
        return self._serial_log_path
    
    def stop_serial_log(self) -> None:
        """Stop serial logging and close file."""
        if self._serial_log_file:
            self._serial_log_file.write(f"\n# Serial Log Ended: {datetime.now().isoformat()}\n")
            self._serial_log_file.close()
            self._serial_log_file = None
    
    def log_serial_tx(self, data: str) -> None:
        """Log transmitted serial data."""
        if self._serial_log_file:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._serial_log_file.write(f"TX | {ts} | {data}\n")
            self._serial_log_file.flush()
    
    def log_serial_rx(self, data: str) -> None:
        """Log received serial data."""
        if self._serial_log_file:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._serial_log_file.write(f"RX | {ts} | {data}\n")
            self._serial_log_file.flush()
    
    def _log(self, level: str, source: str, message: str) -> None:
        """Internal logging method."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            source=source,
            message=message
        )
        self.entries.append(entry)
        
        # Standard logger
        log_func = getattr(self._logger, level.lower(), self._logger.info)
        log_func(f"[{source}] {message}")
        
        # GUI callback
        if self._gui_callback:
            self._gui_callback(entry)
    
    def debug(self, message_or_source: str, message: Optional[str] = None) -> None:
        """Log debug message. Accepts (source, message) or (message)."""
        if message is None:
            self._log("DEBUG", "App", message_or_source)
        else:
            self._log("DEBUG", message_or_source, message)
    
    def info(self, message_or_source: str, message: Optional[str] = None) -> None:
        """Log info message. Accepts (source, message) or (message)."""
        if message is None:
            self._log("INFO", "App", message_or_source)
        else:
            self._log("INFO", message_or_source, message)
    
    def warning(self, message_or_source: str, message: Optional[str] = None) -> None:
        """Log warning message. Accepts (source, message) or (message)."""
        if message is None:
            self._log("WARNING", "App", message_or_source)
        else:
            self._log("WARNING", message_or_source, message)
    
    def error(self, message_or_source: str, message: Optional[str] = None) -> None:
        """Log error message. Accepts (source, message) or (message)."""
        if message is None:
            self._log("ERROR", "App", message_or_source)
        else:
            self._log("ERROR", message_or_source, message)
    
    def success(self, message_or_source: str, message: Optional[str] = None) -> None:
        """Log success message (info level with SUCCESS tag). Accepts (source, message) or (message)."""
        if message is None:
            self._log("SUCCESS", "App", message_or_source)
        else:
            self._log("SUCCESS", message_or_source, message)
    
    def get_entries(self, source: Optional[str] = None) -> List[LogEntry]:
        """Get log entries, optionally filtered by source."""
        if source:
            return [e for e in self.entries if e.source == source]
        return self.entries.copy()
    
    def clear(self) -> None:
        """Clear log entries."""
        self.entries.clear()


# Global logger instance
_logger: Optional[AppLogger] = None


def get_logger() -> AppLogger:
    """Get or create global logger instance."""
    global _logger
    if _logger is None:
        _logger = AppLogger()
    return _logger


class LogLevel(Enum):
    """Backward-compatibility enum for log levels (not strictly required)."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"