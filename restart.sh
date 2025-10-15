#!/bin/bash
# NDK Dashboard Restart Script
# This script kills any running Flask instances and starts a fresh one

echo "🔄 Restarting NDK Dashboard..."

# Kill any existing Flask processes (NDK-specific only)
echo "🛑 Stopping existing NDK Flask processes..."
pkill -f "ndk-dashboard.*run.py" 2>/dev/null || true
pkill -f "ndk-dashboard.*app.py" 2>/dev/null || true

# Wait a moment for processes to terminate
sleep 2

# Verify processes are stopped
if pgrep -f "ndk-dashboard.*run.py" > /dev/null || pgrep -f "ndk-dashboard.*app.py" > /dev/null; then
    echo "⚠️  Force killing remaining NDK processes..."
    pkill -9 -f "ndk-dashboard.*run.py" 2>/dev/null || true
    pkill -9 -f "ndk-dashboard.*app.py" 2>/dev/null || true
    sleep 1
fi

# Change to the dashboard directory
cd /home/nutanix/dev/ndk-dashboard

# Activate virtual environment and start Flask
echo "🚀 Starting Flask application..."
source .venv/bin/activate

# Start Flask in the background
nohup python run.py > flask.log 2>&1 &
FLASK_PID=$!

# Wait a moment for Flask to start
sleep 3

# Check if Flask is running
if ps -p $FLASK_PID > /dev/null; then
    echo "✅ Flask started successfully (PID: $FLASK_PID)"
    echo "📝 Logs: tail -f /home/nutanix/dev/ndk-dashboard/flask.log"
    echo "🌐 Dashboard: http://localhost:5000"
    echo "🔐 Default credentials: admin / admin"
    echo ""
    echo "To stop: pkill -f 'ndk-dashboard.*run.py'"
else
    echo "❌ Failed to start Flask. Check flask.log for errors:"
    tail -20 flask.log
    exit 1
fi