from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Literal
import datetime
import json
import time
from statistics import median

from app.database.connection import get_db
from app.database.models import Patient, Device, ExerciseConfiguration, RehabilitationSession, SensorSample, SessionMovementAnalytics
from app.schemas.sensor import SensorPacket, ProcessedAngleOutput
from app.schemas.session import (
    StartSessionRequest,
    FinishSessionRequest,
    RehabilitationSessionResponse,
    SessionSummaryDTO,
    SessionSampleDTO
)
from app.schemas.device import DeviceStatusDTO, ConnectDeviceRequest, CalibrateRequest
from app.schemas.analytics import DashboardSummaryResponse, ROMProgressItem, WeeklyActivityItem
from app.services.sensor.ingestion import sensor_ingestion_service
from app.services.flexion.replay import catalog, load_recording
from app.services.flexion.signal import FS
from app.services.analytics.session_metrics import sampled_wrist_metrics
from app.services.analytics.dataset_reference import load as load_dataset_reference
from app.services.analytics.progress_service import ProgressAnalyticsService, same_movement_measure

router = APIRouter()

# ----------------- 1. HEALTH -----------------
@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "ShoulderSense Backend API",
        "timestamp": time.time(),
        "database": "connected",
        "sensor_mode": sensor_ingestion_service.mode,
        "is_monitoring": sensor_ingestion_service.is_monitoring
    }

# ----------------- 2. DASHBOARD SUMMARY -----------------
@router.get("/dashboard/summary", response_model=DashboardSummaryResponse, tags=["Dashboard"])
def get_dashboard_summary(patient_id: int = 1, db: Session = Depends(get_db)):
    summary = ProgressAnalyticsService.get_dashboard_summary(db=db, patient_id=patient_id)
    diag = sensor_ingestion_service.get_diagnostic_status()
    summary["device_status"] = diag
    return summary

# ----------------- 3. DEVICES -----------------
@router.get("/devices", tags=["Device Management"])
def list_devices(db: Session = Depends(get_db)):
    devices = db.query(Device).all()
    diag = sensor_ingestion_service.get_diagnostic_status()
    return [{
        "id": d.id,
        "name": d.device_name,
        "type": d.device_type,
        "connection_method": d.connection_method,
        "is_active": diag["hardware_active"] if d.id == diag["device_id"] else d.is_active,
        "last_seen_at": d.last_seen_at,
        "diagnostics": diag
    } for d in devices]

