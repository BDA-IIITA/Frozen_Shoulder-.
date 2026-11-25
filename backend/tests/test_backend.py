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
    pkt1 = sim.generate_packet(t=sim.start_epoch)
    pkt2 = sim.generate_packet(t=sim.start_epoch + 2.0) # peak
    
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



@pytest.mark.parametrize("with_model", [False, True])
def test_wrist_only_http_websocket_and_persistence(monkeypatch, tmp_path, with_model):
    import joblib
    import sklearn
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import OneClassSVM
    from app.services.flexion.signal import FEATURES, SCHEMA

    path = tmp_path / "flexion.joblib"
    if with_model:
        fixture = np.random.default_rng(12).normal(size=(32, len(FEATURES)))
        model = make_pipeline(StandardScaler(), OneClassSVM()).fit(fixture)
        joblib.dump({"model": model, "schema": SCHEMA, "scikit_learn": sklearn.__version__}, path)
    monkeypatch.setenv("FLEXION_MODEL_PATH", str(path))
    with TestClient(app) as client:
        started = client.post("/api/sessions", json={"data_source": "live"})
        session_id = started.json()["session_id"]
        assert client.post("/api/sessions", json={"data_source": "live"}).status_code == 409
        packet = {
            "timestamp": 1.0, "source": "live", "sensors": {"wrist": {
                "accelerometer": {"x": 0, "y": 0, "z": 9.81},
                "gyroscope": {"x": 0, "y": 1, "z": 0},
            }},
        }
        with client.websocket_connect("/ws/live") as websocket:
            assert websocket.receive_json()["type"] == "STATUS_UPDATE"
            websocket.send_json({"type": "SENSOR_PACKET", "data": packet})
            sample = websocket.receive_json()
            assert sample["type"] == "SENSOR_SAMPLE"
            assert sample["data"]["quality_flag"] == "ORIENTATION_UNAVAILABLE"
            assert sample["data"]["analytics"]["relative_excursion_deg"] is None

        for i in range(1, 200):
            packet["timestamp"] = 1 + i / 50
            response = client.post("/api/sensor/ingest", json=packet)
            assert response.status_code == 200
        live = response.json()["sample"]["analytics"]
        assert live["windows"] == 1
        assert "latest_prediction" not in live
        assert "scored_windows" not in live
        assert live["wrist_jerk_rms_m_s3"] == pytest.approx(0, abs=1e-9)
        assert live["trunk_peak_deg"] is None
        finished = client.post(f"/api/sessions/{session_id}/finish", json={})
        assert finished.status_code == 200
        metrics = finished.json()["session"]["movement_analytics"]
        assert metrics["relative_excursion_deg"] is None
        assert metrics["estimated_repetition_count"] is None
        assert metrics["wrist_gyro_peak_rad_s"] == pytest.approx(1)
        assert client.get(f"/api/sessions/{session_id}").json()["movement_analytics"] == metrics
        assert client.post(f"/api/sessions/{session_id}/finish", json={}).json() == finished.json()


def test_live_calibration_requires_fresh_paired_orientation(client):
    assert client.post("/api/devices/esp32-shoulder-01/connect", json={"mode": "live"}).status_code == 200
    packet = SensorSimulator().generate_packet()
    packet["source"] = "live"
    packet["device_id"] = "calibration-test"
    packet["sensors"]["upper_arm"]["quaternion"] = {
        "x": 0, "y": np.sin(np.pi / 6), "z": 0, "w": np.cos(np.pi / 6),
    }
    url = "/api/devices/calibration-test/calibrate"
    assert client.post(url).status_code == 409
    response = client.post("/api/sensor/ingest", json=packet)
    assert response.json()["sample"]["primary_angle"] > 45
    assert client.post(url).status_code == 200
    packet["timestamp"] += .02
    response = client.post("/api/sensor/ingest", json=packet)
    assert response.json()["sample"]["primary_angle"] == pytest.approx(0, abs=.1)


