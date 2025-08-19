#!/bin/bash
# Build macOS Installer Package for VidSnatch

set -e

INSTALLER_DIR="macos-installer"
PACKAGE_NAME="VidSnatch-Installer"
BUILD_DIR="dist"

echo "🔨 Building VidSnatch Installer Package..."

# Clean previous builds
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create installer directory structure
mkdir -p "$INSTALLER_DIR/server"
mkdir -p "$INSTALLER_DIR/chrome-extension"

# Copy Python server files
echo "📦 Packaging Python server..."
cp *.py "$INSTALLER_DIR/server/" 2>/dev/null || true
cp -r modules "$INSTALLER_DIR/server/" 2>/dev/null || true

# Create requirements.txt with all dependencies
echo "📋 Creating requirements.txt with all dependencies..."
cat > "$INSTALLER_DIR/requirements.txt" << 'EOF'
# VidSnatch Dependencies - All required packages
flask==2.3.2
flask-cors==4.0.0
yt-dlp>=2023.12.30
colorama>=0.4.6
requests>=2.28.0
pystray==0.19.5
pillow>=10.0.0
EOF

# Copy Chrome extension
echo "🌐 Packaging Chrome extension..."
cp -r chrome-extension/* "$INSTALLER_DIR/chrome-extension/"

# Copy the menu bar app
echo "📱 Packaging menu bar app..."
cp -r macos-app/VidSnatch.app "$INSTALLER_DIR/"

# Copy uninstall script
echo "🗑️  Adding uninstall script..."
cp uninstall-vidsnatch.sh "$INSTALLER_DIR/uninstall.sh"

# Copy GUI installer
echo "🖥️  Adding GUI installer..."
cp gui_installer.py "$INSTALLER_DIR/"

# Make scripts executable
chmod +x "$INSTALLER_DIR/install.sh"
chmod +x "$INSTALLER_DIR/uninstall.sh"
chmod +x "$INSTALLER_DIR/gui_installer.py"
chmod +x macos-app/VidSnatch.app/Contents/MacOS/VidSnatch

# Create README for users
cat > "$INSTALLER_DIR/README.txt" << 'EOF'
🎬 VidSnatch Installer
===================

INSTALLATION:
Double-click "🎬 VidSnatch Installer.app" for a user-friendly graphical installer!

Or use command line options:
• "🎬 Install VidSnatch.command" to install VidSnatch
• "🗑️ Uninstall VidSnatch.command" to completely remove VidSnatch

What the installer does:
✅ Installs Python server with all dependencies
✅ Adds VidSnatch menu bar app  
✅ Sets up Chrome extension files
✅ Creates desktop shortcut for extension setup

What the uninstaller does:
✅ Stops all VidSnatch processes
✅ Removes all installed files
✅ Cleans up configuration and logs
✅ Frees up port 8080

After installation:
1. Look for VidSnatch icon in your menu bar
2. Click to start/stop the server
3. Install Chrome extension using desktop shortcut

Support: https://github.com/nicholaspsmith/VidSnatch
EOF

# Create GUI installer app bundle
echo "🖥️  Creating GUI installer app bundle..."
mkdir -p "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/MacOS"
mkdir -p "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/Resources"

# Create Info.plist for the app bundle
cat > "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VidSnatch Installer</string>
    <key>CFBundleIdentifier</key>
    <string>com.vidsnatch.installer</string>
    <key>CFBundleName</key>
    <string>VidSnatch Installer</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.9</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create the launcher script
cat > "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/MacOS/VidSnatch Installer" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../../../"
python3 gui_installer.py
EOF

chmod +x "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/MacOS/VidSnatch Installer"

# Copy icon to app bundle
cp chrome-extension/icons/icon128.png "$INSTALLER_DIR/🎬 VidSnatch Installer.app/Contents/Resources/icon.png" 2>/dev/null || true

# Create a clickable installer (command line fallback)
cat > "$INSTALLER_DIR/🎬 Install VidSnatch.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./install.sh
EOF

chmod +x "$INSTALLER_DIR/🎬 Install VidSnatch.command"

# Create a clickable uninstaller (command line fallback)
cat > "$INSTALLER_DIR/🗑️ Uninstall VidSnatch.command" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
./uninstall.sh
EOF

chmod +x "$INSTALLER_DIR/🗑️ Uninstall VidSnatch.command"

# Create the final package
echo "📦 Creating installer package..."
cd "$INSTALLER_DIR"
zip -r "../$BUILD_DIR/$PACKAGE_NAME.zip" . -x "*.DS_Store"
cd ..

# Copy icon for the package
cp chrome-extension/icons/icon128.png "$BUILD_DIR/VidSnatch-Icon.png" 2>/dev/null || true

echo ""
echo "✅ Installer package created successfully!"
echo "📁 Location: $BUILD_DIR/$PACKAGE_NAME.zip"
echo ""
echo "📋 Distribution Instructions:"
echo "1. Upload $PACKAGE_NAME.zip to your website/GitHub releases"
echo "2. Users download and unzip the package"
echo "3. Users double-click '🎬 VidSnatch Installer.app' for GUI installer"
echo "4. Or use '🎬 Install VidSnatch.command' for command line install"
echo "5. VidSnatch installs and appears in menu bar!"
echo ""
echo "🎉 Ready for distribution!"