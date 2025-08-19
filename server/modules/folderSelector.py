"""Cross-platform folder selection dialog for Quikvid-DL."""

import os
import sys
import platform
import subprocess
from pathlib import Path

def select_download_folder():
    """
    Open a native folder selection dialog.
    Returns the selected folder path or None if cancelled.
    """
    # Try macOS AppleScript first (most reliable on macOS)
    if platform.system() == "Darwin":
        folder_path = _macos_folder_selection()
        if folder_path:
            return folder_path
    
    # Try tkinter for other platforms or as fallback
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Create a temporary root window and hide it
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        # Show folder selection dialog
        folder_path = filedialog.askdirectory(
            title="Select Download Folder for Videos",
            initialdir=str(Path.home() / "Downloads")
        )
        
        # Clean up the root window
        root.destroy()
        
        return folder_path if folder_path else None
        
    except (ImportError, Exception):
        # Fallback for systems without GUI support
        return _fallback_folder_selection()

def _macos_folder_selection():
    """
    Use macOS AppleScript to show a native folder selection dialog.
    Returns the selected folder path or None if cancelled.
    """
    try:
        # AppleScript to show folder selection dialog
        applescript = '''
        tell application "System Events"
            activate
            set chosenFolder to choose folder with prompt "Select Download Folder for Videos:" default location (path to downloads folder)
            return POSIX path of chosenFolder
        end tell
        '''
        
        # Execute AppleScript
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Remove trailing slash and return path
            folder_path = result.stdout.strip().rstrip('/')
            return folder_path
        else:
            return None
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return None

def _fallback_folder_selection():
    """
    Fallback folder selection using command line interface.
    Used when tkinter is not available.
    """
    print(" [!] GUI folder selection not available.")
    print(" [?] Please enter the full path where you'd like videos downloaded:")
    print(f" [?] (Press Enter for default: {Path.home() / 'Downloads'})")
    
    while True:
        user_input = input(" [?] Download folder path: ").strip()
        
        if not user_input:
            # Use default Downloads folder
            default_path = Path.home() / "Downloads"
            if default_path.exists():
                return str(default_path)
            else:
                # Create Downloads folder if it doesn't exist
                try:
                    default_path.mkdir(exist_ok=True)
                    return str(default_path)
                except PermissionError:
                    print(" [!] Cannot create Downloads folder. Please specify a different path.")
                    continue
        
        # Expand user path (handles ~)
        expanded_path = Path(user_input).expanduser().resolve()
        
        if expanded_path.exists() and expanded_path.is_dir():
            return str(expanded_path)
        elif expanded_path.parent.exists():
            # Parent exists, ask to create the folder
            try:
                create = input(f" [?] Folder doesn't exist. Create '{expanded_path}'? (Y/n): ")
                if create.lower() in ['', 'y', 'yes']:
                    expanded_path.mkdir(parents=True, exist_ok=True)
                    return str(expanded_path)
                else:
                    print(" [!] Please choose an existing folder or allow creation.")
                    continue
            except PermissionError:
                print(" [!] Permission denied. Please choose a different folder.")
                continue
        else:
            print(" [!] Invalid path. Please enter a valid folder path.")
            continue

def prompt_for_download_folder():
    """
    Prompt user to select a download folder with helpful instructions.
    Returns the selected folder path or None if cancelled.
    """
    print("\n [+] Welcome to Quikvid-DL!")
    print(" [?] First, let's choose where you'd like your downloaded videos saved.")
    print(" [?] A folder selection dialog will open...")
    
    # Small delay to let user read the message
    import time
    time.sleep(2)
    
    selected_folder = select_download_folder()
    
    if selected_folder:
        print(f" [+] Download folder set to: {selected_folder}")
        return selected_folder
    else:
        print(" [!] No folder selected. Using default location.")
        return None