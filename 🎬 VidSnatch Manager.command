#!/bin/bash
# VidSnatch Manager Launcher
# This script launches the graphical manager for installing, uninstalling, or reinstalling VidSnatch

cd "$(dirname "$0")" || exit

# Check if GUI manager exists
if [[ ! -f "gui_installer.py" ]]; then
  echo "❌ VidSnatch Manager not found!"
  echo "Please run ./build-installer.sh first to create the manager package."
  exit 1
fi

# Prefer Homebrew Python 3.12+ over system Python for better compatibility
PYTHON=""
if [[ -x "/opt/homebrew/bin/python3.12" ]]; then
  PYTHON="/opt/homebrew/bin/python3.12"
elif [[ -x "/opt/homebrew/bin/python3" ]]; then
  PYTHON="/opt/homebrew/bin/python3"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
fi

if [[ -z "$PYTHON" ]]; then
  echo "❌ Python 3 is not installed!"
  echo "Please install Python 3: brew install python@3.12"
  exit 1
fi

echo "Using Python: $PYTHON"

# Check if tkinter is available
$PYTHON -c "import tkinter" 2>/dev/null
if [[ $? -ne 0 ]]; then
  echo "⚠️  tkinter not available. Installing..."
  echo "This may require administrator privileges."

  # Try to install tkinter via homebrew
  if command -v brew &>/dev/null; then
    echo "Installing python-tk via Homebrew..."
    # Detect Python version for correct tk package
    PY_VER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    brew install "python-tk@$PY_VER" 2>/dev/null || brew install python-tk
  else
    echo "❌ Homebrew not found. Please install tkinter manually:"
    echo "   brew install python-tk@3.12"
    echo ""
    echo "Falling back to command line manager..."
    $PYTHON gui_installer.py
    exit $?
  fi
fi

# Launch the GUI installer/uninstaller
echo "🎬 Launching VidSnatch Manager..."
$PYTHON gui_installer.py

