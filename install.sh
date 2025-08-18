#!/bin/bash
# VidSnatch Installer Script for macOS
set -e

INSTALL_DIR="$HOME/Applications/VidSnatch"
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🎬 Installing VidSnatch..."

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy Python server files
echo "🐍 Installing Python server..."
cp -r "$CURRENT_DIR/server/"* "$INSTALL_DIR/"

# Set up Python virtual environment
echo "⚙️ Setting up Python environment..."
cd "$INSTALL_DIR"

# Use system Python to create venv
python3 -m venv venv

# Activate venv and install dependencies
source venv/bin/activate
pip install --upgrade pip

# Install from the requirements.txt that was copied from installer
pip install -r "$CURRENT_DIR/requirements.txt"

echo "✅ Python environment ready!"

# Install menu bar app
echo "📱 Installing menu bar app..."
APPS_DIR="$HOME/Applications"
mkdir -p "$APPS_DIR"

# Copy the app bundle
cp -r "$CURRENT_DIR/VidSnatch.app" "$APPS_DIR/"

# Install Chrome extension files
echo "🌐 Installing Chrome extension..."
EXTENSION_DIR="$INSTALL_DIR/chrome-extension"
mkdir -p "$EXTENSION_DIR"
cp -r "$CURRENT_DIR/chrome-extension/"* "$EXTENSION_DIR/"

# Create desktop shortcut for extension installation
cat > "$HOME/Desktop/Install VidSnatch Extension.command" << 'EOF'
#!/bin/bash
echo "🌐 Opening Chrome Extensions page..."
echo "📋 Instructions:"
echo "1. Enable 'Developer mode' (toggle in top-right)"
echo "2. Click 'Load unpacked'"
echo "3. Navigate to: $HOME/Applications/VidSnatch/chrome-extension"
echo "4. Select the chrome-extension folder"
echo ""
read -p "Press Enter to open Chrome Extensions page..."
open -a "Google Chrome" chrome://extensions/
EOF

chmod +x "$HOME/Desktop/Install VidSnatch Extension.command"

# Add to Applications folder for Launchpad
echo "🚀 Adding to Launchpad..."

# Create a launch script that uses the correct Python environment
cat > "$INSTALL_DIR/start-vidsnatch.command" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
source venv/bin/activate
python3 "$HOME/Applications/VidSnatch.app/Contents/MacOS/VidSnatch"
EOF

chmod +x "$INSTALL_DIR/start-vidsnatch.command"

# Also create a menu bar launcher script
cat > "$INSTALL_DIR/launch-menubar.py" << 'EOF'
#!/usr/bin/env python3
import subprocess
import sys
import os

# Change to the VidSnatch directory
os.chdir(os.path.expanduser("~/Applications/VidSnatch"))

# Run the menu bar app
try:
    subprocess.run([sys.executable, os.path.expanduser("~/Applications/VidSnatch.app/Contents/MacOS/VidSnatch")])
except Exception as e:
    print(f"Error launching menu bar app: {e}")
EOF

chmod +x "$INSTALL_DIR/launch-menubar.py"

# Set permissions
chmod +x "$HOME/Applications/VidSnatch.app/Contents/MacOS/VidSnatch"

echo ""
echo "🎉 Installation Complete!"
echo ""
echo "📋 Next Steps:"
echo "1. ✅ VidSnatch menu bar app installed"
echo "2. 🔍 Look for the VidSnatch icon in your menu bar (top-right)"
echo "3. 🖱️  Click it to start/stop the server"
echo "4. 🌐 Install Chrome extension using the desktop shortcut"
echo ""
echo "🎬 Enjoy downloading videos with VidSnatch!"

# Try to launch the menu bar app
echo "🚀 Starting VidSnatch menu bar app..."

# Use our custom launcher that ensures proper Python environment
cd "$INSTALL_DIR"
source venv/bin/activate

# Launch the menu bar app in background
nohup python3 launch-menubar.py > "$INSTALL_DIR/app.log" 2>&1 &

# Give it a moment to start
sleep 3

# Check if the app is running
if pgrep -f "launch-menubar.py" > /dev/null || pgrep -f "VidSnatch" > /dev/null; then
    echo "✨ VidSnatch menu bar app is starting!"
    echo "🔍 Look for the VidSnatch icon in the top-right menu bar"
    echo "⏳ If you don't see it immediately, wait a few seconds for it to appear"
else
    echo "⚠️  Menu bar app may not have started properly."
    echo "📝 Check the log at: $INSTALL_DIR/app.log"
    echo "🔧 You can manually start it by running: $INSTALL_DIR/start-vidsnatch.command"
fi