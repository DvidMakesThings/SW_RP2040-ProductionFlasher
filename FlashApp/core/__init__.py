#!/usr/bin/env python3
"""
Module initialization file for the core package.
"""

__version__ = '1.0.0'

# Export the main components for easier imports
try:
    from FlashApp.core.utilities import load_config, find_project_dir, run_command, get_path
    from FlashApp.core.build_tools import BuildManager
    from FlashApp.core.pico_device import find_pico_drive, read_device_id, is_device_programmed, flash_uf2
    from FlashApp.core.serial_manager import SerialManager
    from FlashApp.core.uf2_tools import modify_uf2_with_serial
except ImportError:
    # Fall back to relative imports
    try:
        from .utilities import load_config, find_project_dir, run_command, get_path
        from .build_tools import BuildManager
        from .pico_device import find_pico_drive, read_device_id, is_device_programmed, flash_uf2
        from .serial_manager import SerialManager
        from .uf2_tools import modify_uf2_with_serial
    except ImportError as e:
        print(f"Warning: Could not import core modules: {e}")
        print("Some functionality may not be available")