#!/bin/bash
# View server logs - shows last 50 lines and follows new entries

if [ "$1" = "tail" ]; then
    echo "📋 Following server logs (Ctrl+C to stop)..."
    tail -f .logs/server.log
elif [ "$1" = "error" ]; then
    echo "🚨 Showing error logs only..."
    grep -i "error\|exception\|failed" .logs/server.log | tail -20
elif [ "$1" = "clear" ]; then
    echo "🗑️  Clearing log files..."
    rm -f .logs/server.log*
    echo "✅ Logs cleared"
else
    echo "📋 Last 50 log entries:"
    echo "===================="
    if [ -f ".logs/server.log" ]; then
        tail -50 .logs/server.log
    else
        echo "No logs found. Start the server to generate logs."
    fi
    echo ""
    echo "💡 Usage:"
    echo "  ./view-logs.sh        - Show last 50 entries"
    echo "  ./view-logs.sh tail   - Follow logs in real-time"
    echo "  ./view-logs.sh error  - Show only errors"
    echo "  ./view-logs.sh clear  - Clear all logs"
fi