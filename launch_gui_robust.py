#!/usr/bin/env python3
"""
Robust GUI launcher for VidSnatch Manager
This script ensures the GUI is properly launched and brought to the foreground
"""

import os
import sys
import subprocess
import time

def main():
    # Change to the VidSnatch directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check if gui_installer.py exists
    if not os.path.exists('gui_installer.py'):
        print("❌ gui_installer.py not found!")
        return 1
    
    try:
        # Launch the GUI installer
        print("🎬 Launching VidSnatch Manager...")
        
        # Create the subprocess with proper settings for GUI
        env = os.environ.copy()
        env['PYTHONPATH'] = script_dir
        
        # Use subprocess to launch GUI with proper handling
        process = subprocess.Popen(
            [sys.executable, 'gui_installer.py'],
            env=env,
            cwd=script_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )
        
        # Brief delay to let the window initialize
        time.sleep(0.5)
        
        # Use AppleScript to ensure the window is visible and focused
        try:
            # First try to activate by application name
            subprocess.run([
                'osascript', '-e',
                'tell application "Python" to activate'
            ], check=False, timeout=2)
        except:
            try:
                # Fallback: try to bring any Python process to front
                subprocess.run([
                    'osascript', '-e',
                    'tell application "System Events" to set frontmost of every process whose name contains "Python" to true'
                ], check=False, timeout=2)
            except:
                pass  # If this fails too, just continue
        
        print(f"✅ VidSnatch Manager launched (PID: {process.pid})")
        return 0
        
    except Exception as e:
        print(f"❌ Failed to launch VidSnatch Manager: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())