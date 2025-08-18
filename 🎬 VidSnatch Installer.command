#!/bin/bash
# VidSnatch GUI Installer Launcher
# This script launches the graphical installer for VidSnatch

cd "$(dirname "$0")"

# Check if GUI installer exists
if [[ ! -f "gui_installer.py" ]]; then
    echo "❌ GUI installer not found!"
    echo "Please run ./build-installer.sh first to create the installer package."
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo "Please install Python 3 from https://www.python.org/"
    exit 1
fi

# Check if tkinter is available
python3 -c "import tkinter" 2>/dev/null
if [[ $? -ne 0 ]]; then
    echo "⚠️  tkinter not available. Installing..."
    echo "This may require administrator privileges."
    
    # Try to install tkinter via homebrew
    if command -v brew &> /dev/null; then
        echo "Installing python-tk via Homebrew..."
        brew install python-tk
    else
        echo "❌ Homebrew not found. Please install tkinter manually:"
        echo "   brew install python-tk"
        echo ""
        echo "Falling back to command line installer..."
        python3 gui_installer.py
        exit $?
    fi
fi

# Launch the GUI installer
echo "🎬 Launching VidSnatch Installer..."
python3 gui_installer.py

echo "Installation complete. Press any key to close..."
read -n 1