# Raspberry Pi Pico Production Flasher

This project provides tools to build and flash firmware to Raspberry Pi Pico boards in a production setting, with tracking of serial numbers.

## Important Note About Flashing

When flashing firmware to a Pico device:

1. The tool looks for a UF2 file in the build directory with the project name specified in the configuration.
2. If it can't find that specific file, it will look for any UF2 file in the build directory.
3. The Pico device must be in BOOTSEL mode (connected while holding the BOOTSEL button).
4. A drive letter (like I:\ or E:\) must be assigned to the Pico for flashing to work.
5. If the drive isn't detected, make sure the Pico is properly in BOOTSEL mode and has a drive letter assigned.

## Project Structure

The project is organized into several modules:

```
FlashApp/
├── core/                 # Core modules
│   ├── __init__.py       # Package initialization
│   ├── build_tools.py    # Build system tools (CMake/Ninja)
│   ├── pico_device.py    # Pico detection and communication
│   ├── serial_manager.py # Serial number management
│   ├── uf2_tools.py      # UF2 file manipulation
│   └── utilities.py      # Utility functions
├── Templates/            # Template files
│   └── serial_number.h.template # Template for serial number header
├── RP_flasher.py         # Main entry point
├── RP_flasher_new.py     # Refactored implementation
├── alt_config_example.py # Alternative configuration example
├── flasher_config.py     # Configuration
├── serial_number.h       # Generated header with serial number
└── serial_numbers.csv    # Database of serial numbers
```

## Setup and Usage

1. Install dependencies:
   - Python 3.6 or newer
   - For Windows users: `pip install pywin32`

2. Configure your environment:
   - Edit `flasher_config.py` to set paths to your toolchain
   - Make sure the Pico SDK is installed

3. Basic usage:
   ```bash
   # Configure and build
   python RP_flasher.py --project-dir /path/to/project
   
   # Production programming with serial numbers
   python RP_flasher.py --production serial_numbers.csv
   ```

4. Advanced options:
   ```bash
   # List all available devices in the database
   python RP_flasher.py --production serial_numbers.csv --list-devices
   
   # Flash a specific UF2 file
   python RP_flasher.py --flash path/to/firmware.uf2
   
   # Force flashing even if a device appears to be programmed
   python RP_flasher.py --production serial_numbers.csv --force
   ```

For more detailed information, see the [USER_GUIDE.md](../USER_GUIDE.md) file.

## License

This project is licensed under the AGPL License - see the [LICENSE-AGPL](../LICENSE-AGPL) file for details.