@router.get("/devices/{device_id}", tags=["Device Management"])
def get_device(device_id: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    diag = sensor_ingestion_service.get_diagnostic_status()
    return {
        "id": dev.id,
        "name": dev.device_name,
        "type": dev.device_type,
        "connection_method": dev.connection_method,
        "is_active": diag["hardware_active"],
        "diagnostics": diag
    }

@router.post("/devices/{device_id}/connect", tags=["Device Management"])
def connect_device(device_id: str, req: ConnectDeviceRequest, db: Session = Depends(get_db)):
    try:
        dev = db.query(Device).filter(Device.id == device_id).first()
        if not dev:
            dev = Device(
                id=device_id,
                device_name="ShoulderSense ESP32 IMU Hub",
                device_type="ESP32-BNO086 Dual-IMU",
                connection_method="WiFi/HTTP-WS"
            )
            db.add(dev)
        
        mode_clean = str(req.mode).lower().strip()
        if "live" in mode_clean:
            mode_clean = "live"
        else:
            mode_clean = "demo"

        sensor_ingestion_service.set_mode(mode_clean)
        dev.is_active = True
        dev.last_seen_at = datetime.datetime.now(datetime.timezone.utc)
        if req.ip_address:
            dev.ip_address = req.ip_address
        db.commit()
        
        return {
            "status": "connected",
            "device_id": device_id,
            "mode": mode_clean,
            "timestamp": time.time(),
            "message": f"Device configured in {mode_clean.upper()} mode."
        }
    except Exception as e:
        # Graceful fallback: always succeed in switching in-memory sensor ingestion mode
        mode_clean = "live" if "live" in str(req.mode).lower() else "demo"
        sensor_ingestion_service.set_mode(mode_clean)
        return {
            "status": "connected",
            "device_id": device_id,
            "mode": mode_clean,
            "timestamp": time.time(),
            "message": f"Device configured in {mode_clean.upper()} mode."
        }

@router.post("/devices/{device_id}/disconnect", tags=["Device Management"])
async def disconnect_device(device_id: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if dev:
        dev.is_active = False
        db.commit()
    sensor_ingestion_service.last_hardware_packet = None
    if sensor_ingestion_service.session_source == "live":
        sensor_ingestion_service.stop_monitoring()
    return {"status": "disconnected", "device_id": device_id}

@router.post("/devices/{device_id}/calibrate", tags=["Device Management"])
async def calibrate_neutral(device_id: str):
    if not sensor_ingestion_service.calibrate_neutral(device_id):
        raise HTTPException(
            status_code=409,
            detail="Neutral calibration requires a recent paired orientation sample before starting a session.",
        )
    return {
        "status": "calibrated",
        "device_id": device_id,
        "message": "Neutral reference captured for this sensor pair.",
        "timestamp": time.time(),
    }

@router.post("/devices/{device_id}/calibrate/axes/{pose}", tags=["Device Management"])
async def calibrate_axes(device_id: str, pose: Literal["forward", "side"], side: Literal["left", "right"] = "right"):
    try:
        sensor_ingestion_service.capture_motion_axis(device_id, pose, side)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "captured", "pose": pose, "side": side}


# ----------------- 4. SENSOR INGESTION (ESP32) -----------------
@router.get("/sensor/status", tags=["Sensor Ingestion"])
async def sensor_status(side: Literal["left", "right"] = "right"):
    return sensor_ingestion_service.hardware_status(side)


@router.post("/sensor/ingest", tags=["Sensor Ingestion"])
async def ingest_sensor_data(packet: SensorPacket):
    """
    Receives raw sensor packets from ESP32 wearable hardware over HTTP POST.
    Validates components, computes relative quaternion, derives angles,
    updates repetition state, and broadcasts over live WebSocket.
    """
    processed = sensor_ingestion_service.process_packet(packet.model_dump())
    if not processed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expected valid wrist vectors or paired chest and limb orientation for the current sensor source."
        )
    return {"status": "accepted", "sample": processed}

# ----------------- 5. EXERCISE LIBRARY -----------------
@router.get("/exercises", tags=["Exercises"])
def list_exercises(db: Session = Depends(get_db)):
    return db.query(ExerciseConfiguration).all()

@router.get("/exercises/{exercise_key}", tags=["Exercises"])
def get_exercise_details(exercise_key: str, db: Session = Depends(get_db)):
    ex = db.query(ExerciseConfiguration).filter(ExerciseConfiguration.exercise_key == exercise_key).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex

