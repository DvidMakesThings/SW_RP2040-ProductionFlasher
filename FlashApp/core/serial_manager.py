#!/usr/bin/env python3
"""
Serial number management for Raspberry Pi Pico projects
"""

import os
import csv
import datetime
import json
import re

# Try different import strategies
try:
    from FlashApp.core.utilities import get_path, ensure_directory_exists
except ImportError:
    try:
        from core.utilities import get_path, ensure_directory_exists
    except ImportError:
        def get_path(*parts):
            """Get path with proper separators for the current OS"""
            return os.path.join(*parts)
            
        def ensure_directory_exists(directory):
            """Create a directory if it doesn't exist"""
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            return directory

class SerialManager:
    """Class to manage serial numbers for production programming"""
    
    def __init__(self, script_dir, project_dir):
        """
        Initialize the SerialManager
        
        Args:
            script_dir: Path to the script directory (where CSV files are)
            project_dir: Path to the project directory (where header files go)
        """
        self.script_dir = script_dir
        self.project_dir = project_dir
        self.board_id_db_file = os.path.join(script_dir, "board_ids.json")
        self.serial_number_placeholder = "SERIAL_NUMBER_PLACEHOLDER"
        self.serial_template_file = os.path.join("Templates", "serial_number.h.template")
        self.serial_output_file = "serial_number.h"
    
    def get_serial_numbers(self, csv_file):
        """
        Read serial numbers from CSV file
        
        Args:
            csv_file: Path to the CSV file
            
        Returns:
            List of dictionaries containing serial number data
        """
        if not os.path.exists(csv_file):
            print(f"Error: Serial number CSV file {csv_file} not found")
            return None
        
        serial_numbers = []
        try:
            with open(csv_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    serial_numbers.append(row)
            return serial_numbers
        except Exception as e:
            print(f"Error reading serial numbers: {e}")
            return None
    
    def list_programmed_devices(self, csv_file):
        """
        List all programmed devices from the CSV file
        
        Args:
            csv_file: Path to the CSV file
            
        Returns:
            True on success, False on failure
        """
        serial_numbers = self.get_serial_numbers(csv_file)
        if not serial_numbers:
            return False
        
        programmed = []
        available = []
        
        # Sort into programmed and available
        for entry in serial_numbers:
            if entry.get('date_programmed', '').strip():
                programmed.append(entry)
            else:
                available.append(entry)
        
        # Print summary
        print(f"\nSerial Number Database: {csv_file}")
        print(f"Total entries: {len(serial_numbers)}")
        print(f"Programmed devices: {len(programmed)}")
        print(f"Available serial numbers: {len(available)}")
        
        # Print programmed devices
        if programmed:
            print("\nProgrammed Devices:")
            print("-" * 100)
            print(f"{'Serial Number':<15} {'Date':<12} {'Firmware':<10} {'Batch':<12} {'Programmed By':<15} {'Notes'}")
            print("-" * 100)
            for entry in programmed:
                print(f"{entry.get('serial_number', ''):<15} "
                     f"{entry.get('date_programmed', ''):<12} "
                     f"{entry.get('firmware_version', ''):<10} "
                     f"{entry.get('batch_id', ''):<12} "
                     f"{entry.get('programmed_by', ''):<15} "
                     f"{entry.get('notes', '')}")
        
        # Print available devices
        if available:
            print("\nAvailable Serial Numbers:")
            print("-" * 50)
            print(f"{'Serial Number':<15} {'Batch':<12} {'Notes'}")
            print("-" * 50)
            for entry in available:
                print(f"{entry.get('serial_number', ''):<15} "
                     f"{entry.get('batch_id', ''):<12} "
                     f"{entry.get('notes', '')}")
        
        print()
        return True
    
    def get_next_available_serial(self, csv_file):
        """
        Get the next available serial number from the CSV file
        
        Args:
            csv_file: Path to the CSV file
            
        Returns:
            Next available serial number or None if none available
        """
        serial_numbers = self.get_serial_numbers(csv_file)
        if not serial_numbers:
            return None
        
        # Find the first entry with an empty date_programmed
        for entry in serial_numbers:
            if not entry.get('date_programmed', '').strip():
                return entry.get('serial_number')
        
        print("No available serial numbers found in the CSV file")
        return None
    
    def update_serial_number_in_csv(self, csv_file, serial_number, firmware_version="1.0.0", programmed_by="system"):
        """
        Mark a serial number as used in the CSV file
        
        Args:
            csv_file: Path to the CSV file
            serial_number: Serial number to mark as used
            firmware_version: Firmware version to record
            programmed_by: Name of the person who programmed the device
            
        Returns:
            True on success, False on failure
        """
        serial_numbers = self.get_serial_numbers(csv_file)
        if not serial_numbers:
            return False
        
        # Find the entry with the matching serial number
        updated = False
        for entry in serial_numbers:
            if entry.get('serial_number') == serial_number and not entry.get('date_programmed', '').strip():
                entry['date_programmed'] = datetime.datetime.now().strftime('%Y-%m-%d')
                entry['firmware_version'] = firmware_version
                entry['programmed_by'] = programmed_by
                updated = True
                break
        
        if not updated:
            print(f"Serial number {serial_number} not found or already used")
            return False
        
        # Write back to CSV
        try:
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=serial_numbers[0].keys())
                writer.writeheader()
                writer.writerows(serial_numbers)
            return True
        except Exception as e:
            print(f"Error updating serial numbers CSV: {e}")
            return False
    
    def generate_serial_header(self, template_file, output_file, serial_number, firmware_version="1.0.0"):
        """
        Generate a header file with the serial number and firmware version
        
        Args:
            template_file: Template header file with placeholder
            output_file: Output header file name
            serial_number: Serial number to include
            firmware_version: Firmware version string (e.g., "1.0.0")
            
        Returns:
            True on success, False on failure
        """
        # Resolve paths relative to the script and project directories
        if not os.path.isabs(template_file):
            template_path = os.path.join(self.script_dir, template_file)
        else:
            template_path = template_file
            
        if not os.path.exists(template_path):
            print(f"Error: Template file {template_path} not found")
            return False
        
        # Output file should be placed in the project directory
        project_output_file = os.path.join(self.project_dir, output_file)
        
        try:
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Convert firmware version to numeric (e.g., 1.0.0 -> 100)
            numeric_version = ''.join(filter(str.isdigit, firmware_version))
            if len(numeric_version) < 3:
                numeric_version = numeric_version.ljust(3, '0')
            
            # Replace the placeholders with actual values
            output_content = template_content.replace(self.serial_number_placeholder, serial_number)
            
            # Replace firmware version placeholders
            output_content = output_content.replace("FIRMWARE_VERSION_PLACEHOLDER", firmware_version)
            output_content = output_content.replace("NUMERIC_VERSION_PLACEHOLDER", numeric_version)
            
            # Write the file to the project directory
            with open(project_output_file, 'w') as f:
                f.write(output_content)
            
            print(f"Generated serial number header file: {project_output_file}")
            
            
            return True
        except Exception as e:
            print(f"Error generating serial number header: {e}")
            return False
    
    # Board ID database management
    def load_board_id_db(self):
        """
        Load the board ID database that maps unique board IDs to serial numbers
        
        Returns:
            Dictionary mapping board IDs to serial numbers
        """
        if not os.path.exists(self.board_id_db_file):
            return {}
            
        try:
            with open(self.board_id_db_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading board ID database: {e}")
            return {}
    
    def save_board_id_db(self, db):
        """
        Save the board ID database
        
        Args:
            db: Dictionary mapping board IDs to serial numbers
            
        Returns:
            True on success, False on failure
        """
        try:
            with open(self.board_id_db_file, 'w') as f:
                json.dump(db, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving board ID database: {e}")
            return False
    
    def lookup_serial_by_board_id(self, board_id):
        """
        Look up a serial number by unique board ID in our database
        
        Args:
            board_id: Unique board ID
            
        Returns:
            Serial number if found, None otherwise
        """
        if not board_id:
            return None
            
        db = self.load_board_id_db()
        return db.get(board_id)
    
    def register_board_id(self, board_id, serial_number):
        """
        Register a board ID with a serial number in our database
        
        Args:
            board_id: Unique board ID
            serial_number: Serial number to associate with the board ID
            
        Returns:
            True on success, False on failure
        """
        if not board_id or not serial_number:
            return False
            
        db = self.load_board_id_db()
        db[board_id] = serial_number
        return self.save_board_id_db(db)