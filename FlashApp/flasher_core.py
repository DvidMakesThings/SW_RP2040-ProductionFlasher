#!/usr/bin/env python
"""
Main script for Raspberry Pi Pico production flasher

This script orchestrates the build and flashing process for Raspberry Pi Pico
firmware, including serial number management for production use.
"""

import os
import sys
import platform
import argparse
import time
import re
import glob
import serial
from serial.tools import list_ports

# Define picotool function first so it's available for use
def flash_with_picotool(elf_file, verbose=False):
    """
    Flash a file using picotool
    """
    import os
    import subprocess
    
    # Get the picotool path from environment
    user_home = os.path.expanduser("~")
    picotool_path = os.path.join(user_home, ".pico-sdk", "picotool", "2.2.0-a4", "picotool", "picotool.exe")
    
    # Check if picotool path exists, use alternative path if not
    if not os.path.exists(picotool_path):
        picotool_path = os.path.join(user_home, ".pico-sdk", "picotool", "2.1.1", "picotool", "picotool.exe")
    
    # Check again if picotool path exists
    if not os.path.exists(picotool_path):
        print("Error: picotool not found. Please install picotool.")
        return False
        
    # Set -f flag to force programming even if the device is already programmed
    # Set -x flag to restart the device after programming
    cmd = [picotool_path, "load", elf_file, "-f", "-x"]
    
    print(f"Flashing {elf_file} to Pico using picotool...")
    try:
        if verbose:
            print(f"Running: {' '.join(cmd)}")
        
        # Run picotool and capture its output
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Check if the command was successful
        if result.returncode == 0:
            print("Device successfully flashed and restarted.")
            return True
        else:
            print(f"Error flashing device: {result.stderr}")
            print("Make sure your Pico is connected in bootloader mode (hold BOOTSEL while plugging in)")
            return False
    except Exception as e:
        print(f"Error running picotool: {e}")
        return False

def find_serial_ports():
    """Find all available serial ports"""
    return list(list_ports.comports())

def wait_for_new_serial_port(timeout=10, check_interval=0.5):
    """
    Wait for a new serial port to appear
    
    Args:
        timeout: Maximum time to wait in seconds
        check_interval: How often to check for new ports in seconds
        
    Returns:
        The new port name if found, None otherwise
    """
    # Get the initial list of ports
    initial_ports = set(port.device for port in find_serial_ports())
    print(f"Initial serial ports: {', '.join(initial_ports) if initial_ports else 'None'}")
    
    # Wait for a new port to appear
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(check_interval)
        current_ports = set(port.device for port in find_serial_ports())
        new_ports = current_ports - initial_ports
        
        if new_ports:
            new_port = list(new_ports)[0]  # Take the first new port
            print(f"New serial port detected: {new_port}")
            return new_port
            
        elapsed = time.time() - start_time
        if int(elapsed) % 2 == 0 and elapsed < timeout - 0.5:  # Print every 2 seconds
            print(f"Waiting for device to appear on serial port... ({int(elapsed)}s)")
    
    print("No new serial port detected within timeout period")
    return None
    