# ----------------- 6. REHABILITATION SESSIONS -----------------
@router.get("/sessions", response_model=List[RehabilitationSessionResponse], tags=["Sessions"])
def list_sessions(
    patient_id: int = 1,
    exercise_key: Optional[str] = None,
    data_source: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(RehabilitationSession).filter(RehabilitationSession.patient_id == patient_id)
    if exercise_key and exercise_key != "all":
        query = query.filter(RehabilitationSession.exercise_key == exercise_key)
    if data_source and data_source != "all":
        query = query.filter(RehabilitationSession.data_source == data_source)
    return query.order_by(RehabilitationSession.start_time.desc()).all()

@router.get("/replay/recordings", tags=["Replay"])
def list_replay_recordings():
    return catalog()


@router.get("/participants", tags=["Sessions"])
def list_participants(db: Session = Depends(get_db)):
    return [{"id": patient.id, "name": patient.display_name, "affected_side": patient.affected_side}
            for patient in db.query(Patient).order_by(Patient.id).all()]


@router.get("/monitoring/active", tags=["Sessions"])
async def active_monitoring(db: Session = Depends(get_db)):
    snapshot = sensor_ingestion_service.monitoring_snapshot()
    if snapshot:
        session = db.get(RehabilitationSession, snapshot["session_id"])
        snapshot["patient_id"] = session.patient_id if session else None
    return snapshot


@router.post("/sessions/{session_id}/replay/{action}", tags=["Replay"])
async def control_replay(session_id: int, action: Literal["pause", "resume", "restart", "speed"],
                         speed: Literal["1", "2", "4"] | None = None):
    tracker = sensor_ingestion_service
    if tracker.active_session_id != session_id or tracker.replay_metadata is None or not tracker.is_monitoring:
        raise HTTPException(status_code=409, detail="This replay is no longer active.")
    if action == "speed" and speed is None:
        raise HTTPException(status_code=422, detail="Select a playback speed.")
    tracker.control_replay(action, int(speed) if speed else None)
    return tracker.monitoring_snapshot()


@router.post("/sessions", tags=["Sessions"])
async def start_rehabilitation_session(req: StartSessionRequest, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if sensor_ingestion_service.active_session_id is not None:
        raise HTTPException(status_code=409, detail="Finish or discard the active session first.")

    replay = None
    exercise = req.exercise_key
    affected_side = req.affected_side
    if req.data_source == "replay":
        if not req.recording_id:
            raise HTTPException(status_code=422, detail="Select a SPARS9x recording.")
        try:
            replay = load_recording(req.recording_id, samples=True)
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=404, detail="SPARS9x recording unavailable.") from exc
        exercise = replay[0]["exercise_key"]
        affected_side = f"code_{replay[0]['side_code']}"
    elif not db.query(ExerciseConfiguration).filter_by(exercise_key=exercise).first():
        raise HTTPException(status_code=404, detail="Exercise not found.")

    new_session = RehabilitationSession(
        patient_id=req.patient_id,
        exercise_key=exercise,
        affected_side=affected_side,
        data_source=req.data_source,
        status="in_progress",
        start_time=datetime.datetime.utcnow(),
        duration_seconds=0.0
    )
    if req.data_source == "live":
        prescription = {key: value for key, value in req.model_dump(
            include={"prescribed_repetitions", "prescribed_angle_deg"}).items() if value is not None}
        if prescription:
            new_session.movement_record = SessionMovementAnalytics(payload=prescription)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # Configure ingestion service
    sensor_ingestion_service.set_mode(req.data_source)
    sensor_ingestion_service.set_exercise(exercise, affected_side)
    if req.data_source == "live" and req.rep_peak_deg is not None:
        sensor_ingestion_service.rep_counter.threshold_up = req.rep_peak_deg
        sensor_ingestion_service.rep_counter.threshold_down = req.rep_peak_deg * .35
    sensor_ingestion_service.start_monitoring(session_id=new_session.id, replay=replay, playback_speed=req.playback_speed)

    return {
        "status": "started",
        "session_id": new_session.id,
        "exercise_key": req.exercise_key,
        "affected_side": req.affected_side,
        "data_source": req.data_source,
        "start_time": new_session.start_time.isoformat()
    }

@router.get("/sessions/{session_id}", response_model=RehabilitationSessionResponse, tags=["Sessions"])
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s

@router.post("/sessions/{session_id}/finish", response_model=SessionSummaryDTO, tags=["Sessions"])
async def finish_rehabilitation_session(
    session_id: int,
    req: FinishSessionRequest,
    db: Session = Depends(get_db)
):
    session = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "completed":
        if session.id != sensor_ingestion_service.active_session_id:
            raise HTTPException(status_code=409, detail="This session is not active.")
        sensor_ingestion_service.stop_monitoring()

        # Extract consistency metrics from RepetitionCounter
        consistency = sensor_ingestion_service.rep_counter.compute_movement_consistency()
    
        end_dt = datetime.datetime.utcnow()
        duration = (end_dt - session.start_time).total_seconds()
        if duration <= 0:
            duration = 1.0

        session.end_time = end_dt
        session.duration_seconds = round(duration, 1)
        session.min_angle = round(sensor_ingestion_service.rep_counter.session_min_angle if sensor_ingestion_service.rep_counter.session_min_angle < 900 else 0.0, 1)
        session.max_angle = round(sensor_ingestion_service.rep_counter.session_max_angle, 1)
        session.rom = round(max(0.0, session.max_angle - session.min_angle), 1)
        session.repetitions = sensor_ingestion_service.rep_counter.rep_count
    
        session.avg_rep_duration = consistency["avg_rep_duration"] if consistency["total_reps"] else None
        session.rep_duration_variation = consistency["rep_duration_variation"] if consistency["total_reps"] >= 2 else None
        session.peak_angle_variation = consistency["peak_angle_variation"] if consistency["total_reps"] >= 2 else None
        session.status = "completed"
        session.notes = req.notes

        tracker = sensor_ingestion_service
        has_angle = tracker.orientation_kind is not None
        reps = tracker.rep_counter.completed_reps_info
        if tracker.replay_metadata is not None:
            tracker.update_replay_cycles()
        analytics = {
            **tracker.wrist.summary(include_scores=True),
            "angle_source": tracker.orientation_kind,
            "movement_metric": tracker.movement_metric,
            "rep_peak_deg": tracker.rep_counter.threshold_up if tracker.movement_metric else None,
            "relative_excursion_deg": session.rom if has_angle else None,
            "trunk_peak_deg": tracker.trunk_peak,
            "estimated_repetition_count": session.repetitions if has_angle else None,
            "movement_duration_s": round(sum(rep["duration"] for rep in reps), 2) if reps else None,
            "rep_duration_sd_s": consistency["rep_duration_variation"] if len(reps) >= 2 else None,
            "peak_angle_sd_deg": consistency["peak_angle_variation"] if len(reps) >= 2 else None,
            "pain_rating": req.pain_rating if session.data_source == "live" else None,
            **tracker.replay_metrics(),
            **tracker.repetition_review(),
            **tracker.coarse_jerk_metrics(),
            "wrist_trace": tracker.wrist_trace if req.save_samples else [],
            "repetition_timeline": tracker.repetition_timeline(),
        }
        if session.data_source == "live":
            analytics.update(session.movement_record.payload if session.movement_record else {})
            analytics.update(
                stiffness_rating=req.stiffness_rating,
                median_rep_excursion_deg=round(median(rep["excursion_deg"] for rep in reps), 1) if reps else None,
                median_rep_peak_deg=round(median(rep["peak_angle"] for rep in reps), 1) if reps else None,
                mean_rep_duration_s=session.avg_rep_duration,
                rep_count_protocol="adaptive-return-v1" if tracker.rep_counter.adaptive_return else "fixed-return-v1",
                sensor_device_id=tracker.session_device,
                neutral_calibrated=(tracker.session_device, tracker.orientation_kind, "live") in tracker.calibrations,
            )
            analytics.update(sampled_wrist_metrics(tracker.wrist_trace, analytics["repetition_timeline"]))
        if session.data_source == "replay":
            session.repetitions = analytics["estimated_repetition_count"] or 0
            session.duration_seconds = round(tracker.replay_position / FS, 2)
            session.rep_duration_variation = analytics["rep_duration_sd_s"]
            if session.repetitions:
                session.avg_rep_duration = analytics["movement_duration_s"] / session.repetitions
        analytics["source"] = session.data_source
        analytics["movement_baseline"] = None
        if session.data_source == "live":
            baseline = (db.query(RehabilitationSession)
                        .filter_by(patient_id=session.patient_id, exercise_key=session.exercise_key,
                                   affected_side=session.affected_side, data_source="live", status="completed")
                        .filter(RehabilitationSession.id < session.id)
                        .order_by(RehabilitationSession.start_time).all())
            for earlier in baseline:
                measurements = earlier.movement_analytics or {}
                differences = {}
                for metric in ("estimated_repetition_count", "movement_duration_s", "rep_duration_sd_s",
                               "wrist_gyro_peak_rad_s", "wrist_jerk_rms_m_s3", "pain_rating"):
                    if (analytics.get(metric) is not None and measurements.get(metric) is not None
                            and (metric not in {"estimated_repetition_count", "movement_duration_s", "rep_duration_sd_s"}
                                 or same_movement_measure(analytics, measurements, count=True))):
                        differences[metric] = round(analytics[metric] - measurements[metric], 4)
                if same_movement_measure(analytics, measurements):
                    differences["relative_excursion_deg"] = round(
                        analytics["relative_excursion_deg"] - measurements["relative_excursion_deg"], 2)
                if differences:
                    analytics["movement_baseline"] = {"session_id": earlier.id, "changes": differences}
                    break
        if session.movement_record:
            session.movement_record.payload = analytics
        else:
            session.movement_record = SessionMovementAnalytics(payload=analytics)
        session.smoothness_score = None

        # The legacy detail chart stores usable angle samples only.
        samples_to_save = [row for row in tracker.recent_samples if row["quality_flag"] == "VALID"]
        if req.save_samples and samples_to_save:
            step = max(1, (len(samples_to_save) + 99) // 100)
            for s_data in samples_to_save[::step]:
                sample_rec = SensorSample(
                    session_id=session.id,
                    timestamp=s_data["timestamp"],
                    flexion_angle=s_data["flexion_angle"],
                    abduction_angle=s_data["abduction_angle"],
                    rotation_angle=s_data.get("rotation_angle"),
                    angular_velocity=s_data["angular_velocity"],
                    quality_flag=s_data.get("quality_flag", "VALID")
                )
                db.add(sample_rec)

        db.commit()
        sensor_ingestion_service.active_session_id = None
        db.refresh(session)

    # Calculate comparison with prior session
    prior_session = (
        db.query(RehabilitationSession)
        .filter(
            RehabilitationSession.patient_id == session.patient_id,
            RehabilitationSession.exercise_key == session.exercise_key,
            RehabilitationSession.id < session.id,
            RehabilitationSession.data_source == session.data_source,
            RehabilitationSession.affected_side == session.affected_side,
            RehabilitationSession.status == "completed"
        )
        .order_by(RehabilitationSession.start_time.desc())
        .first()
    )

    imp = None
    prior_id = None
    changes = {}
    if prior_session and session.data_source != "replay":
        prior_id = prior_session.id
        current = session.movement_analytics or {}
        previous = prior_session.movement_analytics or {}
        if same_movement_measure(current, previous):
            imp = round(session.rom - prior_session.rom, 1)
        for key in ("movement_duration_s", "rep_duration_sd_s", "wrist_gyro_peak_rad_s", "wrist_jerk_rms_m_s3"):
            if (current.get(key) is not None and previous.get(key) is not None
                    and (key not in {"movement_duration_s", "rep_duration_sd_s"}
                         or same_movement_measure(current, previous, count=True))):
                changes[key] = round(current[key] - previous[key], 4)

    ex = db.query(ExerciseConfiguration).filter(ExerciseConfiguration.exercise_key == session.exercise_key).first()
    ex_name = ((session.movement_analytics or {}).get("recording") or {}).get("exercise_name")
    ex_name = ex_name or (ex.display_name if ex else session.exercise_key)

    return SessionSummaryDTO(
        session=session,
        exercise_name=ex_name,
        improvement_vs_previous_rom=imp,
        previous_session_id=prior_id,
        movement_changes=changes or None
    )

@router.delete("/sessions/{session_id}", tags=["Sessions"])
async def discard_rehabilitation_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if sensor_ingestion_service.active_session_id == session.id:
        sensor_ingestion_service.stop_monitoring()
    db.delete(session)
    db.commit()
    if sensor_ingestion_service.active_session_id == session_id:
        sensor_ingestion_service.active_session_id = None
    return {"status": "discarded", "session_id": session_id, "message": "Session discarded without persisting."}

@router.get("/sessions/{session_id}/samples", tags=["Sessions"])
def get_session_samples(session_id: int, db: Session = Depends(get_db)):
    samples = (
        db.query(SensorSample)
        .filter(SensorSample.session_id == session_id)
        .order_by(SensorSample.timestamp.asc())
        .all()
    )
    return [{
        "timestamp": s.timestamp,
        "flexion_angle": s.flexion_angle,
        "abduction_angle": s.abduction_angle,
        "rotation_angle": s.rotation_angle,
        "angular_velocity": s.angular_velocity,
        "quality_flag": s.quality_flag
    } for s in samples]

# ----------------- 7. ANALYTICS & REPORTS -----------------
@router.get("/analytics/rom", response_model=List[ROMProgressItem], tags=["Analytics"])
def get_rom_analytics(
    patient_id: int = 1,
    exercise_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return ProgressAnalyticsService.get_rom_analytics(
        db=db,
        patient_id=patient_id,
        exercise_key=exercise_key
    )

@router.get("/analytics/dataset-reference", tags=["Analytics"])
def get_dataset_reference():
    return load_dataset_reference()


@router.get("/analytics/weekly", response_model=List[WeeklyActivityItem], tags=["Analytics"])
def get_weekly_analytics(patient_id: int = 1, db: Session = Depends(get_db)):
    return ProgressAnalyticsService.get_weekly_activity(db=db, patient_id=patient_id)

@router.get("/analytics/compare", tags=["Analytics"])
def compare_two_sessions(
    session_a: int = Query(..., description="ID of baseline session"),
    session_b: int = Query(..., description="ID of follow-up session"),
    db: Session = Depends(get_db)
):
    try:
        return ProgressAnalyticsService.compare_sessions(db, session_a, session_b)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/reports/sessions/{session_id}", tags=["Reports"])
def generate_physiotherapy_report(session_id: int, db: Session = Depends(get_db)):
    session = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
    exercise = db.query(ExerciseConfiguration).filter(ExerciseConfiguration.exercise_key == session.exercise_key).first()

    # Compare with prior session of the same exercise
    prior_session = (
        db.query(RehabilitationSession)
        .filter(
            RehabilitationSession.patient_id == session.patient_id,
            RehabilitationSession.exercise_key == session.exercise_key,
            RehabilitationSession.id < session.id,
            RehabilitationSession.affected_side == session.affected_side,
            RehabilitationSession.data_source == session.data_source,
            RehabilitationSession.status == "completed"
        )
        .order_by(RehabilitationSession.start_time.desc())
        .first()
    )

    analytics = session.movement_analytics or {}
    previous = (prior_session.movement_analytics or {}) if prior_session else {}
    angle_source = analytics.get("angle_source")
    rom_change = round(session.rom - prior_session.rom, 1) if same_movement_measure(analytics, previous) else None
    if angle_source:
        narrative = (
            f"The repetition counter estimated {session.repetitions} repetitions. "
            f"Chest-relative {angle_source.replace('_', ' ')} excursion was {session.rom}°."
        )
        if rom_change is not None:
            narrative += f" Excursion changed by {rom_change:+.1f}° since the prior comparable session."
    else:
        narrative = "A chest-relative excursion and repetition estimate are unavailable for this session."
    if session.data_source == "demo":
        narrative = "Synthetic demo session. " + narrative
    elif session.data_source == "replay":
        cycles = analytics.get("estimated_repetition_count")
        narrative = "SPARS9x wrist-only replay. " + narrative
        if cycles is not None:
            narrative += f" The wrist signal supported an exploratory estimate of {cycles} cycles."

    return {
        "report_id": f"REP-{session.id:04d}",
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "patient": {
            "id": patient.id if patient else 1,
            "display_name": patient.display_name if patient else "Participant P-101",
            "affected_side": session.affected_side,
            "notes": patient.notes if patient else ""
        },
        "session": {
            "id": session.id,
            "date": session.start_time.strftime("%A, %B %d, %Y at %H:%M"),
            "data_source": session.data_source,
            "exercise_name": exercise.display_name if exercise else session.exercise_key,
            "exercise_category": exercise.category if exercise else "",
            "duration_seconds": session.duration_seconds,
            "repetitions": session.repetitions,
            "min_angle": session.min_angle,
            "max_angle": session.max_angle,
            "rom": session.rom,
            "rom_change_vs_prior": rom_change,
            "avg_rep_duration": session.avg_rep_duration,
            "rep_duration_variation": session.rep_duration_variation,
            "peak_angle_variation": session.peak_angle_variation,
            "smoothness_score": session.smoothness_score,
            "notes": session.notes,
            "warnings": session.warnings or "[]"
        },
        "movement_analytics": session.movement_analytics,
        "rule_based_demonstration": None,
        "clinical_summary": narrative,
        "disclaimer": "This report is generated by an academic monitoring system (ShoulderSense) for movement visualization. It does NOT provide a medical diagnosis and does NOT replace a qualified physiotherapist or physician."
    }
