import os
import tempfile
from pathlib import Path
import pytest
import numpy as np
from fastapi.testclient import TestClient

# Create a temporary sqlite db file for tests
test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = test_db_file.name
test_db_file.close()

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

from app.database.connection import engine, Base, SessionLocal
from app.database.init_db import init_db
from app.main import app
from app.services.biomechanics.quaternion_math import (
    normalize_quaternion,
    quaternion_conjugate,
    quaternion_multiply,
    relative_quaternion,
    quaternion_to_euler_angles
)
from app.services.biomechanics.angle_calculator import ShoulderAngleCalculator
from app.services.biomechanics.rep_counter import RepetitionCounter
from app.services.sensor.simulator import SensorSimulator
from app.services.sensor.ingestion import sensor_ingestion_service
from app.services.ml.movement_classifier import MovementQualityClassifier

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    init_db()
    yield
    # Cleanup test db
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

# 1. Backend Health
def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

# 2. Database Initialization & Seeded Exercises
def test_database_initialization(client):
    response = client.get("/api/exercises")
    assert response.status_code == 200
    exercises = response.json()
    assert len(exercises) >= 4
    keys = [e["exercise_key"] for e in exercises]
    assert "flexion" in keys
    assert "abduction" in keys
    assert "external_rotation" in keys
    assert "internal_rotation" in keys

# 3. Quaternion Mathematics & Normalization
def test_quaternion_normalization_and_relative_rotation():
    # Zero norm safety
    zero_q = np.array([0.0, 0.0, 0.0, 0.0])
    norm_zero = normalize_quaternion(zero_q)
    assert np.allclose(norm_zero, [0.0, 0.0, 0.0, 1.0])

    # Unit quaternion identity
    q_chest = np.array([0.0, 0.0, 0.0, 1.0])
    q_arm = np.array([0.0, 0.0, 0.0, 1.0])
    q_rel = relative_quaternion(q_chest, q_arm)
    assert np.allclose(q_rel, [0.0, 0.0, 0.0, 1.0])

    # Rotation test: 90 deg rotation around Y
    angle_rad = np.pi / 2.0
    q_arm_90 = np.array([0.0, np.sin(angle_rad / 2), 0.0, np.cos(angle_rad / 2)])
    q_rel_90 = relative_quaternion(q_chest, q_arm_90)
    roll, pitch, yaw = quaternion_to_euler_angles(q_rel_90)
    assert pytest.approx(pitch, abs=1.0) == 90.0

# 4. Angle Calculation & Spike Rejection
def test_angle_calculator():
    calc = ShoulderAngleCalculator()
    q_chest = np.array([0.0, 0.0, 0.0, 1.0])
    ang = np.radians(45.0)
    q_arm = np.array([0.0, np.sin(ang / 2), 0.0, np.cos(ang / 2)])
    
    out = calc.compute_angles(q_chest, q_arm, timestamp=100.0, exercise_key="flexion")
    assert pytest.approx(out["flexion"], abs=1.0) == 45.0
    assert out["quality_flag"] == "VALID"

# 5. Repetition Counter State Machine & ROM Calculation
def test_repetition_counter():
    counter = RepetitionCounter(threshold_up=40.0, threshold_down=20.0, min_rep_duration=0.5)
    
    counter.process_sample(angle=10.0, timestamp=1.0)
    assert counter.state == "REST"
    
    counter.process_sample(angle=30.0, timestamp=1.5)
    assert counter.state == "ASCENT"
    counter.process_sample(angle=75.0, timestamp=2.0)
    assert counter.state == "ASCENT"
    
    counter.process_sample(angle=65.0, timestamp=2.5)
    assert counter.state == "DESCENT"
    
    res = counter.process_sample(angle=15.0, timestamp=3.0)
    assert res["repetitions"] == 1
    assert counter.state == "REST"
    assert res["rom"] >= 60.0

    consistency = counter.compute_movement_consistency()
    assert consistency["total_reps"] == 1
    assert consistency["avg_rep_duration"] > 0

