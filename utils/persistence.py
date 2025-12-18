"""
Persistence manager for RP2040 Programmer.

Saves and restores application state including last-used values.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict, field

from config.settings import CONFIG


@dataclass
class PersistedState:
    """State persisted across application runs."""
    # Last used paths
    last_csv_path: str = ""
    last_firmware_path: str = ""
    last_picotool_path: str = ""
    last_label_template_path: str = ""
    
    # Last used provisioning values
    last_firmware_version: str = ""
    last_hardware_version: str = ""
    last_region_code: str = "EU"
    last_batch_id: str = ""
    last_notes: str = ""
    
    # Window state
    window_width: int = CONFIG.WINDOW_MIN_WIDTH
    window_height: int = CONFIG.WINDOW_MIN_HEIGHT
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    
    # Recent files
    recent_csv_files: list = field(default_factory=list)
    recent_firmware_files: list = field(default_factory=list)


class PersistenceManager:
    """
    Manages persistent state across application sessions.
    
    Uses JSON file storage for simplicity and human readability.
    """
    
    MAX_RECENT_FILES = 10
    
    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize persistence manager.
        
        Args:
            state_file: Path to state file. Defaults to user config directory.
        """
        if state_file:
            self._state_file = Path(state_file)
        else:
            # Resolve persistence path robustly:
            # - If CONFIG.PERSISTENCE_FILE is absolute, use it as-is
            # - If relative, place it under the app config dir alongside logs
            cfg_path = Path(str(CONFIG.PERSISTENCE_FILE))
            if cfg_path.is_absolute():
                self._state_file = cfg_path
            else:
                # Prefer the directory that contains logs, falling back to home
                try:
                    log_path = Path(str(CONFIG.LOG_FILE_PATH))
                    base_dir = log_path.parent.parent if log_path.is_absolute() else Path.home()
                except Exception:
                    base_dir = Path.home()
                self._state_file = base_dir / cfg_path.name
        
        self._state = PersistedState()
        self._load()
    
    def _load(self) -> None:
        """Load state from file."""
        if not self._state_file.exists():
            return
        
        try:
            with open(self._state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Update state with loaded values
            for key, value in data.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
        except (json.JSONDecodeError, IOError) as e:
            # Log error but continue with defaults
            print(f"Warning: Could not load state file: {e}")
    
    def _save(self) -> None:
        """Save state to file."""
        try:
            # Ensure directory exists
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(self._state), f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save state file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a persisted value."""
        return getattr(self._state, key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set and persist a value."""
        if hasattr(self._state, key):
            setattr(self._state, key, value)
            self._save()
    
    def add_recent_csv(self, path: str) -> None:
        """Add a CSV file to recent list."""
        recent = self._state.recent_csv_files
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._state.recent_csv_files = recent[:self.MAX_RECENT_FILES]
        self._save()
    
    def add_recent_firmware(self, path: str) -> None:
        """Add a firmware file to recent list."""
        recent = self._state.recent_firmware_files
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._state.recent_firmware_files = recent[:self.MAX_RECENT_FILES]
        self._save()
    
    def get_recent_csv_files(self) -> list:
        """Get list of recent CSV files."""
        return self._state.recent_csv_files.copy()
    
    def get_recent_firmware_files(self) -> list:
        """Get list of recent firmware files."""
        return self._state.recent_firmware_files.copy()
    
    def save_provisioning_values(
        self,
        firmware_version: str,
        hardware_version: str,
        region_code: str,
        batch_id: str,
        notes: str
    ) -> None:
        """Save all provisioning values at once."""
        self._state.last_firmware_version = firmware_version
        self._state.last_hardware_version = hardware_version
        self._state.last_region_code = region_code
        self._state.last_batch_id = batch_id
        self._state.last_notes = notes
        self._save()
    
    def get_provisioning_values(self) -> Dict[str, str]:
        """Get all last provisioning values."""
        return {
            'firmware_version': self._state.last_firmware_version,
            'hardware_version': self._state.last_hardware_version,
            'region_code': self._state.last_region_code,
            'batch_id': self._state.last_batch_id,
            'notes': self._state.last_notes
        }
    
    def save_window_geometry(
        self,
        width: int,
        height: int,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> None:
        """Save window geometry."""
        self._state.window_width = width
        self._state.window_height = height
        self._state.window_x = x
        self._state.window_y = y
        self._save()
    
    def get_window_geometry(self) -> Dict[str, Optional[int]]:
        """Get saved window geometry."""
        return {
            'width': self._state.window_width,
            'height': self._state.window_height,
            'x': self._state.window_x,
            'y': self._state.window_y
        }