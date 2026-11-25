# Setup & Installation Guide

## Prerequisites
- **Python:** 3.10+ (tested with 3.15)
- **Node.js:** v18+ (tested with Node 26)
- **C++ IDE (optional for hardware):** Arduino IDE 2.x or PlatformIO

---

## 1. Backend Setup

```bash
# 1. Create and activate a Python virtual environment at the repository root
python3 -m venv .venv
source .venv/bin/activate

cd backend

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI development server
python3 run.py
# Server starts at http://127.0.0.1:8000
# OpenAPI Docs available at http://127.0.0.1:8000/docs
```

---

## 2. Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Run Vite development server
npm run dev
# Frontend interface launches at http://localhost:5173
```

---

## 3. Switching Between Demo and Live Hardware

1. Open the web application in your browser (`http://localhost:5173`).
2. Navigate to **Live Monitoring** or **Device Settings**.
3. Toggle between **Demo Generator** and **ESP32 Live Mode**.
   - In **Demo Mode**, synthetic 20Hz biological exercise trajectories are generated automatically, allowing full end-to-end testing of live charts, repetition counting, ROM calculation, and report generation without hardware.
   - In **Live Mode**, the system listens for packets from the physical ESP32.
