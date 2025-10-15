#!/usr/bin/env python3
"""
Functions for Raspberry Pi Pico device detection and communication
"""

import os
import platform
import re
import time
import shutil

# Try to import win32api for Windows systems
try:
    import win32api
    HAVE_WIN32API = True
except ImportError:
    HAVE_WIN32API = False

def get_path(*parts):
    """Get path with proper separators for the current OS"""
    return os.path.join(*parts)

def find_pico_drive():
    """
    Find the drive letter of a connected Pico in BOOTSEL mode
    
    Returns:
        Drive path on success, None if not found
    """
    if platform.system() == "Windows":
        if HAVE_WIN32API:
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            pico_drive = None
            
            for drive in drives:
                try:
                    volume_name = win32api.GetVolumeInformation(drive)[0]
                    if volume_name == "RPI-RP2":
                        pico_drive = drive
                        break
                except:
                    continue
                    
            if pico_drive:
                return pico_drive
            else:
                print("No Raspberry Pi Pico in BOOTSEL mode detected.")
                print("Connect your Pico while holding the BOOTSEL button.")
                return None
        else:
            print("The win32api module is not available. Manual copy may be required.")
            print("Try installing pywin32 with: pip install pywin32")
            return None
    elif platform.system() == "Linux":
        # For Linux, check common mount points
        potential_paths = [
            "/media/$USER/RPI-RP2",
            "/mnt/RPI-RP2",
            "/media/RPI-RP2"
        ]
        
        for path in potential_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                return expanded_path
                
        print("No Raspberry Pi Pico in BOOTSEL mode detected on Linux.")
        print("Connect your Pico while holding the BOOTSEL button.")
        return None
    elif platform.system() == "Darwin":  # macOS
        # For macOS, check common mount points
        potential_paths = [
            "/Volumes/RPI-RP2"
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                return path
                
        print("No Raspberry Pi Pico in BOOTSEL mode detected on macOS.")
        print("Connect your Pico while holding the BOOTSEL button.")
        return None
    else:
        # For other systems
        print(f"Auto-detection not implemented for {platform.system()}")
        return None

def get_unique_board_id(pico_drive, verbose=False):
    """
    Extract the unique board ID from the INFO_UF2.TXT file
    
    Args:
        pico_drive: Path to the Pico drive
        verbose: Whether to print verbose output
        
    Returns:
        Board ID if found, None otherwise
    """
    if not pico_drive:
        return None
        
    info_file_path = get_path(pico_drive, "INFO_UF2.TXT")
    if not os.path.exists(info_file_path):
        if verbose:
            print(f"INFO_UF2.TXT not found")
        return None
        
    try:
        with open(info_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            if verbose:
                print(f"INFO_UF2.TXT content: {content}")
                
            # The board ID is a 16-character hexadecimal value in the pico_get_unique_board_id_string() format
            # It's not directly in the INFO_UF2.TXT file by default, but we can still check
            hex_match = re.search(r'([0-9A-F]{16})', content)
            if hex_match:
                board_id = hex_match.group(1)
                if verbose:
                    print(f"Found board ID in hex format: {board_id}")
                return board_id
            
            # If not found, return None
            return None
    except Exception as e:
        if verbose:
            print(f"Error reading INFO_UF2.TXT: {e}")
        return None

def read_device_id(pico_drive, board_id_db=None, verbose=False):
    """
    Read the device ID (serial number) from a connected Pico in BOOTSEL mode.
    
    We use multiple approaches:
    1. First, check if we have our own pico_id.txt file (from previous programming)
    2. Check if the board ID is in our database
    3. Look for identifiers in binary files
    
    Args:
        pico_drive: Path to the Pico drive
        board_id_db: Optional database mapping board IDs to serial numbers
        verbose: Whether to print verbose output
        
    Returns:
        Serial number if found, None otherwise
    """
    if not pico_drive:
        if verbose:
            print("No Pico drive found")
        return None
    
    if verbose:
        print(f"Checking Pico drive: {pico_drive}")
        print(f"Listing root directory contents:")
        try:
            root_files = os.listdir(pico_drive)
            for item in root_files:
                print(f"  {item}")
        except Exception as e:
            print(f"Error listing directory: {e}")
            
    # Read the unique board ID from the device
    unique_id = get_unique_board_id(pico_drive, verbose)
    if unique_id and verbose:
        print(f"Unique board ID: {unique_id}")
        
    # If we have a unique ID, look it up in our database
    if unique_id and board_id_db:
        serial_number = board_id_db.get(unique_id)
        if serial_number:
            if verbose:
                print(f"Found matching serial number in database: {serial_number}")
            return serial_number
    
    # First, check for our special ID file
    for id_filename in ["pico_id.txt", ".pico_id.txt"]:
        id_file_path = get_path(pico_drive, id_filename)
        if os.path.exists(id_file_path):
            try:
                if verbose:
                    print(f"Found {id_filename} file")
                
                with open(id_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Extract the serial number
                    serial_match = re.search(r'PICO_SERIAL=(.+)', content)
                    if serial_match:
                        serial = serial_match.group(1).strip()
                        if verbose:
                            print(f"Found serial number in {id_filename}: {serial}")
                        return serial
            except Exception as e:
                if verbose:
                    print(f"Error reading {id_filename} file: {e}")
                
    # Try to get the serial number from the INFO_UF2.TXT file next
    info_file_path = get_path(pico_drive, "INFO_UF2.TXT")
    if os.path.exists(info_file_path):
        try:
            if verbose:
                print(f"Examining INFO_UF2.TXT file")
            
            with open(info_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if verbose and content:
                    print(f"INFO_UF2.TXT content: {content}")
                
                # Check if we have our custom board info field
                serial_match = re.search(r'Board-ID: Pico-([\w-]+)', content)
                if serial_match:
                    serial = serial_match.group(1)
                    if verbose:
                        print(f"Found serial number in INFO_UF2.TXT: {serial}")
                    return f"PICO-{serial}"
        except Exception as e:
            if verbose:
                print(f"Error examining INFO_UF2.TXT: {e}")
    
    # If we didn't find it in the INFO file, look for our marker
    if verbose:
        print("Looking for device ID pattern in binary data...")
    
    # Define the patterns we're looking for in the binary
    id_patterns = [
        rb'DEVICE_ID:([^:]+):END',          # Our defined pattern (exact match)
        rb'DEVICE_ID[:\s]*([A-Za-z0-9\-]+)', # More flexible pattern
        rb'PICO[_\-](\d\d\d)',              # Serial number pattern like PICO-001 or PICO_001
        rb'serial[_\-]?number[^\n\r]*PICO-(\d\d\d)',  # Serial number from header file
        rb'SERIAL[=:]([A-Za-z0-9\-]+)'      # Any SERIAL= or SERIAL: pattern
    ]
    
    try:
        # Check all files for our binary patterns
        for root, dirs, files in os.walk(pico_drive):
            for file in files:
                try:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    if file_size > 10 * 1024 * 1024:  # Skip files larger than 10MB
                        continue
                    
                    if verbose and not file.endswith(('.txt', '.htm')):
                        print(f"  Checking file: {file} ({file_size/1024:.1f}KB)")
                    
                    # Use binary mode to read the file
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        
                        # Search for all our patterns
                        for pattern in id_patterns:
                            match = re.search(pattern, content)
                            if match:
                                serial = match.group(1).decode('utf-8', errors='ignore')
                                if verbose:
                                    print(f"  Found serial number pattern in file: {file_path}")
                                # If we got just the number part, add the PICO- prefix
                                if serial.isdigit() or (serial.startswith("00") and len(serial) <= 3):
                                    serial = f"PICO-{serial}"
                                return serial
                except Exception as e:
                    if verbose:
                        print(f"  Error processing file {file}: {e}")
    except Exception as e:
        if verbose:
            print(f"Error during binary search: {e}")
    
    if verbose:
        print("No serial number information found on device")
            
    return None

def is_device_programmed(pico_drive, board_id_db=None, verbose=False):
    """
    Check if a device appears to already have firmware on it
    
    Args:
        pico_drive: Path to the Pico drive
        board_id_db: Optional database mapping board IDs to serial numbers
        verbose: Whether to print verbose output
        
    Returns:
        True if the device appears to be programmed, False otherwise
    """
    if not pico_drive:
        return False
    
    # First check for serial number in header file
    device_id = read_device_id(pico_drive, board_id_db, verbose)
    if device_id:
        print(f"Found device with serial number: {device_id}")
        return True
        
    # Fall back to the heuristic check
    index_path = get_path(pico_drive, "INDEX.HTM")
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Check for standard content in the Pico's default INDEX.HTM
                if "Raspberry Pi Pico" in content and "MicroPython" in content:
                    return False  # Likely a fresh device
        except:
            pass
    
    # If we can't determine, assume it might be programmed to be safe
    return True

def flash_with_picotool(uf2_file, verbose=False):
    """
    Flash a UF2 or ELF file to a connected Pico using picotool
    
    Args:
        uf2_file: Path to the UF2 or ELF file
        verbose: Whether to print verbose output
        
    Returns:
        True on success, False otherwise
    """
    import subprocess
    import os
    
    # Check if file exists
    if not os.path.exists(uf2_file):
        print(f"Error: File {uf2_file} not found")
        return False
    
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
    cmd = [picotool_path, "load", uf2_file, "-f", "-x"]
    
    print(f"Flashing {uf2_file} to Pico using picotool...")
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

def flash_uf2(uf2_file, force=False, board_id_db=None, verbose=False):
    """
    Flash a UF2 file to a connected Pico
    
    Args:
        uf2_file: Path to the UF2 file
        force: Whether to force flashing even if the device appears to be programmed
        board_id_db: Optional database mapping board IDs to serial numbers
        verbose: Whether to print verbose output
        
    Returns:
        True on success, False otherwise
    """
    if not os.path.exists(uf2_file):
        print(f"Error: UF2 file {uf2_file} not found")
        return False
    
    print(f"Flashing {uf2_file} to Pico...")
    print("Checking for Raspberry Pi Pico drive...")
    
    pico_drive = find_pico_drive()
    if not pico_drive:
        print("Error: No Raspberry Pi Pico in bootloader mode found.")
        print("Please connect your Pico while holding the BOOTSEL button.")
        return False
        
    # Check if device already appears to be programmed and get its ID if available
    serial_number = read_device_id(pico_drive, board_id_db, verbose)
    if not force and is_device_programmed(pico_drive, board_id_db, verbose):
        if serial_number:
            print(f"Warning: Device with serial number {serial_number} already has firmware installed.")
        else:
            print("Warning: Device appears to already have firmware installed.")
            print("This could be a device with custom firmware that was put into BOOTSEL mode.")
        
        print("To flash anyway, use --force option.")
        response = input("Do you want to continue flashing? (y/N): ").strip().lower()
        if response != 'y':
            print("Flashing cancelled.")
            return False
    
    # Extract filename from path
    uf2_filename = os.path.basename(uf2_file)
    dest_path = get_path(pico_drive, uf2_filename)
    print(f"Copying {uf2_file} to {dest_path}")
    
    # Make sure the destination is writable and accessible
    try:
        # Open for writing to test access
        with open(dest_path, 'w') as f:
            pass
        os.remove(dest_path)  # Remove the test file
    except Exception as e:
        print(f"Error: Cannot write to the Pico drive: {e}")
        return False
        
    # Copy the file with proper file synchronization to ensure complete write
    try:
        # Copy the file
        shutil.copy2(uf2_file, dest_path)
        
        # Force a file system flush to ensure the write is complete
        if hasattr(os, 'sync'):
            os.sync()  # On Unix-like systems
    except Exception as e:
        print(f"Error copying UF2 file to Pico: {e}")
        return False
        
    print("UF2 file copied, waiting for device to reboot...")
    
    # Give a small delay before checking if device has rebooted
    import time
    time.sleep(1)
    
    # Create a zero-byte REBOOT file to force reboot if needed
    try:
        reboot_path = get_path(pico_drive, "REBOOT")
        with open(reboot_path, 'w') as f:
            pass  # Create empty file
        # Force flush the file system again
        if hasattr(os, 'sync'):
            os.sync()
    except Exception as e:
        # If this fails, it's likely because the device already rebooted
        if verbose:
            print(f"Note: Could not create REBOOT file: {e}")
    
    # Use the verification function to check if device properly reboots
    drive_letter = pico_drive[0]  # Extract drive letter (e.g., 'E' from 'E:\')
    
    # Verify that the device exits bootloader mode successfully
    if verify_flash_successful(drive_letter):
        print("Firmware flashed successfully!")
        return True
    
    # If we get here, the device is still in bootloader mode
    print("Warning: Device is still in bootloader mode after flashing.")
    print("The UF2 file may not have been written correctly or the device didn't reboot.")
    print("You may need to manually reset the device or check the UF2 file.")
    
    # Device did not reboot properly
    return False

def create_id_file(pico_drive, serial_number, verbose=False):
    """
    Create an ID file on the Pico drive
    
    Args:
        pico_drive: Path to the Pico drive
        serial_number: Serial number to write
        verbose: Whether to print verbose output
        
    Returns:
        True on success, False otherwise
    """
    if not pico_drive or not serial_number:
        return False
    
    try:
        # Create a simple text file with the serial number
        id_file = get_path(pico_drive, "pico_id.txt")
        with open(id_file, 'w') as f:
            f.write(f"PICO_SERIAL={serial_number}\n")
        print(f"Created device ID file on Pico")
        return True
    except Exception as e:
        print(f"Note: Could not create device ID file: {e}")
        return False
        
        
def verify_flash_successful(original_drive_letter, max_wait=20, check_interval=1):
    """
    Verifies that a Pico device has successfully been flashed and rebooted
    out of bootloader mode.
    
    Args:
        original_drive_letter: The drive letter of the Pico in bootloader mode
        max_wait: Maximum time to wait for reboot (in seconds)
        check_interval: How often to check for reboot (in seconds)
        
    Returns:
        True if the device is no longer in bootloader mode, False otherwise
    """
    import time
    
    print("Verifying that device properly exits bootloader mode...")
    print(f"Waiting for device to reboot (this may take up to {max_wait} seconds)...")
    
    # Wait for the drive to disappear (indicating successful reboot out of bootloader)
    for i in range(int(max_wait / check_interval)):
        time.sleep(check_interval)
        
        # Check if the drive still exists
        drive_path = original_drive_letter + ":\\"
        if not os.path.exists(drive_path):
            print(f"Success! Drive {original_drive_letter}: is no longer present - device has rebooted with new firmware")
            return True
        
        # Print progress every 5 seconds
        if (i+1) % 5 == 0:
            print(f"Still waiting for reboot... ({i+1} seconds passed)")
    
    # Provide more detailed diagnostics if reboot failed
    print(f"Warning: Drive {original_drive_letter}: is still present - device may not have rebooted properly")
    
    try:
        # Try to list directory contents to see if the drive is responsive
        print(f"Checking drive contents:")
        files = os.listdir(drive_path)
        print(f"Files on {drive_path}: {files}")
    except Exception as e:
        print(f"Error accessing drive: {e}")
    
    print("You may need to manually press the reset button on your device.")
    return False