#!/usr/bin/env python3
"""
VidSnatch Setup Script - Automatic Virtual Environment Management
Similar to npm scripts, this handles venv creation and activation automatically.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def is_venv_active():
    """Check if we're currently in a virtual environment."""
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)

def venv_exists():
    """Check if a venv directory exists in the project."""
    venv_path = Path("venv")
    if platform.system() == "Windows":
        return (venv_path / "Scripts" / "python.exe").exists()
    else:
        return (venv_path / "bin" / "python").exists()

def create_venv():
    """Create a new virtual environment."""
    print(" [+] Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print(" [+] Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f" [!] Failed to create virtual environment: {e}")
        return False

def get_venv_python():
    """Get the path to the Python executable in the venv."""
    if platform.system() == "Windows":
        return str(Path("venv") / "Scripts" / "python.exe")
    else:
        return str(Path("venv") / "bin" / "python")

def get_venv_pip():
    """Get the path to pip in the venv."""
    if platform.system() == "Windows":
        return str(Path("venv") / "Scripts" / "pip.exe")
    else:
        return str(Path("venv") / "bin" / "pip")

def install_dependencies():
    """Install required dependencies in the venv."""
    print(" [+] Installing dependencies...")
    pip_path = get_venv_pip()
    
    # Install from requirements if it exists, otherwise install basic requirements
    if Path("requirements.txt").exists():
        try:
            subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
            print(" [+] Dependencies installed from requirements.txt")
            return True
        except subprocess.CalledProcessError:
            print(" [!] Failed to install from requirements.txt, installing basic deps...")
    
    # Install basic requirements
    basic_deps = ["yt-dlp", "colorama"]
    try:
        subprocess.run([pip_path, "install"] + basic_deps, check=True)
        print(" [+] Basic dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f" [!] Failed to install dependencies: {e}")
        return False

def ensure_venv():
    """Ensure virtual environment exists and is set up properly."""
    print(" [+] VidSnatch Environment Setup")
    print(" [+] " + "=" * 40)
    
    # If already in venv, we're good
    if is_venv_active():
        print(" [+] Virtual environment already active")
        return True
    
    # If venv exists but not active, we'll use it
    if venv_exists():
        print(" [+] Found existing virtual environment")
    else:
        # Create new venv
        if not create_venv():
            return False
    
    # Install dependencies if needed
    pip_path = get_venv_pip()
    try:
        # Check if yt-dlp is installed
        subprocess.run([pip_path, "show", "yt-dlp"], 
                      check=True, capture_output=True)
        print(" [+] Dependencies already installed")
    except subprocess.CalledProcessError:
        if not install_dependencies():
            return False
    
    print(" [+] Environment ready!")
    return True

def run_in_venv(script_name, args=None):
    """Run a Python script in the virtual environment."""
    if not ensure_venv():
        print(" [!] Failed to set up environment")
        sys.exit(1)
    
    python_path = get_venv_python()
    cmd = [python_path, script_name]
    if args:
        cmd.extend(args)
    
    print(f" [+] Running: {' '.join(cmd)}")
    print(" [+] " + "=" * 40)
    
    try:
        # Use execv to replace current process, like npm scripts
        if platform.system() == "Windows":
            subprocess.run(cmd)
        else:
            os.execv(python_path, cmd)
    except KeyboardInterrupt:
        print("\n [+] Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f" [!] Error running script: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python setup.py <script> [args...]")
        print("Examples:")
        print("  python setup.py main.py")
        print("  python setup.py server_only.py")
        print("  python setup.py start_with_server.py")
        sys.exit(1)
    
    script = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else None
    
    run_in_venv(script, args)

if __name__ == "__main__":
    main()