def test_replay_websocket_live_feature_parity_and_persistence(client, tmp_path, monkeypatch):
    from app.services.flexion.signal import FEATURES, FS, WINDOW, features

    monkeypatch.setenv("SPARS9X_RECORDINGS", str(tmp_path))
    key = "spars9x_s42_1000"
    clock = np.arange(WINDOW) / FS
    raw = np.column_stack((np.sin(clock), clock * 0, np.full(WINDOW, 9.81),
                           np.cos(clock), clock * 0, clock * 0))
    np.savez(tmp_path / f"{key}.npz", raw=raw, subject="spars9x_s42", start=1000, side=2, label=8)
    catalog = client.get("/api/replay/recordings").json()
    assert len(catalog) == 1 and catalog[0]["samples"] == WINDOW
    assert client.post("/api/sessions", json={"data_source": "replay", "recording_id": "../x"}).status_code == 404
    with client.websocket_connect("/ws/live") as socket:
        assert socket.receive_json()["type"] == "STATUS_UPDATE"
        started = client.post("/api/sessions", json={"data_source": "replay", "recording_id": key})
        assert started.status_code == 200
        session = started.json()["session_id"]
        first = socket.receive_json()["data"]
        assert first["source"] == "replay"
        assert first["wrist_sample"]["acceleration_m_s2"] == pytest.approx(9.81)
        for _ in range(WINDOW - 1):
            last = socket.receive_json()["data"]
        assert last["analytics"]["replay_complete"]
        assert last["timestamp"] - first["timestamp"] == pytest.approx(3.98, abs=.001)
        assert last["analytics"]["trunk_peak_deg"] is None
        stats = last["analytics"]["wrist_features"]
        assert [stats[key] for key in FEATURES] == pytest.approx(features(raw))
        assert "latest_prediction" not in last["analytics"]
    saved = client.post(f"/api/sessions/{session}/finish", json={"pain_rating": 6})
    assert saved.status_code == 200
    data = saved.json()["session"]["movement_analytics"]
    assert data["pain_rating"] is None
    assert data["relative_excursion_deg"] is None
    assert data["recording"]["id"] == key
    assert len(data["wrist_trace"]) == 20
    assert client.get(f"/api/sessions/{session}").json()["movement_analytics"] == data
    progress = client.get("/api/analytics/rom?exercise_key=flexion").json()
    row = next(row for row in progress if row["session_id"] == session)
    assert row["data_source"] == "replay"
    assert row["duration_seconds"] == pytest.approx(WINDOW / FS)


def test_live_pain_baseline_stays_in_live_session_history(client):
    for pain in (6, 4):
        response = client.post("/api/sessions", json={"data_source": "live", "affected_side": "left"})
        sid = response.json()["session_id"]
        invalid = client.post(f"/api/sessions/{sid}/finish", json={"pain_rating": 12})
        assert invalid.status_code == 422
        saved = client.post(f"/api/sessions/{sid}/finish", json={"pain_rating": pain})
        analytics = saved.json()["session"]["movement_analytics"]
        assert analytics["pain_rating"] == pain
        if pain == 6:
            baseline = sid
            assert analytics["movement_baseline"] is None
    assert analytics["movement_baseline"] == {"session_id": baseline, "changes": {"pain_rating": -2}}


