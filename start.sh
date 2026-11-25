#!/bin/bash

# Resolve directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "         ShoulderSense — Full-Stack Launcher             "
echo "=========================================================="

# Detect local IP address for ESP32 configuration
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
echo "  [LAN IP] Laptop IP Address: $LOCAL_IP"
echo "  --> ESP32 BACKEND_URL: http://$LOCAL_IP:8000/api/sensor/ingest"
echo "=========================================================="

# Trap Ctrl+C (SIGINT / SIGTERM) to stop both servers cleanly
cleanup() {
    echo ""
    echo "[ShoulderSense] Shutting down backend and frontend..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo "[ShoulderSense] All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1. Start Backend (FastAPI on Port 8000)
echo "[1/2] Starting FastAPI backend on http://0.0.0.0:8000..."
cd "$DIR/backend"
if [ -f "$DIR/.venv/bin/python3" ]; then
    "$DIR/.venv/bin/python3" run.py &
elif [ -f "venv/bin/python3" ]; then
    ./venv/bin/python3 run.py &
else
    python3 run.py &
fi
BACKEND_PID=$!

# Give backend a moment to initialize database
sleep 2

# 2. Start Frontend (Vite on Port 5173)
echo "[2/2] Starting React frontend on http://localhost:5173..."
cd "$DIR/frontend"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
npm run dev &
FRONTEND_PID=$!

sleep 2
echo ""
echo "=========================================================="
echo "  [READY] Web App:     http://localhost:5173"
echo "  [READY] Backend API: http://localhost:8000/docs"
echo "  Press Ctrl+C in this terminal anytime to stop both servers."
echo "=========================================================="

# Open the browser automatically
open "http://localhost:5173" 2>/dev/null || true

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
