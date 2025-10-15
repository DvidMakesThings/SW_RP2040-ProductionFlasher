#!/usr/bin/env python3
"""
Utilities for modifying UF2 files for device identification.

The UF2 file format consists of 512-byte blocks with a specific structure:
- Bytes 0-31: Block header
- Bytes 32-287: Data payload (256 bytes)
- Bytes 288-511: Reserved/padding

We can modify these blocks to include our device identification information.
"""

import os
import struct
import binascii
from pathlib import Path

# UF2 constants
UF2_MAGIC_START0 = 0x0A324655  # "UF2\n"
UF2_MAGIC_START1 = 0x9E5D5157  # Randomly selected
UF2_MAGIC_END    = 0x0AB16F30  # Ditto

class UF2File:
    """Class for handling UF2 files and embedding metadata"""
    
    def __init__(self, uf2_path):
        """
        Initialize a UF2File object
        
        Args:
            uf2_path: Path to the UF2 file
        """
        self.uf2_path = uf2_path
        self.data = None
        
    def read(self):
        """Read the UF2 file into memory"""
        try:
            with open(self.uf2_path, 'rb') as f:
                self.data = bytearray(f.read())
            return True
        except Exception as e:
            print(f"Error reading UF2 file: {e}")
            return False
    
    def write(self, output_path=None):
        """
        Write the UF2 data to a file
        
        Args:
            output_path: Path to write to (default is the original path)
            
        Returns:
            Path to the written file
        """
        if not output_path:
            output_path = self.uf2_path
            
        try:
            with open(output_path, 'wb') as f:
                f.write(self.data)
            return output_path
        except Exception as e:
            print(f"Error writing UF2 file: {e}")
            return None
    
    def embed_serial_number(self, serial_number):
        """
        Embed a serial number into the UF2 file
        
        Args:
            serial_number: Serial number to embed
            
        Returns:
            True on success, False on failure
        """
        if not serial_number:
            return False
            
        if not self.data:
            if not self.read():
                return False
        
        try:
            print(f"Adding serial number metadata to UF2 file...")
            
            # Create marker text (make it distinctive)
            marker = f"DEVICE_ID:{serial_number}:END"
            encoded_marker = marker.encode('ascii')
            print(f"Using marker: {marker}")
            
            # Simple approach 1: Add marker at the end of the file
            self.data.extend(encoded_marker)
            
            # Simple approach 2: Insert marker at regular intervals
            # Every 10KB should be frequent enough without making the file too large
            interval = 10 * 1024  # 10KB
            original_size = len(self.data) - len(encoded_marker)  # Don't count the marker we just added
            
            # Calculate insertion points
            insertion_points = list(range(interval, original_size, interval))
            
            # Insert markers at the calculated points
            # We need to insert from the end to avoid messing up the offsets
            for i in reversed(insertion_points):
                self.data[i:i] = encoded_marker
                
            print(f"Serial number embedded at {len(insertion_points) + 1} points in the UF2 file")
            return True
                
        except Exception as e:
            print(f"Error modifying UF2 file: {e}")
            return False

def modify_uf2_with_serial(uf2_path, serial_number):
    """
    Modifies a UF2 file to include the serial number in a way that can be
    easily detected when the device is in BOOTSEL mode.
    
    Args:
        uf2_path: Path to the UF2 file
        serial_number: Serial number to embed
        
    Returns:
        Path to the modified UF2 file (same as input)
    """
    if not serial_number:
        return uf2_path
    
    uf2_file = UF2File(uf2_path)
    if uf2_file.read() and uf2_file.embed_serial_number(serial_number):
        return uf2_file.write()
    else:
        return uf2_path

def extract_serial_from_uf2(uf2_path):
    """
    Extract serial number from a UF2 file if present
    
    Args:
        uf2_path: Path to the UF2 file
        
    Returns:
        Serial number if found, None otherwise
    """
    try:
        with open(uf2_path, 'rb') as f:
            data = f.read()
            
        # Look for our marker
        import re
        match = re.search(rb'DEVICE_ID:([^:]+):END', data)
        if match:
            serial = match.group(1).decode('ascii')
            return serial
    except Exception as e:
        print(f"Error examining UF2 file: {e}")
        
    return None