def test_replay_transport_controls_preserve_analysis_at_all_speeds(client, tmp_path, monkeypatch):
    import time
    from app.services.flexion.signal import FS, WINDOW

    monkeypatch.setenv("SPARS9X_RECORDINGS", str(tmp_path))
    monkeypatch.setattr(sensor_ingestion_service, "last_hardware_packet", None)
    key = "spars9x_s42_0"
    clock = np.arange(WINDOW + FS * 2) / FS
    theta = .8 * np.sin(2 * np.pi * clock / 1.5)
    raw = np.column_stack((9.81 * np.sin(theta), clock * 0, 9.81 * np.cos(theta),
                           clock * 0, np.gradient(theta) * FS, clock * 0))
    np.savez(tmp_path / f"{key}.npz", raw=raw, subject="spars9x_s42", start=0, side=2, label=8)
    started = client.post("/api/sessions", json={"data_source": "replay", "recording_id": key})
    sid = started.json()["session_id"]
    control = f"/api/sessions/{sid}/replay"
    active = "/api/monitoring/active"

    def wait_for(condition):
        deadline = time.monotonic() + 9
        while time.monotonic() < deadline:
            snapshot = client.get(active).json()
            if condition(snapshot):
                return snapshot
            time.sleep(.03)
        pytest.fail("Replay did not reach the expected state")

    wait_for(lambda state: state["analytics"]["samples_replayed"] >= 20)
    paused = client.post(f"{control}/pause").json()
    assert paused["status"] == "paused"
    time.sleep(.15)
    assert client.get(active).json()["analytics"]["samples_replayed"] == paused["analytics"]["samples_replayed"]
    assert client.post(f"{control}/speed?speed=2").json()["status"] == "paused"
    assert client.post(f"{control}/resume").json()["status"] == "playing"
    wait_for(lambda state: state["status"] == "complete")
    results = {}
    timings = {}
    for speed in (1, 2, 4):
        start = time.monotonic()
        reset = client.post(f"{control}/restart?speed={speed}").json()
        assert reset["elapsed_s"] == 0
        assert "decision_trace" not in reset["analytics"]
        assert reset["analytics"]["repetition_timeline"] == []
        snapshot = wait_for(lambda state: state["status"] == "complete")
        timings[speed] = time.monotonic() - start
        assert snapshot["elapsed_s"] == len(raw) / FS
        results[speed] = snapshot["analytics"]
    assert timings[4] < timings[2] < timings[1]
    for key in ("wrist_features", "repetition_timeline", "wrist_jerk_rms_m_s3"):
        assert results[1][key] == results[2][key] == results[4][key]
    assert not client.get("/api/dashboard/summary").json()["device_status"]["hardware_active"]
    saved = client.post(f"/api/sessions/{sid}/finish", json={}).json()["session"]["movement_analytics"]
    assert "decision_trace" not in saved
    assert saved["repetition_timeline"] == results[4]["repetition_timeline"]


def test_live_orientation_snapshot_and_hardware_status(client, monkeypatch):
    tracker = sensor_ingestion_service
    monkeypatch.setattr(tracker, "hardware_packets", 0)
    monkeypatch.setattr(tracker, "hardware_rejected", 0)
    packet = {
        "source": "live", "timestamp": 10,
        "sensors": {
            "chest": {"quaternion": {"x": 0, "y": 0, "z": 0, "w": 1}},
            "upper_arm": {"quaternion": {"x": 0, "y": np.sin(np.pi / 8), "z": 0, "w": np.cos(np.pi / 8)}},
        },
    }
    assert client.post("/api/sensor/ingest", json=packet).status_code == 200
    assert client.get("/api/monitoring/active").json() is None
    status = client.get("/api/sensor/status").json()
    assert status["receiving"] and status["valid_packets"] == 1 and status["has_orientation"]
    assert status["sensors"] == ["chest", "upper_arm"] and not status["has_wrist_vectors"]
    started = client.post("/api/sessions", json={"data_source": "live"})
    assert started.status_code == 200
    packet["timestamp"] += .02
    assert client.post("/api/sensor/ingest", json=packet).status_code == 200
    active = client.get("/api/monitoring/active").json()
    assert active["orientation"]["primary_angle"] == pytest.approx(45)
    assert active["orientation"]["quality_flag"] == "VALID"
    packet["timestamp"] += .02
    packet["sensors"]["upper_arm"].update(
        accelerometer={"x": 0, "y": 0, "z": 9.81},
        gyroscope={"x": 0, "y": 0, "z": 0},
    )
    assert client.post("/api/sensor/ingest", json=packet).status_code == 200
    assert client.get("/api/sensor/status").json()["has_wrist_vectors"]
    analytics = client.get("/api/monitoring/active").json()["analytics"]
    assert analytics["buffered_wrist_samples"] == 1
    client.post(f"/api/sessions/{started.json()['session_id']}/finish", json={})