def monitor_serial_port(port_name, target_serial=None, timeout=10):
    """
    Monitor a serial port for boot messages and verify serial number
    
    Args:
        port_name: Name of the serial port to monitor
        target_serial: Expected serial number to verify against
        timeout: Maximum time to wait in seconds (default: 10 seconds)
        
    Returns:
        A tuple of (success, detected_serial, detected_firmware) where:
        - success: Boolean indicating if the verification succeeded
          (True if target_serial is None or matches detected_serial)
        - detected_serial: The actual serial number reported by the device
        - detected_firmware: The firmware version reported by the device
    """
    try:
        # Configuration for Pico serial connection
        ser = serial.Serial(port_name, baudrate=115200, timeout=0.1)
        print(f"Connected to {port_name}, monitoring for boot messages...")
        
        start_time = time.time()
        output_buffer = []
        detected_serial = None
        detected_firmware = None
        
        while time.time() - start_time < timeout:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    output_buffer.append(line)
                    print(f"Serial: {line}")
                    
                    # Check for serial number in the output
                    serial_match = re.search(r'Device Serial\s*:\s*(SN-\d+)', line)
                    if serial_match:
                        detected_serial = serial_match.group(1)
                        print(f"Detected serial number: {detected_serial}")
                    
                    # Check for firmware version in the output
                    firmware_match = re.search(r'Firmware Ver\s*:\s*(\d+\.\d+\.\d+)', line)
                    if firmware_match:
                        detected_firmware = firmware_match.group(1)
                        print(f"Detected firmware version: {detected_firmware}")
                    
                    # If we found both serial and firmware, and they match what we expect
                    if detected_serial and detected_firmware:
                        if target_serial and detected_serial != target_serial:
                            print(f"WARNING: Detected serial {detected_serial} does not match expected {target_serial}")
                            return (False, detected_serial, detected_firmware)
                        else:
                            print(f"SUCCESS: Verified device with serial {detected_serial} and firmware {detected_firmware}")
                            return (True, detected_serial, detected_firmware)
            except serial.SerialException:
                print("Serial connection lost")
                break
            except Exception as e:
                print(f"Error reading from serial: {e}")
                break
                
            # Sleep a bit to avoid hammering the CPU
            time.sleep(0.05)
        
        print(f"Timeout waiting for device boot messages after {timeout} seconds")
        return (False, detected_serial, detected_firmware)
    except Exception as e:
        print(f"Error opening serial port {port_name}: {e}")
        return (False, None, None)
    finally:
        try:
            ser.close()
        except:
            pass

# Import core modules
try:
    from FlashApp.core.utilities import load_config, find_project_dir
    from FlashApp.core.build_tools import BuildManager
    from FlashApp.core.pico_device import (
        find_pico_drive, 
        read_device_id, 
        is_device_programmed, 
        flash_uf2,
        get_unique_board_id
    )
    from FlashApp.core.serial_manager import SerialManager
    from FlashApp.core.uf2_tools import modify_uf2_with_serial
except ImportError:
    # Try relative import if absolute import fails
    try:
        from core.utilities import load_config, find_project_dir
        from core.build_tools import BuildManager
        from core.pico_device import (
            find_pico_drive, 
            read_device_id, 
            is_device_programmed, 
            flash_uf2, 
            get_unique_board_id
        )
        from core.serial_manager import SerialManager
        from core.uf2_tools import modify_uf2_with_serial
    except ImportError as e:
        print(f"Error importing core modules: {e}")
        print("Please make sure the core modules are properly installed.")
        sys.exit(1)

# Constants
CONFIG_FILE = "flasher_config.py"
DEFAULT_CONFIG = {
    'PROJECT_NAME': "rpsetup",
    'BUILD_DIR': "build",
    'PROJECT_DIR': None,
    'HOME_DIR': os.path.expanduser("~"),
    'PICO_SDK_ROOT': os.path.expanduser("~/.pico-sdk"),
    'CMAKE_PATH': "",
    'C_COMPILER_PATH': "",
    'CXX_COMPILER_PATH': "",
    'NINJA_PATH': "",
    'PYTHON3_PATH': "python",
    'VERBOSE': False
}

