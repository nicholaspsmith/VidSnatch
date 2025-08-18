#!/bin/bash
# VidSnatch Uninstaller
# Completely removes VidSnatch from your system

cd "$(dirname "$0")"

echo "🗑️  VidSnatch Uninstaller"
echo "========================="
echo ""
echo "⚠️  This will completely remove VidSnatch from your system."
echo "   All downloaded files will remain, but the application will be uninstalled."
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "🛑 Stopping all VidSnatch processes..."

# Stop all VidSnatch processes
killall -9 VidSnatch 2>/dev/null && echo "   ✅ Stopped VidSnatch menu bar app" || echo "   ℹ️  No VidSnatch menu bar app running"
pkill -9 -f "web_server.py" 2>/dev/null && echo "   ✅ Stopped web server" || echo "   ℹ️  No web server running"
pkill -9 -f "VidSnatch" 2>/dev/null && echo "   ✅ Stopped VidSnatch processes" || echo "   ℹ️  No VidSnatch processes running"
pkill -9 -f "gui_installer.py" 2>/dev/null || true

# Kill anything using port 8080
PORT_PIDS=$(lsof -ti :8080 2>/dev/null)
if [[ ! -z "$PORT_PIDS" ]]; then
    echo "$PORT_PIDS" | xargs kill -9 2>/dev/null && echo "   ✅ Freed port 8080"
else
    echo "   ℹ️  Port 8080 is free"
fi

echo ""
echo "🗂️  Removing files and directories..."

# Remove installation directory
if [[ -d ~/Applications/VidSnatch ]]; then
    rm -rf ~/Applications/VidSnatch && echo "   ✅ Removed ~/Applications/VidSnatch"
else
    echo "   ℹ️  ~/Applications/VidSnatch not found"
fi

# Remove app bundle
if [[ -d ~/Applications/VidSnatch.app ]]; then
    rm -rf ~/Applications/VidSnatch.app && echo "   ✅ Removed ~/Applications/VidSnatch.app"
else
    echo "   ℹ️  ~/Applications/VidSnatch.app not found"
fi

# Remove desktop shortcuts
if [[ -f ~/Desktop/"Install VidSnatch Extension.command" ]]; then
    rm -f ~/Desktop/"Install VidSnatch Extension.command" && echo "   ✅ Removed desktop shortcut"
else
    echo "   ℹ️  No desktop shortcut found"
fi

echo ""
echo "🎉 VidSnatch Uninstall Complete!"
echo ""
echo "📋 What was removed:"
echo "   • Menu bar application"
echo "   • Python server and dependencies"
echo "   • Chrome extension files"
echo "   • Desktop shortcuts"
echo "   • All configuration files"
echo ""
echo "📌 Note: Chrome extension needs to be manually removed from chrome://extensions/"
echo "📁 Note: Downloaded video files remain in your Downloads folder"
echo ""
echo "Thank you for using VidSnatch! 👋"

sleep 3