#!/usr/bin/env python3
"""
Configuration file for RP_flasher.py
Edit this file to match your system's paths
"""

import os

# Project configuration
PROJECT_NAME = "rpsetup"  # Your project name
BUILD_DIR = "build"       # Build directory name (relative to PROJECT_DIR)
PROJECT_DIR = None        # Will be set dynamically or by command-line args

# Path to user's home directory (automatically detected)
HOME_DIR = os.path.expanduser("~")

# SDK and Toolchain base directories
# You can use ~ for the home directory, or absolute paths like C:/Users/username/...
PICO_SDK_ROOT = "~/.pico-sdk"  # Base directory of your Pico SDK installationpython3
"""
Configuration file for RP_flasher.py
Edit this file to match your system's paths
"""

# Tool paths - Edit these paths to match your system setup
# Copy and paste the full absolute paths to your tools here if needed
CMAKE_PATH = f"{PICO_SDK_ROOT}\\cmake\\v3.31.5\\bin\\cmake.exe"
C_COMPILER_PATH = f"{PICO_SDK_ROOT}\\toolchain\\14_2_Rel1\\bin\\arm-none-eabi-gcc.exe" 
CXX_COMPILER_PATH = f"{PICO_SDK_ROOT}\\toolchain\\14_2_Rel1\\bin\\arm-none-eabi-g++.exe"
NINJA_PATH = f"{PICO_SDK_ROOT}\\ninja\\v1.12.1\\ninja.exe"
PYTHON3_PATH = "C:\\Python313\\python.exe"  # Path to Python 3 executable

# Process paths to replace ~ with actual home directory
def process_path(path):
    if path.startswith("~"):
        return os.path.expanduser(path)
    return path

CMAKE_PATH = process_path(CMAKE_PATH)
C_COMPILER_PATH = process_path(C_COMPILER_PATH)
CXX_COMPILER_PATH = process_path(CXX_COMPILER_PATH)
NINJA_PATH = process_path(NINJA_PATH)
PYTHON3_PATH = process_path(PYTHON3_PATH)

# Build configuration
CMAKE_BUILD_TYPE = "Debug"  # Debug, Release, RelWithDebInfo, or MinSizeRel