def process_paths(config):
    """Process and validate tool paths in the config"""
    # Resolve relative paths
    for key in ['CMAKE_PATH', 'C_COMPILER_PATH', 'CXX_COMPILER_PATH', 'NINJA_PATH', 'PYTHON3_PATH']:
        if key in config and config[key]:
            if config[key].startswith("~"):
                config[key] = os.path.expanduser(config[key])
    
    return config

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Build and deploy tool for Raspberry Pi Pico projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 RP_flasher.py                         # Configure and build the project
  python3 RP_flasher.py --clean                 # Clean the build directory
  python3 RP_flasher.py --configure             # Only run the CMake configuration step
  python3 RP_flasher.py --build                 # Only build the project (without configuring)
  python3 RP_flasher.py --rebuild               # Clean, configure, and build
  python3 RP_flasher.py --deploy                # Deploy the firmware to a connected Pico using picotool with verification
  python3 RP_flasher.py --deploy --skip-verify  # Deploy firmware without serial verification
  python3 RP_flasher.py --clean --rebuild       # Clean, then configure and build
  python3 RP_flasher.py --all                   # Configure, build, and deploy with picotool
  python3 RP_flasher.py --config my_config.py   # Use alternative config file
  python3 RP_flasher.py --flash latest.uf2      # Flash a pre-built file using picotool
  python3 RP_flasher.py --flash latest.uf2 --force # Force flash even if device appears to be programmed
  python3 RP_flasher.py --identify-device       # Identify connected Pico's serial number
  python3 RP_flasher.py --identify-device --production serial_numbers.csv # Show full device details
  python3 RP_flasher.py --project-dir /path/to/project # Specify a different project directory
  python3 RP_flasher.py --production serial_numbers.csv # Production programming with serial numbers
  python3 RP_flasher.py --production serial_numbers.csv --skip-verify # Production programming without verification
  python3 RP_flasher.py --production serial_numbers.csv --firmware-version 1.1.0 --programmed-by "John Doe"
  python3 RP_flasher.py --production serial_numbers.csv --list-devices # List all programmed devices
  python3 RP_flasher.py --production serial_numbers.csv --next-serial # Show next available serial number
  python3 RP_flasher.py --production serial_numbers.csv --reprogram # Reprogram device with a different serial number
