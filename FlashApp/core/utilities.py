#!/usr/bin/env python3
"""
Utility functions for RP_flasher
"""

import os
import subprocess
import platform
import sys
import shutil

def get_path(*parts):
    """Get path with proper separators for the current OS"""
    return os.path.join(*parts)

def get_project_path(project_dir, *parts):
    """Get path relative to the project directory"""
    return get_path(project_dir, *parts)

def get_script_path(*parts):
    """Get path relative to the script directory"""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return get_path(script_dir, *parts)

def get_build_path(project_dir, build_dir, *parts):
    """Get path relative to the build directory"""
    # The build directory is relative to the project directory
    return get_path(project_dir, build_dir, *parts)

def find_project_dir(specified_dir=None):
    """
    Find the project directory containing CMakeLists.txt
    
    Args:
        specified_dir: Optional explicitly specified project directory
        
    Returns:
        The absolute path to the project directory
    """
    if specified_dir:
        # Use command-line specified project directory
        project_dir = os.path.abspath(specified_dir)
        print(f"Using specified project directory: {project_dir}")
    else:
        # Try to find the project directory
        # Check if we're in the project root
        if os.path.exists("CMakeLists.txt"):
            project_dir = os.getcwd()
            print(f"Found CMakeLists.txt in current directory: {project_dir}")
        # Check if we're in a subdirectory of the project (like FlashApp)
        elif os.path.exists("../CMakeLists.txt"):
            project_dir = os.path.abspath("..")
            print(f"Found CMakeLists.txt in parent directory: {project_dir}")
        else:
            # Default to the script directory's parent (assuming FlashApp is a subdirectory)
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if os.path.exists(os.path.join(script_dir, "CMakeLists.txt")):
                project_dir = script_dir
                print(f"Using script parent directory as project root: {project_dir}")
            else:
                project_dir = os.getcwd()
                print(f"No CMakeLists.txt found. Using current directory as project root: {project_dir}")
                print("You should specify a project directory with --project-dir")
    
    return project_dir

# Command execution utilities
def run_command(cmd, cwd=None, check=True, verbose=False):
    """
    Run a command and return its output
    
    Args:
        cmd: Command list to execute
        cwd: Directory to run the command in
        check: Whether to check the return code
        verbose: Whether to print verbose output
        
    Returns:
        Command output on success, None on failure
    """
    if verbose:
        print(f"Running: {' '.join(cmd)}")
    else:
        print(f"Running: {cmd[0].split('/')[-1].split('\\\\')[-1]}")
    
    # Always show full command for CMake when debugging
    if cmd[0].endswith("cmake.exe") and not verbose:
        print(f"Full CMake command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            check=False,  # Don't raise exception, handle it manually 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            if verbose and result.stdout:
                print(result.stdout)
            return result.stdout
        else:
            print(f"Error executing command: {' '.join(cmd)}")
            print(f"Exit code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error executing command: {e}")
        return None

# File and directory utilities
def ensure_directory_exists(directory):
    """Create a directory if it doesn't exist"""
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")
    return directory

def copy_file(src, dest):
    """Copy a file, creating the destination directory if needed"""
    dest_dir = os.path.dirname(dest)
    if dest_dir:
        ensure_directory_exists(dest_dir)
    shutil.copy2(src, dest)
    print(f"Copied {src} to {dest}")
    return dest

# Configuration loading
def load_config(config_file, default_config=None):
    """
    Load configuration from a file
    
    Args:
        config_file: Path to the configuration file
        default_config: Dictionary of default config values
        
    Returns:
        Dictionary containing configuration values
    """
    # Start with default config if provided
    config = default_config.copy() if default_config else {}
    
    # Try to load from file
    if os.path.exists(config_file):
        try:
            print(f"Loading configuration from {config_file}")
            with open(config_file, 'r') as f:
                config_globals = {}
                exec(f.read(), config_globals)
                
                # Extract configuration variables
                for key in list(config_globals.keys()):
                    # Skip built-in Python attributes and modules
                    if not key.startswith('__') and not key.startswith('os'):
                        config[key] = config_globals[key]
            
            print(f"Configuration loaded successfully")
        except Exception as e:
            print(f"Error loading configuration from {config_file}: {e}")
    else:
        print(f"Configuration file {config_file} not found")
    
    return config