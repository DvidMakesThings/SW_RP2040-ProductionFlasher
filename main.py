#!/usr/bin/env python3
"""
RP2040 Programmer - Main Entry Point

Factory programming tool for RP2040-based ENERGIS PDU devices.

This script:
1. Sets up logging
2. Initializes the GUI
3. Starts the main event loop

Usage:
    python main.py
    
Requirements:
    - Python 3.8+
    - See requirements.txt for dependencies
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox


def check_dependencies():
    """Check that all required dependencies are available."""
    missing = []
    
    try:
        import serial
    except ImportError:
        missing.append("pyserial")
        
    try:
        import psutil
    except ImportError:
        missing.append("psutil")
        
    try:
        import watchdog
    except ImportError:
        missing.append("watchdog")
        
    # Optional dependencies (warn but don't fail)
    optional_missing = []
    
    try:
        from svglib.svglib import svg2rlg
    except ImportError:
        optional_missing.append("svglib")
        
    try:
        from reportlab.graphics import renderPM
    except ImportError:
        optional_missing.append("reportlab")
        
    try:
        from PIL import Image
    except ImportError:
        optional_missing.append("Pillow")
        
    return missing, optional_missing


def setup_environment():
    """Set up the application environment."""
    # Add the application directory to the path
    app_dir = os.path.dirname(os.path.abspath(__file__))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
        
    # Create necessary directories
    from config.settings import Settings
    
    dirs_to_create = [
        Settings.ARTEFACT_BASE_PATH,
        os.path.dirname(Settings.LOG_FILE_PATH),
    ]
    
    for dir_path in dirs_to_create:
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)


def configure_tkinter():
    """Configure tkinter for better appearance."""
    root = tk.Tk()
    
    # Try to use a modern theme
    try:
        # On Windows, use 'vista' or 'winnative'
        # On Linux, use 'clam' or 'alt'
        style = tk.ttk.Style()
        available_themes = style.theme_names()
        
        preferred_themes = ['vista', 'winnative', 'clam', 'alt', 'default']
        for theme in preferred_themes:
            if theme in available_themes:
                style.theme_use(theme)
                break
    except Exception:
        pass
        
    # Configure default fonts
    try:
        default_font = ('Segoe UI', 9) if sys.platform == 'win32' else ('Ubuntu', 10)
        root.option_add('*Font', default_font)
    except Exception:
        pass
        
    return root


def main():
    """Main entry point."""
    # Check dependencies first
    missing, optional_missing = check_dependencies()
    
    if missing:
        print("ERROR: Missing required dependencies:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)
        
    if optional_missing:
        print("WARNING: Missing optional dependencies (some features may not work):")
        for dep in optional_missing:
            print(f"  - {dep}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(optional_missing)}")
        print()
        
    # Set up environment
    try:
        setup_environment()
    except Exception as e:
        print(f"ERROR: Failed to set up environment: {e}")
        sys.exit(1)
        
    # Import after environment setup
    from gui.main_window import MainWindow
    from config.settings import Settings
    
    # Create and configure root window
    root = configure_tkinter()
    
    # Set window icon (if available)
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(icon_path):
            icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, icon)
    except Exception:
        pass
        
    # Create main window
    try:
        app = MainWindow(root)
    except Exception as e:
        messagebox.showerror("Startup Error", 
            f"Failed to initialize application:\n\n{str(e)}")
        sys.exit(1)
        
    # Run the main loop
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        messagebox.showerror("Fatal Error", 
            f"An unexpected error occurred:\n\n{str(e)}")
        sys.exit(1)
        
    print("RP2040 Programmer exited.")


if __name__ == "__main__":
    main()