@pytest.mark.parametrize("degrees", [60, 90, 120, 150])
@pytest.mark.parametrize("exercise,axis,other", [
    ("flexion", (0, -1, 0), "abduction"),
    ("abduction", (1, 0, 0), "flexion"),
])
def test_angle_elevation_does_not_fold_or_switch_planes(degrees, exercise, axis, other):
    from scipy.spatial.transform import Rotation

    chest = Rotation.from_euler("xyz", [22, 17, 51], degrees=True)
    mounting = Rotation.from_euler("xyz", [35, -19, 72], degrees=True)
    raise_motion = Rotation.from_rotvec(np.radians(degrees) * np.array(axis))
    calculator = ShoulderAngleCalculator()
    calculator.set_calibration_neutral(chest.as_quat(), (chest * mounting).as_quat())
    result = calculator.compute_angles(chest.as_quat(), (chest * raise_motion * mounting).as_quat(),
                                       timestamp=5, exercise_key=exercise)
    assert result["primary_angle"] == pytest.approx(degrees)
    assert result[other] == 0
    assert result["ext_rotation"] == result["int_rotation"] == 0


@pytest.mark.parametrize("side,sign", [("right", 1), ("left", -1)])
def test_functional_calibration_under_swapped_torso_axes(side, sign):
    from scipy.spatial.transform import Rotation
    from app.services.biomechanics.angle_calculator import calibrated_axes, motion_axis

    frame = Rotation.from_euler("z", 90, degrees=True)
    neutral = Rotation.from_euler("xyz", [10, 35, -45], degrees=True)
    forward = frame * Rotation.from_euler("y", -40, degrees=True) * frame.inv()
    sideways = frame * Rotation.from_euler("x", sign * 35, degrees=True) * frame.inv()
    calculator = ShoulderAngleCalculator(neutral.as_quat())
    calculator.motion_basis = calibrated_axes(
        motion_axis((forward * neutral).as_quat(), neutral.as_quat()),
        motion_axis((sideways * neutral).as_quat(), neutral.as_quat()), side,
    )
    result = calculator.compute_angles(Rotation.identity().as_quat(), (forward * neutral).as_quat(),
                                       timestamp=0, exercise_key="flexion", affected_side=side)
    assert result["primary_angle"] == 40
    assert result["abduction"] == 0


@pytest.mark.parametrize("degrees", [0, 30, 45, 60, 90, 120])
@pytest.mark.parametrize("exercise,axis", [("flexion", [0, -1, 0]), ("abduction", [1, 0, 0])])
def test_projected_raise_ignores_common_torso_rotation_and_axial_twist(degrees, exercise, axis):
    from scipy.spatial.transform import Rotation

    neutral_torso = Rotation.from_euler("xyz", [11, 23, -31], degrees=True)
    leaning_torso = Rotation.from_euler("xyz", [-55, 20, 43], degrees=True)
    mount = Rotation.from_euler("xyz", [21, -16, 82], degrees=True)
    raise_motion = Rotation.from_rotvec(np.radians(degrees) * np.array(axis))
    axial = Rotation.from_euler("z", 40, degrees=True)
    calculator = ShoulderAngleCalculator()
    calculator.set_calibration_neutral(neutral_torso.as_quat(), (neutral_torso * mount).as_quat())
    result = calculator.compute_angles(-1.12 * leaning_torso.as_quat(),
                                       1.36 * (leaning_torso * raise_motion * axial * mount).as_quat(),
                                       timestamp=1, exercise_key=exercise)
    assert result["primary_angle"] == pytest.approx(degrees, abs=.1)


def test_horizontal_projection_underreading_reproduction():
    from scipy.spatial.transform import Rotation

    bearing = np.pi / 6
    arm = Rotation.from_rotvec((np.pi / 2) * np.array([np.sin(bearing), -np.cos(bearing), 0.]))
    q = Rotation.identity().as_quat()
    result = ShoulderAngleCalculator().compute_angles(q, arm.as_quat(), timestamp=1)
    legacy = 90 * np.cos(bearing)
    assert legacy == pytest.approx(77.942, abs=.001)
    assert result["primary_angle"] == 90
    assert result["movement_plane"] == "mixed"
    assert result["off_plane"] is True


