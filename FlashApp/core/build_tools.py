#!/usr/bin/env python3
"""
Build system tools for Raspberry Pi Pico projects
"""

import os
import subprocess
import shutil
from pathlib import Path

# Try different import strategies
try:
    from FlashApp.core.utilities import get_path, run_command, ensure_directory_exists
except ImportError:
    try:
        from core.utilities import get_path, run_command, ensure_directory_exists
    except ImportError:
        # Simple fallback implementations
        def get_path(*parts):
            """Get path with proper separators for the current OS"""
            return os.path.join(*parts)
            
        def run_command(cmd, cwd=None, check=True, verbose=False):
            """Run a command and return its output"""
            print(f"Running: {cmd}")
            try:
                result = subprocess.run(
                    cmd, 
                    cwd=cwd, 
                    check=False,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0:
                    return result.stdout
                else:
                    print(f"Error: {result.stderr}")
                    return None
            except Exception as e:
                print(f"Error executing command: {e}")
                return None
                
        def ensure_directory_exists(directory):
            """Create a directory if it doesn't exist"""
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            return directory

class BuildManager:
    """Class to manage the build process for Pico projects"""
    
    def __init__(self, project_dir, build_dir, config):
        """
        Initialize the BuildManager
        
        Args:
            project_dir: Path to the project directory containing CMakeLists.txt
            build_dir: Path to the build directory (relative to project_dir)
            config: Configuration dictionary with tool paths and settings
        """
        self.project_dir = project_dir
        self.build_dir = build_dir
        self.cmake_path = config.get('CMAKE_PATH')
        self.c_compiler_path = config.get('C_COMPILER_PATH')
        self.cxx_compiler_path = config.get('CXX_COMPILER_PATH')
        self.ninja_path = config.get('NINJA_PATH')
        self.python3_path = config.get('PYTHON3_PATH')
        self.project_name = config.get('PROJECT_NAME')
        self.verbose = config.get('VERBOSE', False)
        
        # Validate required tools
        self._validate_tools()
        
    def _validate_tools(self):
        """Validate that all required tools exist"""
        for tool, path in {
            'CMake': self.cmake_path,
            'C Compiler': self.c_compiler_path,
            'C++ Compiler': self.cxx_compiler_path,
            'Ninja': self.ninja_path
        }.items():
            if not os.path.exists(path):
                print(f"Warning: {tool} not found at {path}")
    
    def get_build_path(self, *parts):
        """Get path relative to the build directory"""
        return get_path(self.project_dir, self.build_dir, *parts)
    
    def clean(self):
        """Clean the build directory"""
        build_dir = self.get_build_path()
        if os.path.exists(build_dir):
            print(f"Cleaning build directory: {build_dir}")
            shutil.rmtree(build_dir)
            os.makedirs(build_dir)
            return True
        else:
            print(f"Build directory {build_dir} does not exist. Creating...")
            os.makedirs(build_dir, exist_ok=True)
            return True
    
    def configure(self):
        """Configure the project with CMake"""
        source_dir = self.project_dir
        build_dir = self.get_build_path()
        
        print(f"Using project directory: {source_dir}")
        print(f"Using build directory: {build_dir}")
        
        # Ensure the build directory exists
        ensure_directory_exists(build_dir)
            
        cmake_cmd = [
            self.cmake_path,
            "-DCMAKE_BUILD_TYPE=Debug",
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=TRUE",
            f"-DCMAKE_C_COMPILER:FILEPATH={self.c_compiler_path}",
            f"-DCMAKE_CXX_COMPILER:FILEPATH={self.cxx_compiler_path}",
            f"-DPython3_EXECUTABLE:STRING={self.python3_path}",
            f"-DCMAKE_MAKE_PROGRAM:FILEPATH={self.ninja_path}",
            "--no-warn-unused-cli",
            "-S", source_dir,  # Source directory with CMakeLists.txt
            "-B", build_dir,   # Build directory (using absolute path)
            "-G", "Ninja"
        ]
        
        print("Configuring project with CMake...")
        output = run_command(cmake_cmd, verbose=self.verbose)
        if output is None:
            return False
            
        return True
    
    def build(self):
        """Build the project with Ninja"""
        build_dir = self.get_build_path()
        print(f"Building in directory: {build_dir}")
        
        # Build with Ninja
        ninja_cmd = [
            self.ninja_path,
            "-C", build_dir
        ]
        
        print("Building project with Ninja...")
        output = run_command(ninja_cmd, verbose=self.verbose)
        if output is None:
            return False
            
        return True
    
    def get_uf2_path(self):
        """Get the path to the generated UF2 file"""
        # Find any UF2 file in the build directory
        uf2_files = list(Path(self.get_build_path()).glob("*.uf2"))
        if uf2_files:
            # If multiple UF2 files exist, take the newest one
            if len(uf2_files) > 1:
                # Sort by modification time (newest first)
                uf2_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                print(f"Multiple UF2 files found, using most recent: {uf2_files[0]}")
            return str(uf2_files[0])
        else:
            print(f"Error: No UF2 files found in build directory: {self.get_build_path()}")
            
    def get_elf_path(self):
        """Get the path to the generated ELF file"""
        # Find any ELF file in the build directory
        elf_files = list(Path(self.get_build_path()).glob("*.elf"))
        if elf_files:
            # If multiple ELF files exist, take the newest one
            if len(elf_files) > 1:
                # Sort by modification time (newest first)
                elf_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                print(f"Multiple ELF files found, using most recent: {elf_files[0]}")
            return str(elf_files[0])
        else:
            print(f"No ELF files found in build directory: {self.get_build_path()}")
            return None
            return None
    
    def rebuild(self):
        """Clean and rebuild the project"""
        return self.clean() and self.configure() and self.build()