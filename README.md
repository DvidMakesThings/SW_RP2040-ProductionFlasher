# RP2040 Programmer

A Python-based factory programming tool for RP2040-based ENERGIS PDU devices.

## Features

- **Device Detection**: Automatic detection of RP2040 devices in BOOTSEL mode
- **Firmware Upload**: Upload ELF/HEX/UF2 firmware via picotool
- **Serial Provisioning**: Configure device serial number and region via UART
- **Verification**: Verify device configuration after programming
- **Label Generation**: Generate product labels from SVG templates
- **Label Printing**: Print to PM-241-BT USB label printer
- **Artefact Management**: Generate reports and archive all production data
- **CSV Management**: Track production progress with CSV-based workflow

## Requirements

### System Requirements
- Python 3.8 or higher
- Windows 10/11 or Linux (Ubuntu 20.04+)
- picotool installed and accessible

### Python Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `pyserial` - Serial communication
- `psutil` - System/process utilities
- `watchdog` - File system monitoring

Optional packages (for full functionality):
- `svglib` - SVG rendering
- `reportlab` - PDF/image generation
- `Pillow` - Image processing

## Installation

1. Clone or extract the repository:
```bash
cd energis_factory_programmer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Ensure picotool is installed:
   - **Windows**: Place `picotool.exe` in PATH or specify path in GUI
   - **Linux**: Install via package manager or build from source
     ```bash
     sudo apt install picotool
     # or build from https://github.com/raspberrypi/picotool
     ```

4. Configure label templates:
   - Place SVG templates in `assets/templates/`
   - Templates should contain `SERIAL_NUMBER` placeholder

## Usage

### Starting the Application
```bash
python main.py
```

### Programming Workflow

1. **Load CSV**: Open a production CSV file with serial numbers
2. **Select Firmware**: Choose the firmware file (.elf, .hex, or .uf2)
3. **Configure Settings**: Set firmware version, hardware version, region, etc.
4. **Connect Device**: Put RP2040 in BOOTSEL mode (hold BOOTSEL, plug USB)
5. **Start Programming**: Click "Start" to begin the automated workflow

### CSV Format

The production CSV must have these columns:
```csv
serial_number,date_programmed,firmware_version,hardware_version,region_code,batch_id,notes
```

- `serial_number`: Unique device identifier (required)
- `date_programmed`: Filled automatically after successful programming
- `firmware_version`: Recorded firmware version
- `hardware_version`: Recorded hardware version
- `region_code`: EU or US
- `batch_id`: Production batch identifier
- `notes`: Additional notes

### Programming Sequence

1. **Firmware Upload**: Uses picotool to flash firmware
2. **Wait for Serial**: Detects serial port after device boots
3. **Provisioning**:
   - Sends unlock command
   - Sets serial number
   - Sets region code
   - Verifies with status command
   - Reboots device
4. **Verification**: Queries SYSINFO/NETINFO to verify settings
5. **Label Generation**: Creates label PNG from SVG template
6. **Report Generation**: Creates markdown/HTML report
7. **CSV Update**: Marks row as programmed with timestamp

## Configuration

Edit `config/settings.py` to customize:

```python
# Device detection
RP2040_VID = 0x2E8A
RP2040_PID = 0x0003

# Serial communication
SERIAL_BAUDRATE = 115200
SERIAL_TIMEOUT = 1.0

# Label settings
LABEL_WIDTH_MM = 75
LABEL_HEIGHT_MM = 50
LABEL_DPI = 300

# Printer
LABEL_PRINTER_NAME = "PM-241-BT"
```

## Project Structure

```
energis_factory_programmer/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── config/
│   ├── __init__.py
│   └── settings.py        # Global configuration
│
├── core/
│   ├── __init__.py
│   ├── device_detector.py # USB device detection
│   ├── firmware_uploader.py # picotool wrapper
│   ├── serial_provisioner.py # UART provisioning
│   ├── csv_manager.py     # CSV file management
│   └── verification.py    # Post-programming verification
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py     # Main application window
│   ├── device_panel.py    # Device list panel
│   ├── csv_panel.py       # CSV management panel
│   ├── provisioning_panel.py # Settings panel
│   └── log_panel.py       # Activity log panel
│
├── label/
│   ├── __init__.py
│   └── label_generator.py # SVG→PNG label generation
│
├── artefacts/
│   ├── __init__.py
│   └── report_generator.py # Report/archive generation
│
├── utils/
│   ├── __init__.py
│   ├── logger.py          # Logging utilities
│   └── persistence.py     # State persistence
│
└── assets/
    ├── templates/
    │   ├── ENERGIS_rating_label_EU.svg
    │   └── ENERGIS_rating_label_US.svg
    └── sample_production.csv
```

## Artefact Output

For each programmed device, artefacts are saved to:
```
docs/Compliance_Documents/Artefacts/<SERIAL_NUMBER>/
├── logs/
│   ├── session_YYYYMMDD_HHMMSS.log
│   └── serial_YYYYMMDD_HHMMSS.log
├── reports/
│   ├── report_YYYYMMDD_HHMMSS.md
│   └── report_YYYYMMDD_HHMMSS.html
├── labels/
│   └── label_<serial>.png
├── calibration/      # Placeholder for future use
├── measurements/     # Placeholder for future use
└── tests/           # Placeholder for future use
```

## Extending the Tool

### Adding Calibration Support

1. Create `core/calibration.py` with calibration routines
2. Add calibration panel to GUI
3. Integrate into workflow in `main_window.py`
4. Save calibration data to artefacts `calibration/` directory

### Adding Automated Tests

1. Create `core/test_runner.py` for UTFW test integration
2. Add test configuration panel
3. Integrate into workflow
4. Save test results to artefacts `tests/` directory

## Troubleshooting

### Device Not Detected
- Ensure device is in BOOTSEL mode (LED should indicate)
- Check USB cable and connection
- Verify RP2040 VID/PID match settings
- Try refreshing devices (Tools → Refresh Devices)

### Firmware Upload Fails
- Verify picotool is installed and in PATH
- Check firmware file is valid ELF/HEX/UF2
- Ensure device is in BOOTSEL mode
- Check picotool output in log panel

### Serial Port Issues
- Verify device has correct firmware with serial support
- Check baud rate matches device configuration
- On Linux, ensure user has permission to access serial ports:
  ```bash
  sudo usermod -a -G dialout $USER
  ```

### Label Printing Issues
- Verify printer is installed as system printer
- Check printer name matches settings
- Ensure svglib and reportlab are installed

## License

Proprietary - ENERGIS Systems

## Support

For issues and support, contact the factory engineering team.