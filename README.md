# ShoulderSense — Smart Frozen Shoulder Monitoring & Rehabilitation System

Wearable IMU-Based Shoulder Movement Monitoring, Biomechanical Range-of-Motion (ROM) Extraction, and Longitudinal Progress Tracking for Adhesive Capsulitis.

---

## 1. Project Location

All source code, configuration, tests, documentation, and firmware files live in this repository. Work from the repository root after cloning:

```bash
git clone https://github.com/BDA-IIITA/Frozen_Shoulder-..git
cd Frozen_Shoulder-.
```

---

## 2. Directory Structure

```
shouldersense/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application instance & lifespan
│   │   ├── api/
│   │   │   ├── routes.py               # Documented REST API endpoints
│   │   │   └── websocket.py            # Real-time WebSocket streaming (/ws/live)
│   │   ├── core/
│   │   │   ├── config.py               # Environment & system configurations
│   │   │   └── logger.py               # Structured logging
│   │   ├── database/
│   │   │   ├── connection.py           # SQLAlchemy database connection (SQLite / PostgreSQL ready)
│   │   │   ├── models.py               # Patient, Device, Session, Sample, Exercise models
│   │   │   └── init_db.py              # Schema generation & baseline seed data
│   │   ├── schemas/
│   │   │   ├── sensor.py               # Documented IMU JSON schema & quaternion models
│   │   │   ├── session.py              # Session request/response DTOs
│   │   │   ├── device.py               # Diagnostics & device status DTOs
│   │   │   └── analytics.py            # Longitudinal ROM & weekly activity DTOs
│   │   └── services/
│   │       ├── biomechanics/
│   │       │   ├── quaternion_math.py  # Hamiltonian product, conjugate, Euler extraction
│   │       │   ├── angle_calculator.py # Elevation, abduction, velocity, spike filtering
│   │       │   └── rep_counter.py      # FSM repetition state machine & consistency scoring
│   │       ├── sensor/
│   │       │   ├── simulator.py        # Deterministic 20Hz biological Demo Mode generator
│   │       │   └── ingestion.py        # Central sensor pipeline (Demo / ESP32 Live Mode)
│   │       ├── analytics/
│   │       │   ├── progress_service.py # Recovery narrative, ROM delta, session comparison
│   │       │   ├── dataset_reference.py # SPARS9x wrist reference summary
│   │       │   ├── performance.py      # Experimental performance index
│   │       │   ├── session_metrics.py  # Per-session measurement aggregation
│   │       │   └── wrist_jerk.py       # Sparse wrist jerk estimate
│   │       ├── flexion/
│   │       │   ├── offline.py          # Dataset processing, training and evaluation
│   │       │   ├── inference.py        # Novelty and cycle scoring
│   │       │   ├── replay.py           # Recorded-session replay catalog
│   │       │   ├── dataset.py          # SPARS9x CSV loading
│   │       │   ├── annotation.py       # Cycle annotation utilities
│   │       │   ├── exercise_rep_study.py # Repetition reference study
│   │       │   ├── rep_study.py        # Neutral-candidate repetition study
│   │       │   ├── repetitions.py      # Wrist cycle estimation
│   │       │   ├── signal.py           # Signal helpers
│   │       │   └── live_rep_reference.py # Live repetition reference loader
│   │       └── ml/
│   │           └── movement_classifier.py # Modular ML candidate interface (unvalidated safeguard)
│   ├── tests/
│   │   ├── test_backend.py             # Core backend and WebSocket tests
│   │   ├── test_flexion.py             # Dataset replay and flexion pipeline tests
│   │   └── test_performance.py         # Analytics performance tests
│   ├── requirements.txt                # Python dependencies
│   └── run.py                          # Backend launch runner
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Header.tsx          # Telemetry status, patient profile, mode pills
│   │   │   │   └── Sidebar.tsx         # Persistent desktop & mobile drawer navigation
│   │   │   ├── common/
│   │   │   │   └── MetricCard.tsx      # Clean medical metric cards
│   │   │   └── monitoring/
│   │   │       ├── ArmVisualization.tsx # SVG interactive kinematic upper-body diagram
│   │   │       ├── MovementAnalytics.tsx # Dataset replay movement analytics
│   │   │       ├── OrientationDiagnostics.tsx # Sensor orientation diagnostics
│   │   │       ├── PersonalProgress.tsx # Personal baseline comparison
│   │   │       └── SessionTimeline.tsx # Session timeline view
│   │   ├── pages/
│   │   │   ├── OverviewPage.tsx        # Dashboard: ROM trends, weekly activity, telemetry
│   │   │   ├── LiveMonitoringPage.tsx  # Real-time charts, controls, FSM rep states, save modal
│   │   │   ├── ExerciseLibraryPage.tsx # Shoulder flexion, abduction, internal/external rotation
│   │   │   ├── SessionsPage.tsx        # Session table, sample charts, session comparison tool
│   │   │   ├── ProgressAnalyticsPage.tsx# Longitudinal graphs & measured ROM change %
│   │   │   ├── ReportsPage.tsx         # Physiotherapist clinical report with print layout
│   │   │   └── DeviceSettingsPage.tsx  # Calibration workflow, ESP32 diagnostics, JSON payload
│   │   ├── services/
│   │   │   ├── api.ts                  # REST API client
│   │   │   └── websocket.ts            # WebSocket client with heartbeat & reconnect
│   │   ├── types/
│   │   │   └── index.ts                # TypeScript interfaces
│   │   ├── App.tsx                     # Main layout & routing state
│   │   ├── main.tsx                    # React DOM root
│   │   └── index.css                   # Tailwind CSS styling
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   └── vite.config.ts                  # Vite config with backend proxy
├── firmware/
│   ├── esp32_bno086_example/
│   │   └── esp32_bno086_example.ino    # Arduino C++ dual BNO086 I2C Wi-Fi transmitter
│   └── esp32_bno086_dual_bus/
│       └── esp32_bno086_dual_bus.ino   # Dual I2C-bus BNO086 variant
├── docs/
│   ├── architecture.md                 # Biomechanical model & FSM documentation
│   ├── sensor_protocol.md              # Documented JSON schema & wiring diagram
│   ├── setup.md                        # Step-by-step installation instructions
│   ├── testing.md                      # Automated test suite documentation
│   ├── flexion-pipeline.md             # Ten-participant pilot pipeline
│   ├── spars9x-replay.md               # 20-participant replay and evaluation guide
│   ├── spars9x-cycle-review.csv        # Manual cycle annotation review data
│   ├── live-angle-validation.md        # Live angle validation notes
│   └── personal-progress.md            # Personal baseline method
├── .env.example
└── README.md
```