"""
    )
    
    # Add arguments
    parser.add_argument("--clean", action="store_true", help="Clean the build directory")
    parser.add_argument("--configure", action="store_true", help="Run the CMake configuration step")
    parser.add_argument("--build", action="store_true", help="Build the project")
    parser.add_argument("--rebuild", action="store_true", help="Clean, configure, and build")
    parser.add_argument("--deploy", action="store_true", help="Deploy the firmware to a connected Pico")
    parser.add_argument("--all", action="store_true", help="Configure, build, and deploy")
    parser.add_argument("--flash", type=str, help="Flash a pre-built file to a Pico using picotool")
    parser.add_argument("--force", action="store_true", help="Force flash even if device appears to be already programmed")
    parser.add_argument("--skip-verify", action="store_true", help="Skip serial verification step after flashing (verification is enabled by default)")
    parser.add_argument("--reprogram", action="store_true", help="Allow reprogramming a device with a different serial number than it currently has")
    parser.add_argument("--production", type=str, help="Production programming with serial numbers from CSV file")
    parser.add_argument("--serial-template", type=str, help="Template C header file with SERIAL_NUMBER macro to replace")
    parser.add_argument("--next-serial", action="store_true", help="Get the next available serial number from the CSV file")
    parser.add_argument("--list-devices", action="store_true", help="List all programmed devices from the CSV file")
    parser.add_argument("--identify-device", action="store_true", help="Identify serial number of connected device in BOOTSEL mode")
    parser.add_argument("--firmware-version", type=str, default="1.0.0", help="Firmware version to record in CSV")
    parser.add_argument("--programmed-by", type=str, help="Name of person programming the device")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--config", type=str, help="Specify a custom configuration file")
    parser.add_argument("--project-dir", type=str, help="Specify the root directory of the project (where CMakeLists.txt is located)")
    
    return parser.parse_args()

def production_programming(build_manager, serial_manager, csv_file, template_file=None, firmware_version="1.0.0", programmed_by=None, force=False, verify=True, reprogram=False):
    """Run the production programming workflow"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # ===== STEP 1: PREPARATION =====
    print("\n===== STEP 1: PREPARATION =====")
    
    if template_file is None:
        template_file = os.path.join(script_dir, "Templates", "serial_number.h.template")
    
    # Default to current user if not specified
    if programmed_by is None:
        programmed_by = os.getenv("USERNAME", "system")
    
    # If csv_file is not absolute, look for it relative to script directory
    if not os.path.isabs(csv_file):
        csv_file = os.path.join(script_dir, csv_file)
    
    # Get the next available serial number
    serial_number = serial_manager.get_next_available_serial(csv_file)
    if not serial_number:
        print("No available serial numbers found")
        return False
    
    print(f"Using serial number: {serial_number}")
    
    # ===== STEP 2: CLEAN =====
    print("\n===== STEP 2: CLEAN =====")
    print("Cleaning build directory to ensure no cached objects with old serial numbers...")
    build_manager.clean()
    
    # ===== STEP 3: CONFIGURE =====
    print("\n===== STEP 3: CONFIGURE =====")
    # Generate header file with the serial number and firmware version
    print(f"Generating header with serial number {serial_number} and firmware version {firmware_version}...")
    if not serial_manager.generate_serial_header(template_file, "serial_number.h", serial_number, firmware_version):
        print("ERROR: Failed to generate serial number header!")
        return False
    
    # Configure the build
    print("Configuring build system...")
    if not build_manager.configure():
        print("ERROR: Failed to configure the project!")
        return False
    
    # ===== STEP 4: COMPILE =====
    print("\n===== STEP 4: COMPILE =====")
    print("Compiling project with new serial number...")
    if not build_manager.build():
        print("ERROR: Failed to build the project!")
        return False
    
    # Deploy the firmware with serial number info
    uf2_path = build_manager.get_uf2_path()
    if not uf2_path:
        print("No UF2 file found in build directory")
        return False
    
    # ===== STEP 5: PREPARE FOR UPLOAD =====
    print("\n===== STEP 5: PREPARE FOR UPLOAD =====")
    print("Preparing firmware image...")
    
    # Embed serial number in UF2 file
    uf2_path = modify_uf2_with_serial(uf2_path, serial_number)
    if not uf2_path:
        print("ERROR: Failed to modify UF2 file with serial number!")
        return False
        
    # ===== STEP 6: UPLOAD =====
    print("\n===== STEP 6: UPLOAD =====")
    print(f"Uploading firmware with serial number {serial_number}...")
    print("Please ensure device is in BOOTSEL mode (hold BOOTSEL button while connecting)")
    
    # Flash the firmware using the deploy_firmware function
    success = deploy_firmware(build_manager, force, serial_number, verify=verify, reprogram=reprogram)
    
    if not success:
        print("\n===== ERROR: PROGRAMMING FAILED =====")
        print("Device programming failed! The serial number was NOT marked as used.")
        print("Possible causes:")
        print("  - Device was not in BOOTSEL mode")
        print("  - Serial number mismatch (old firmware detected)")
        print("  - Connection or hardware issue")
        print("\nPlease try again after ensuring the device is in BOOTSEL mode.")
        return False
    
    # ===== STEP 7: VERIFY =====
    print("\n===== STEP 7: VERIFY =====")
    if verify:
        print("Serial verification complete!")
    else:
        print("Serial verification skipped.")
        # After successful deployment, try to read the unique board ID
        # But only if verify was false - otherwise the device is already rebooted and not in BOOTSEL mode
        print("Attempting to read device unique ID...")
        pico_drive = find_pico_drive()
        if pico_drive:
            # Try to get the unique board ID
            unique_board_id = get_unique_board_id(pico_drive, DEFAULT_CONFIG['VERBOSE'])
            if unique_board_id:
                # Register this board ID with our serial number
                if serial_manager.register_board_id(unique_board_id, serial_number):
                    print(f"Registered board ID {unique_board_id} with serial number {serial_number}")
            else:
                print("Note: Could not read unique board ID from device")
        else:
            print("Device not found in BOOTSEL mode for board ID registration.")
    
    # ===== STEP 8: UPDATE DATABASE =====
    print("\n===== STEP 8: UPDATE DATABASE =====")
    print(f"Marking serial number {serial_number} as used in database...")
    
    # Mark the serial number as used
    if not serial_manager.update_serial_number_in_csv(csv_file, serial_number, firmware_version, programmed_by):
        print("WARNING: Failed to update serial number in CSV")
    
    # ===== STEP 9: COMPLETE =====
    print("\n===== STEP 9: COMPLETE =====")
    print(f"Successfully programmed device with serial number: {serial_number}")
    print(f"Firmware version: {firmware_version}")
    print(f"Programmed by: {programmed_by}")
    print("\nProgramming complete! The device is now ready for use.")
    return True