def test_shared_calibration_order_side_scope_exercise_switch_and_sync(client):
    from scipy.spatial.transform import Rotation

    url = "/api/devices/axis-test/calibrate"
    identity = Rotation.identity()
    counter = 0

    def send(rotation, skew=None):
        nonlocal counter
        counter += 1
        timestamp = counter * .1
        packet = {"timestamp": timestamp, "device_id": "axis-test", "source": "live", "sensors": {}}
        for index, (key, orientation) in enumerate((("chest", identity), ("wrist", rotation))):
            packet["sensors"][key] = {"quaternion": dict(zip("xyzw", orientation.as_quat()))}
            if skew is not None:
                packet["sensors"][key]["sample_timestamp"] = timestamp - index * skew
        return client.post("/api/sensor/ingest", json=packet).json()["sample"]

    send(identity)
    assert client.post(url).status_code == 200
    assert client.get("/api/sensor/status").json()["neutral_calibrated"]
    send(Rotation.from_euler("x", 40, degrees=True))
    assert client.post(f"{url}/axes/side").status_code == 200
    assert client.get("/api/sensor/status").json()["captured_poses"] == ["side"]
    assert client.post(f"{url}/axes/forward").status_code == 409
    send(Rotation.from_euler("y", -40, degrees=True))
    assert client.post(f"{url}/axes/forward").status_code == 200
    assert client.get("/api/sensor/status").json()["axes_calibrated"]
    assert not client.get("/api/sensor/status?side=left").json()["axes_calibrated"]

    for exercise, rotation in (("flexion", Rotation.from_euler("y", -90, degrees=True)),
                               ("abduction", Rotation.from_euler("x", 90, degrees=True))):
        sid = client.post("/api/sessions", json={"data_source": "live", "exercise_key": exercise}).json()["session_id"]
        sample = send(rotation, skew=.01)
        assert sample["primary_angle"] == 90
        assert client.get("/api/sensor/status").json()["diagnostic"]["sync"] == "within_tolerance"
        assert send(rotation, skew=.06)["quality_flag"] == "UNSYNCHRONIZED_ORIENTATION"
        assert client.get("/api/sensor/status").json()["diagnostic"]["sync"] == "out_of_sync"
        assert client.post(url).status_code == 409
        client.post(f"/api/sessions/{sid}/finish", json={})
    send(identity)
    assert client.post(url).status_code == 200
    assert client.get("/api/sensor/status").json()["captured_poses"] == []


