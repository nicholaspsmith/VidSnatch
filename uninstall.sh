#!/bin/bash
# VidSnatch Complete Uninstaller
# Removes all traces of VidSnatch from your system

echo "🗑️  VidSnatch Uninstaller"
echo "========================="
echo ""

echo ""
echo "🛑 Stopping all VidSnatch processes..."

# Stop all VidSnatch processes
killall -9 VidSnatch 2>/dev/null && echo "   ✅ Stopped VidSnatch menu bar app" || echo "   ℹ️  No VidSnatch menu bar app running"
pkill -9 -f "web_server.py" 2>/dev/null && echo "   ✅ Stopped web server" || echo "   ℹ️  No web server running"
pkill -9 -f "VidSnatch" 2>/dev/null && echo "   ✅ Stopped VidSnatch processes" || echo "   ℹ️  No VidSnatch processes running"

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
echo "🔧 Checking for system integration..."

# Remove launch agents
LAUNCH_AGENTS_FOUND=false
for agent_dir in ~/Library/LaunchAgents /Library/LaunchAgents; do
    if [[ -d "$agent_dir" ]]; then
        for agent_file in "$agent_dir"/*vidsnatch* "$agent_dir"/*VidSnatch*; do
            if [[ -f "$agent_file" ]]; then
                rm -f "$agent_file" && echo "   ✅ Removed launch agent: $(basename "$agent_file")"
                LAUNCH_AGENTS_FOUND=true
            fi
        done
    fi
done

if [[ "$LAUNCH_AGENTS_FOUND" == false ]]; then
    echo "   ℹ️  No launch agents found"
fi

echo ""
echo "🔍 Final cleanup check..."

# Check for any remaining VidSnatch processes
REMAINING_PROCESSES=$(ps aux | grep -i vidsnatch | grep -v grep | grep -v "uninstall-vidsnatch")
if [[ ! -z "$REMAINING_PROCESSES" ]]; then
    echo "   ⚠️  Warning: Some VidSnatch processes may still be running:"
    echo "$REMAINING_PROCESSES"
else
    echo "   ✅ No remaining VidSnatch processes found"
fi

# Check for remaining files
REMAINING_FILES=""
for check_path in ~/Applications/VidSnatch ~/Applications/VidSnatch.app ~/Desktop/"Install VidSnatch Extension.command"; do
    if [[ -e "$check_path" ]]; then
        REMAINING_FILES="$REMAINING_FILES\n   - $check_path"
    fi
done

if [[ ! -z "$REMAINING_FILES" ]]; then
    echo "   ⚠️  Warning: Some files may not have been removed:"
    echo -e "$REMAINING_FILES"
else
    echo "   ✅ All files successfully removed"
fi

echo ""
echo "🎉 VidSnatch Uninstall Complete!"
echo ""
echo "📋 What was removed:"
echo "   • Menu bar application"
echo "   • Python server and dependencies"
echo "   • Chrome extension files"
echo "   • Desktop shortcuts"
echo "   • Launch agents (if any)"
echo "   • All configuration files"
echo ""
echo "📌 Note: Chrome extension needs to be manually removed from chrome://extensions/"
echo ""
echo "Thank you for using VidSnatch! 👋"

sleep 3
echo "Uninstall Complete"
exit 0