# 6. Invalid Sensor Data Handling
def test_invalid_sensor_data(client):
    malformed_payload = {
        "timestamp": 123456.0,
        "device_id": "esp32-shoulder-01",
        "source": "live",
        "sensors": {
            "chest": {"quaternion": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}
        }
    }
    response = client.post("/api/sensor/ingest", json=malformed_payload)
    assert response.status_code == 422

# 7. Demo Mode Sensor Simulator
def test_demo_simulator():
    sim = SensorSimulator(exercise_key="flexion", cycle_duration=4.0)
    pkt1 = sim.generate_packet(t=0.0)
    pkt2 = sim.generate_packet(t=2.0) # peak
    
    assert pkt1["source"] == "demo"
    assert "chest" in pkt1["sensors"]
    assert "upper_arm" in pkt1["sensors"]
    
    arm1_y = pkt1["sensors"]["upper_arm"]["quaternion"]["y"]
    arm2_y = pkt2["sensors"]["upper_arm"]["quaternion"]["y"]
    assert abs(arm2_y - arm1_y) > 0.1

# 8. Session Lifecycle: Start, Process, Finish, and Persist
def test_session_lifecycle(client):
    start_payload = {
        "patient_id": 1,
        "exercise_key": "flexion",
        "affected_side": "right",
        "data_source": "demo"
    }
    start_resp = client.post("/api/sessions", json=start_payload)
    assert start_resp.status_code == 200
    session_id = start_resp.json()["session_id"]

    sim = SensorSimulator(exercise_key="flexion")
    packet = sim.generate_packet()
    ingest_resp = client.post("/api/sensor/ingest", json=packet)
    assert ingest_resp.status_code == 200

    finish_payload = {
        "notes": "Automated unit test session",
        "save_samples": True
    }
    finish_resp = client.post(f"/api/sessions/{session_id}/finish", json=finish_payload)
    assert finish_resp.status_code == 200
    summary = finish_resp.json()
    assert summary["session"]["id"] == session_id
    assert summary["session"]["status"] == "completed"
    assert summary["session"]["data_source"] == "demo"

    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["notes"] == "Automated unit test session"

# 9. Missing ML Model Handling
def test_missing_ml_model_handling():
    clf = MovementQualityClassifier(model_path="non_existent_model.pkl")
    assert not clf.is_loaded
    dummy_feats = np.zeros((1, 7))
    res = clf.predict(dummy_feats)
    assert res["inference_status"] == "NOT_CONFIGURED"
    assert "not configured yet" in res["message"]

# 10. Analytics & Comparisons
def test_analytics_endpoints(client):
    rom_resp = client.get("/api/analytics/rom?exercise_key=flexion")
    assert rom_resp.status_code == 200
    assert isinstance(rom_resp.json(), list)

    weekly_resp = client.get("/api/analytics/weekly")
    assert weekly_resp.status_code == 200
    assert len(weekly_resp.json()) == 7

    sessions_resp = client.get("/api/sessions")
    sessions = sessions_resp.json()
    if len(sessions) >= 2:
        s1 = sessions[0]["id"]
        s2 = sessions[1]["id"]
        comp_resp = client.get(f"/api/analytics/compare?session_a={s1}&session_b={s2}")
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert "rom_difference" in comp_data

# 11. Physiotherapy Report Generation
def test_physiotherapy_report(client):
    sessions = client.get("/api/sessions").json()
    if sessions:
        s_id = sessions[0]["id"]
        rep_resp = client.get(f"/api/reports/sessions/{s_id}")
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert "report_id" in rep_data
        assert "clinical_summary" in rep_data
        assert "disclaimer" in rep_data

# 12. WebSocket Data Delivery
def test_websocket_stream(client):
    with client.websocket_connect("/ws/live") as websocket:
        initial = websocket.receive_json()
        assert initial["type"] == "STATUS_UPDATE"
        assert "data" in initial
        
        # Test ping pong
        websocket.send_json({"type": "PING", "timestamp": 12345.0})
        pong = websocket.receive_json()
        assert pong["type"] == "PONG"