def deploy_firmware(build_manager, force=False, serial_number=None, verify=True, reprogram=False):
    """Deploy the firmware to a Pico in BOOTSEL mode"""
    # Get the file paths from the build directory
    uf2_path = build_manager.get_uf2_path()
    elf_path = build_manager.get_elf_path()
    
    if not uf2_path:
        print("No UF2 file found in build directory")
        return False
    
    # If we have a serial number, modify the UF2 file to include it
    if serial_number:
        uf2_path = modify_uf2_with_serial(uf2_path, serial_number)
        
    # Use picotool with ELF file
    if elf_path and os.path.exists(elf_path):
        print("Using picotool with ELF file")
        success = flash_with_picotool(elf_path, verbose=True)
        if success:
            # If verification is disabled, return success immediately
            if not verify:
                print("Device flashed successfully. Serial verification skipped.")
                return True
                
            # Device should reboot and appear as a serial port
            print("Device flashed successfully, waiting for device to reboot and appear as a serial port...")
            new_port = wait_for_new_serial_port(timeout=15)
            
            if new_port:
                # Wait a bit for the device to fully boot
                time.sleep(2)
                # Monitor the serial port for boot messages
                verified, detected_serial, detected_firmware = monitor_serial_port(new_port, serial_number)
                
                if verified:
                    print(f"Flash verification complete: Device serial {detected_serial}, firmware {detected_firmware}")
                    return True
                else:
                    if detected_serial and serial_number and detected_serial != serial_number:
                        if reprogram:
                            print(f"WARNING: Detected different serial number ({detected_serial}), but reprogramming with {serial_number} as requested")
                            # With --reprogram flag, we continue despite the mismatch
                            return True
                        else:
                            print(f"ERROR: Serial number mismatch! Expected {serial_number} but device reported {detected_serial}")
                            print("This likely means the device was flashed with old firmware or already has a different serial.")
                            print("Options:")
                            print("  1. Try again with a clean build (if it's an old firmware issue)")
                            print("  2. Use --reprogram flag if you want to change the device's existing serial number")
                            # Return False on serial number mismatch to prevent database update
                            return False
                    else:
                        print("Device flashed but serial verification failed or timed out.")
                        if detected_serial or detected_firmware:
                            print(f"Partial data: Serial={detected_serial}, Firmware={detected_firmware}")
                        # Allow continue for other verification issues - maybe timeout or incomplete data
                        return True
            else:
                print("Device flashed but did not appear as a serial port. Manual verification recommended.")
                # Continue anyway since flashing was successful
                return True
        
        print("Picotool with ELF file failed, trying with UF2...")
            
    # Fall back to using picotool with UF2 file
    success = flash_with_picotool(uf2_path, verbose=True)
    if success:
        # If verification is disabled, return success immediately
        if not verify:
            print("Device flashed successfully with UF2. Serial verification skipped.")
            return True
            
        # Device should reboot and appear as a serial port
        print("Device flashed successfully with UF2, waiting for device to reboot and appear as a serial port...")
        new_port = wait_for_new_serial_port(timeout=15)
        
        if new_port:
            # Wait a bit for the device to fully boot
            time.sleep(2)
            # Monitor the serial port for boot messages
            verified, detected_serial, detected_firmware = monitor_serial_port(new_port, serial_number)
            
            if verified:
                print(f"Flash verification complete: Device serial {detected_serial}, firmware {detected_firmware}")
                return True
            else:
                if detected_serial and serial_number and detected_serial != serial_number:
                    if reprogram:
                        print(f"WARNING: Detected different serial number ({detected_serial}), but reprogramming with {serial_number} as requested")
                        # With --reprogram flag, we continue despite the mismatch
                        return True
                    else:
                        print(f"ERROR: Serial number mismatch! Expected {serial_number} but device reported {detected_serial}")
                        print("This likely means the device was flashed with old firmware or already has a different serial.")
                        print("Options:")
                        print("  1. Try again with a clean build (if it's an old firmware issue)")
                        print("  2. Use --reprogram flag if you want to change the device's existing serial number")
                        # Return False on serial number mismatch
                        return False
                else:
                    print("Device flashed but serial verification failed or timed out.")
                    if detected_serial or detected_firmware:
                        print(f"Partial data: Serial={detected_serial}, Firmware={detected_firmware}")
                    # For other verification issues, continue
                    return True
        else:
            print("Device flashed but did not appear as a serial port. Manual verification recommended.")
            # Allow continue for port detection failure
            return True
        return True
    
    # If picotool fails completely, report an error
    print("Error: Picotool failed to flash the device.")
    print("Make sure the device is in BOOTSEL mode and properly connected.")
    return False