> The raw `dataset/` and generated `artifacts/` directories are local-only and intentionally git-ignored. Recreate them with the commands in [SPARS9x replay and evaluation](docs/spars9x-replay.md).

---

## 3. Quick Start Guide

### Step 1: Start the Backend (Port 8000)

```bash
cd backend
source ../.venv/bin/activate
python3 run.py
```
- API is running at: `http://localhost:8000`
- Interactive Swagger documentation: `http://localhost:8000/docs`

### Step 2: Start the Frontend (Port 5173)

In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
- Web Application is running at: `http://localhost:5173`

---

## 4. Running Automated Tests

```bash
cd backend
source ../.venv/bin/activate
PYTHONPATH=. pytest -q
```

All 64 automated tests run and verify:
1. Health endpoint (`/api/health`)
2. Database initialization and exercise configurations
3. Quaternion normalization, Hamiltonian multiplication, relative rotation
4. Shoulder angle extraction and velocity spike rejection
5. Repetition counting state machine (REST -> ASCENT -> DESCENT -> COUNT)
6. Invalid sensor data rejection (HTTP 422)
7. Demo simulator deterministic trajectory generation
8. Session lifecycle (start, sample ingestion, finish, database persistence)
9. Missing ML model handling (`"ML movement assessment is not configured yet"`)
10. Analytics & multi-session comparison endpoints
11. Physiotherapy clinical report generation
12. Real-time WebSocket streaming (`/ws/live`)

The remaining tests in `test_flexion.py` and `test_performance.py` cover SPARS9x dataset loading, replay, cycle/repetition scoring, and analytics performance.

---

## 5. Demonstration Workflow (Works Without Hardware)

1. Open `http://localhost:5173` in your browser.
2. Observe the **Overview Dashboard** with initial baseline session history, ROM progress chart, weekly frequency, and data-grounded recovery trend narrative.
3. Click **Live Monitoring** in the sidebar.
4. The system is in **Demo Generator** mode by default. Select an exercise (e.g. *Shoulder Flexion* or *Shoulder Abduction*), choose the affected arm (*Right* or *Left*), and click **Start Session**.
5. Watch the real-time kinematic **Arm Visualization** and **Angle & Velocity vs. Time** charts update dynamically at 20 Hz as the arm elevates smoothly.
6. The repetition state machine automatically tracks movement phases (`REST` -> `ASCENT` -> `DESCENT`) and increments verified repetitions.
7. Click **Finish & Save**, add clinical notes (e.g., *"Good form, full extension"*), and confirm.
8. Navigate to **Rehabilitation Sessions** to inspect the saved session, view downsampled time-series graphs, or run the **Compare Two Sessions** tool.
9. Open **Reports** to review and print a standardized physiotherapist consultation summary.
10. Open **Device Settings** to examine ESP32 telemetry, test neutral baseline calibration, or switch to **Live ESP32 Wearable** mode.

---

## 6. Connecting the Physical ESP32 Hardware

1. Flash `firmware/esp32_bno086_example/esp32_bno086_example.ino` (or the dual-bus variant in `firmware/esp32_bno086_dual_bus/`) to your ESP32-WROOM-32 via Arduino IDE.
2. Ensure both the ESP32 and your computer are connected to the same local Wi-Fi network.
3. In `esp32_bno086_example.ino`, set `BACKEND_INGEST_URL = "http://<YOUR_LAPTOP_IP>:8000/api/sensor/ingest"`.
4. In the web interface, switch from **Demo Mode** to **Live Mode**.
5. Live sensor readings will immediately stream into the dashboard with the **LIVE** badge.


## Offline flexion reference pipeline

See [SPARS9x replay and evaluation](docs/spars9x-replay.md) for installation, offline processing and model training, real dataset replay, and session analytics. The [ten-participant pilot](docs/flexion-pipeline.md) documents the original signal and sensor contract.