@pytest.mark.parametrize("calibrate_planes", [False, True])
def test_live_small_mixed_raise_is_measured_and_counted(client, calibrate_planes):
    from scipy.spatial.transform import Rotation

    device = f"limited-motion-{calibrate_planes}"
    calibration = f"/api/devices/{device}/calibrate"
    index = 0
    previous_angle = 0

    def send(axis, angle, *, unsynchronized=False):
        nonlocal index, previous_angle
        index += 1
        wrist = Rotation.from_rotvec(np.radians(angle) * np.array(axis)).as_quat()
        payload = {"source": "live", "timestamp": index * .4, "device_id": device,
                   "sensors": {"chest": {"quaternion": dict(x=0, y=0, z=0, w=1)},
                               "wrist": {"quaternion": dict(zip("xyzw", wrist))}}}
        gyro = np.radians((angle - previous_angle) / .4)
        previous_angle = angle
        payload["sensors"]["wrist"].update(
            accelerometer=dict(x=0, y=0, z=9.81),
            gyroscope=dict(zip("xyz", gyro * np.array(axis))),
        )
        if unsynchronized:
            payload["sensors"]["chest"]["sample_timestamp"] = payload["timestamp"] - .06
            payload["sensors"]["wrist"]["sample_timestamp"] = payload["timestamp"]
        result = client.post("/api/sensor/ingest", json=payload)
        assert result.status_code == 200
        return result.json()["sample"]

    send([0, -1, 0], 0)
    assert client.post(calibration).status_code == 200
    if calibrate_planes:
        send([0, -1, 0], 25)
        assert client.post(calibration + "/axes/forward").status_code == 200
        send([1, 0, 0], 25)
        assert client.post(calibration + "/axes/side").status_code == 200

    session = client.post("/api/sessions", json={"data_source": "live", "rep_peak_deg": 10,
                        "prescribed_repetitions": 4, "prescribed_angle_deg": 25}).json()
    axis = [2 ** -.5, -2 ** -.5, 0]
    for angle in [0, 2, 6, 10, 13, 14, 13, 11, 9, 3, 0]:
        sample = send(axis, angle, unsynchronized=angle == 11)
        if angle == 11:
            assert sample["quality_flag"] == "UNSYNCHRONIZED_ORIENTATION"
        if angle == 14:
            assert sample["movement_angle_deg"] == 14
            assert sample["off_plane"]
    assert sample["repetitions"] == 1
    summary = client.get("/api/monitoring/active").json()["analytics"]
    assert summary["repetition_review"]["median_peak_deg"] is None
    for peak in (17, 20):
        for angle in (0, 6, 12, peak, 11, 3, 0):
            send(axis, angle)
    review = client.get("/api/monitoring/active").json()["analytics"]["repetition_review"]
    assert review["completed"] == 3
    assert review["median_peak_deg"] == 17
    assert review["median_duration_s"] > 0
    result = client.post(f"/api/sessions/{session['session_id']}/finish",
                         json={"pain_rating": 3, "stiffness_rating": 4}).json()
    metrics = result["session"]["movement_analytics"]
    assert metrics["estimated_repetition_count"] == 3
    assert metrics["repetition_review"] == review
    assert "rep_reference" not in metrics
    assert metrics["median_rep_excursion_deg"] == 17
    assert metrics["median_rep_peak_deg"] == 17
    assert metrics["prescribed_repetitions"] == 4
    assert metrics["prescribed_angle_deg"] == 25
    assert metrics["stiffness_rating"] == 4
    assert metrics["neutral_calibrated"]
    assert metrics["relative_excursion_deg"] == 20
    assert metrics["rep_peak_deg"] == 10
    assert metrics["movement_metric"] == ("total_tilt" if calibrate_planes else "neutral_rotation")


def test_live_adaptive_return_counts_partial_lowering_without_duplicates():
    from app.services.biomechanics.rep_counter import RepetitionCounter

    counter = RepetitionCounter(threshold_up=15, threshold_down=5.25)
    counter.adaptive_return = True
    samples = [0, 20, 60, 90, 65, 40, 30, 30, 31, 30, 45, 75, 100, 60, 34, 30]
    counts = [counter.process_sample(angle, index * .4)["repetitions"] for index, angle in enumerate(samples)]
    assert counts == [0] * 6 + [1] * 9 + [2]
    assert [rep["excursion_deg"] for rep in counter.completed_reps_info] == [90, 70]


def test_coarse_wrist_jerk_uses_elapsed_time_and_skips_uncovered_reps():
    from app.services.analytics.wrist_jerk import coarse_wrist_jerk

    times = [0, .55, 1.13, 2.28, 2.86, 3.42, 10., 10.6]
    trace = [{"time_s": t, "acceleration_m_s2": 9.81 + 2 * t} for t in times]
    reps = [{"start_s": 0, "end_s": 3.42}, {"start_s": 8, "end_s": 11}]
    assert coarse_wrist_jerk(trace, reps) == {
        "coarse_wrist_jerk_rms_m_s3": 2.,
        "coarse_wrist_jerk_covered_reps": 1,
        "coarse_wrist_jerk_coverage_s": 3.42,
    }
    assert coarse_wrist_jerk(trace, reps[1:]) == {}