def main():
    """Main function"""
    args = parse_arguments()
    success = True
    
    # Determine script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Set global verbose flag in default config
    DEFAULT_CONFIG['VERBOSE'] = args.verbose
    
    # Load custom configuration file if specified
    config_file = args.config if args.config else os.path.join(script_dir, CONFIG_FILE)
    config = load_config(config_file, DEFAULT_CONFIG)
    
    # Process and validate paths
    config = process_paths(config)
    
    # Set project directory
    project_dir = find_project_dir(args.project_dir)
    config['PROJECT_DIR'] = project_dir
    
    # Verify that we have a valid project
    if not os.path.exists(os.path.join(project_dir, "CMakeLists.txt")):
        print(f"Warning: No CMakeLists.txt found in {project_dir}")
        if not args.flash and not args.identify_device:  # Only require CMakeLists.txt for build operations
            print(f"Error: {project_dir} doesn't appear to be a valid CMake project directory")
            print("Please specify a valid project directory with --project-dir")
            return 1
    
    # Print configuration if verbose
    if args.verbose:
        print("\nUsing the following configuration:")
        for key, value in config.items():
            print(f"{key}: {value}")
        print("")
    
    # Create managers
    build_manager = BuildManager(
        project_dir=config['PROJECT_DIR'],
        build_dir=config['BUILD_DIR'],
        config=config
    )
    
    serial_manager = SerialManager(
        script_dir=script_dir,
        project_dir=config['PROJECT_DIR']
    )
    
    # Handle flash a pre-built UF2 file option
    if args.flash:
        # Determine verification setting (enable by default unless skip_verify is true)
        verify = not args.skip_verify
        
        # Use picotool for flashing
        success = flash_with_picotool(args.flash, verbose=True)
        
        if success:
            # If verification is disabled, return success immediately
            if not verify:
                print("Device flashed successfully. Serial verification skipped.")
                return 0
                
            # Device should reboot and appear as a serial port
            print("Device flashed successfully, waiting for device to reboot and appear as a serial port...")
            new_port = wait_for_new_serial_port(timeout=15)
            
            if new_port:
                # Wait a bit for the device to fully boot
                time.sleep(2)
                # Monitor the serial port for boot messages
                verified, detected_serial, detected_firmware = monitor_serial_port(new_port, None)
                
                if verified:
                    print(f"Flash verification complete: Device serial {detected_serial}, firmware {detected_firmware}")
                else:
                    print("Device flashed but serial verification failed or timed out.")
                    if detected_serial or detected_firmware:
                        print(f"Partial data: Serial={detected_serial}, Firmware={detected_firmware}")
            else:
                print("Device flashed but did not appear as a serial port. Manual verification recommended.")
            
            return 0  # Success regardless of verification outcome
            
        # If picotool fails, report error
        print("Error: Picotool failed to flash the device.")
        print("Make sure the device is in BOOTSEL mode and properly connected.")
        return 1
        
    # Handle identify device option - but only if production programming wasn't already done
    if args.identify_device and not args.production:
        pico_drive = find_pico_drive()
        if pico_drive:
            # Get the board's unique ID
            board_id = get_unique_board_id(pico_drive, args.verbose)
            
            # Try to find the serial number
            serial_number = None
            
            # First check if the board ID is in our database
            if board_id:
                print(f"Connected device unique board ID: {board_id}")
                serial_number = serial_manager.lookup_serial_by_board_id(board_id)
                if serial_number:
                    print(f"Found registered serial number: {serial_number}")
            
            # If not found by board ID, try our other methods
            if not serial_number:
                serial_number = read_device_id(pico_drive, None, args.verbose)
            
            if serial_number:
                print(f"Connected device serial number: {serial_number}")
                
                # If production CSV is specified, look up the device details
                if args.production and os.path.exists(args.production):
                    csv_path = args.production
                    if not os.path.isabs(csv_path):
                        csv_path = os.path.join(script_dir, csv_path)
                    
                    serial_numbers = serial_manager.get_serial_numbers(csv_path)
                    if serial_numbers:
                        for entry in serial_numbers:
                            if entry.get('serial_number') == serial_number:
                                print("\nDevice Information:")
                                print(f"  Serial Number:    {serial_number}")
                                if board_id:
                                    print(f"  Unique Board ID:  {board_id}")
                                print(f"  Date Programmed:  {entry.get('date_programmed', 'Not recorded')}")
                                print(f"  Firmware Version: {entry.get('firmware_version', 'Not recorded')}")
                                print(f"  Programmed By:    {entry.get('programmed_by', 'Not recorded')}")
                                print(f"  Batch ID:         {entry.get('batch_id', 'Not recorded')}")
                                print(f"  Notes:            {entry.get('notes', 'None')}")
                                break
                return 0
            else:
                print("No device ID found on connected Pico.")
                if board_id:
                    print(f"This device has unique board ID: {board_id}")
                    print("This board ID is not yet registered in our database.")
                    print("You can register it by programming it with a serial number.")
                else:
                    print("This device was not programmed with this tool or could not be identified.")
                
                if not args.verbose:
                    print("Try running with -v flag for more detailed debugging information.")
                return 1
        else:
            print("No Raspberry Pi Pico in BOOTSEL mode detected.")
            print("Connect your Pico while holding the BOOTSEL button.")
            return 1
    
    # Handle serial number functions when --production is specified
    if args.production:
        csv_path = args.production
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(script_dir, csv_path)
        
        # Handle listing devices
        if args.list_devices:
            serial_manager.list_programmed_devices(csv_path)
            return 0
            
        # Handle just getting the next available serial number
        if args.next_serial:
            serial_number = serial_manager.get_next_available_serial(csv_path)
            if serial_number:
                print(f"Next available serial number: {serial_number}")
                return 0
            return 1
            
        # Otherwise, do production programming
        template_file = args.serial_template
        firmware_version = args.firmware_version
        programmed_by = args.programmed_by
        # Determine verification setting (enable by default unless skip_verify is true)
        verify = True
        if args.skip_verify:
            verify = False  # Explicitly disable verification
        
        success = production_programming(
            build_manager,
            serial_manager,
            csv_path, 
            template_file, 
            firmware_version, 
            programmed_by,
            args.force,
            verify=verify,
            reprogram=args.reprogram
        )
        return 0 if success else 1
    
    # Error handling for commands that require --production
    if args.next_serial:
        print("Error: --next-serial requires --production with a CSV file path")
        return 1
        
    if args.list_devices:
        print("Error: --list-devices requires --production with a CSV file path")
        return 1
    
    # Clean if requested
    if args.clean or args.rebuild:
        build_manager.clean()
        print("Build directory cleaned.")
    
    # Configure if requested or if no specific action was chosen
    if args.configure or args.rebuild or args.all or (not any([args.clean, args.build, args.deploy, args.flash, args.production])):
        success = build_manager.configure()
    
    # Build if requested or if no specific action was chosen
    if success and (args.build or args.rebuild or args.all or (not any([args.clean, args.configure, args.deploy, args.flash, args.production]))):
        success = build_manager.build()
    
    # Deploy if requested
    if success and (args.deploy or args.all):
        # Determine verification setting (enable by default unless skip_verify is true)
        verify = not args.skip_verify
        
        success = deploy_firmware(build_manager, args.force, verify=verify)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())