# Automated Testing Guide

The ShoulderSense test suite includes 64 automated unit and integration tests covering the backend, database, biomechanical quaternion math, repetition state machine, WebSocket streaming, flexion replay, and analytics performance.

## Running the Automated Test Suite

```bash
source .venv/bin/activate
cd backend
PYTHONPATH=. pytest -q
```

The original 12 core backend tests live in `tests/test_backend.py`; flexion and analytics coverage is in `tests/test_flexion.py` and `tests/test_performance.py`.

## Test Coverage Summary

1. `test_health_endpoint`: Verifies `/api/health` status, database connection, and monitoring flags.
2. `test_database_initialization`: Verifies SQLite schema creation and seeded exercise library (flexion, abduction, internal/external rotation).
3. `test_quaternion_normalization_and_relative_rotation`: Verifies Hamiltonian product, conjugate inverse, zero-norm safety, and 90° rotation accuracy.
4. `test_angle_calculator`: Verifies anatomical angle extraction, velocity differentiation, and spike rejection.
5. `test_repetition_counter`: Tests the Finite State Machine (REST -> ASCENT -> DESCENT -> REP COUNTED) with hysteresis and duration filtering.
6. `test_invalid_sensor_data`: Verifies HTTP 422 rejection when sensors are missing or corrupted.
7. `test_demo_simulator`: Tests deterministic kinematic trajectory generation and peak elevation.
8. `test_session_lifecycle`: Tests starting a session, streaming packets, finishing, calculating ROM, and database persistence.
9. `test_missing_ml_model_handling`: Verifies honest unconfigured status reporting when no trained model is loaded.
10. `test_analytics_endpoints`: Verifies longitudinal ROM queries, 7-day activity, and session comparison calculations.
11. `test_physiotherapy_report`: Verifies clinical report generation with narrative, ROM change, and disclaimer.
12. `test_websocket_stream`: Tests real-time `/ws/live` connection, initial status delivery, and ping/pong heartbeat.
