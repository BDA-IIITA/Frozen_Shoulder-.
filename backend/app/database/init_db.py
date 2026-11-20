import json
from app.database.connection import engine, Base, SessionLocal
from app.database.models import Patient, Device, ExerciseConfiguration, ModelMetadata, RehabilitationSession
import datetime

DEFAULT_EXERCISES = [
    {
        "exercise_key": "flexion",
        "display_name": "Shoulder Forward Flexion",
        "category": "Sagittal Plane Elevation",
        "target_movement": "Lifting arm forward and upward in front of body",
        "primary_metric": "Flexion Angle (°)",
        "threshold_up": 45.0,
        "threshold_down": 20.0,
        "min_rep_duration_sec": 1.2,
        "default_target_angle": 90.0,
        "description": "Forward elevation of the arm in the sagittal plane. Essential for reaching overhead and functional daily tasks.",
        "instructions": "Stand or sit upright with torso stable. Keep elbow straight and thumb pointing upwards. Smoothly raise your affected arm directly in front of you as far as comfortable without arching your back, pause momentarily at top, then lower under control."
    },
    {
        "exercise_key": "abduction",
        "display_name": "Shoulder Abduction",
        "category": "Coronal Plane Elevation",
        "target_movement": "Lifting arm sideways away from body",
        "primary_metric": "Abduction Angle (°)",
        "threshold_up": 40.0,
        "threshold_down": 18.0,
        "min_rep_duration_sec": 1.2,
        "default_target_angle": 85.0,
        "description": "Lateral elevation in the coronal plane. Frequently restricted in adhesive capsulitis due to inferior glenohumeral ligament tightness.",
        "instructions": "Stand tall facing forward. Keep your palm facing inward or slightly forward. Raise your arm outward to the side in a smooth arc. Stop at the point of firm resistance or pain. Lower slowly back to your side."
    },
    {
        "exercise_key": "external_rotation",
        "display_name": "External Shoulder Rotation",
        "category": "Transverse Rotation",
        "target_movement": "Rotating arm outward with elbow bent at 90°",
        "primary_metric": "External Rotation (°)",
        "threshold_up": 25.0,
        "threshold_down": 10.0,
        "min_rep_duration_sec": 1.0,
        "default_target_angle": 45.0,
        "description": "Outward rotation of the humerus. This is characteristically the most restricted movement in early and frozen stages of adhesive capsulitis.",
        "instructions": "Keep elbow pinned close to your waist bent at 90 degrees. Rotate your forearm outward away from your abdomen while keeping your upper arm still. Hold briefly, then return gently to start."
    },
    {
        "exercise_key": "internal_rotation",
        "display_name": "Internal Shoulder Rotation",
        "category": "Transverse Rotation",
        "target_movement": "Rotating arm inward toward abdomen with elbow bent",
        "primary_metric": "Internal Rotation (°)",
        "threshold_up": 25.0,
        "threshold_down": 10.0,
        "min_rep_duration_sec": 1.0,
        "default_target_angle": 50.0,
        "description": "Inward rotation of the humerus toward the torso.",
        "instructions": "Start with elbow at 90 degrees at your side. Rotate your forearm inward across your belly. Return smoothly to the starting position."
    }
]

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if default patient exists
        patient = db.query(Patient).first()
        if not patient:
            patient = Patient(
                id=1,
                display_name="Participant P-101",
                affected_side="right",
                notes="Adhesive Capsulitis (Freezing phase, right shoulder). Participating in academic monitoring protocol."
            )
            db.add(patient)
            db.commit()
            
        # Check devices
        device = db.query(Device).filter(Device.id == "esp32-shoulder-01").first()
        if not device:
            device = Device(
                id="esp32-shoulder-01",
                device_name="ShoulderSense ESP32-WROOM-32 IMU Hub",
                device_type="ESP32-BNO086 Dual-IMU",
                connection_method="WiFi/HTTP-WS",
                is_active=False
            )
            db.add(device)
            db.commit()
            
        # Check exercises
        for ex_data in DEFAULT_EXERCISES:
            existing = db.query(ExerciseConfiguration).filter(
                ExerciseConfiguration.exercise_key == ex_data["exercise_key"]
            ).first()
            if not existing:
                ex = ExerciseConfiguration(**ex_data)
                db.add(ex)
        db.commit()

        # Seed sample baseline demo sessions if empty so Overview & Analytics are immediately informative and testable
        existing_sessions = db.query(RehabilitationSession).count()
        if existing_sessions == 0:
            base_date = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            demo_historical = [
                {
                    "patient_id": 1,
                    "exercise_key": "flexion",
                    "affected_side": "right",
                    "data_source": "demo",
                    "status": "completed",
                    "start_time": base_date + datetime.timedelta(days=0, hours=10),
                    "end_time": base_date + datetime.timedelta(days=0, hours=10, minutes=4),
                    "duration_seconds": 240.0,
                    "min_angle": 12.0,
                    "max_angle": 68.5,
                    "rom": 56.5,
                    "repetitions": 8,
                    "avg_rep_duration": 4.1,
                    "rep_duration_variation": 0.42,
                    "peak_angle_variation": 2.8,
                    "smoothness_score": 78.5,
                    "notes": "Baseline session recorded in demo mode for calibration verification.",
                    "warnings": "[]"
                },
                {
                    "patient_id": 1,
                    "exercise_key": "flexion",
                    "affected_side": "right",
                    "data_source": "demo",
                    "status": "completed",
                    "start_time": base_date + datetime.timedelta(days=2, hours=11),
                    "end_time": base_date + datetime.timedelta(days=2, hours=11, minutes=5),
                    "duration_seconds": 280.0,
                    "min_angle": 10.5,
                    "max_angle": 74.0,
                    "rom": 63.5,
                    "repetitions": 10,
                    "avg_rep_duration": 3.9,
                    "rep_duration_variation": 0.38,
                    "peak_angle_variation": 2.2,
                    "smoothness_score": 82.0,
                    "notes": "Second session: steady progression in forward flexion elevation.",
                    "warnings": "[]"
                },
                {
                    "patient_id": 1,
                    "exercise_key": "flexion",
                    "affected_side": "right",
                    "data_source": "demo",
                    "status": "completed",
                    "start_time": base_date + datetime.timedelta(days=5, hours=9),
                    "end_time": base_date + datetime.timedelta(days=5, hours=9, minutes=6),
                    "duration_seconds": 330.0,
                    "min_angle": 9.8,
                    "max_angle": 81.2,
                    "rom": 71.4,
                    "repetitions": 12,
                    "avg_rep_duration": 3.8,
                    "rep_duration_variation": 0.31,
                    "peak_angle_variation": 1.9,
                    "smoothness_score": 86.4,
                    "notes": "Third session: noticeable increase in peak elevation angle.",
                    "warnings": "[]"
                },
                {
                    "patient_id": 1,
                    "exercise_key": "abduction",
                    "affected_side": "right",
                    "data_source": "demo",
                    "status": "completed",
                    "start_time": base_date + datetime.timedelta(days=1, hours=15),
                    "end_time": base_date + datetime.timedelta(days=1, hours=15, minutes=4),
                    "duration_seconds": 230.0,
                    "min_angle": 14.0,
                    "max_angle": 58.0,
                    "rom": 44.0,
                    "repetitions": 8,
                    "avg_rep_duration": 4.5,
                    "rep_duration_variation": 0.51,
                    "peak_angle_variation": 3.4,
                    "smoothness_score": 74.0,
                    "notes": "Lateral abduction baseline.",
                    "warnings": "[]"
                },
                {
                    "patient_id": 1,
                    "exercise_key": "abduction",
                    "affected_side": "right",
                    "data_source": "demo",
                    "status": "completed",
                    "start_time": base_date + datetime.timedelta(days=4, hours=16),
                    "end_time": base_date + datetime.timedelta(days=4, hours=16, minutes=5),
                    "duration_seconds": 290.0,
                    "min_angle": 12.2,
                    "max_angle": 67.5,
                    "rom": 55.3,
                    "repetitions": 10,
                    "avg_rep_duration": 4.2,
                    "rep_duration_variation": 0.40,
                    "peak_angle_variation": 2.5,
                    "smoothness_score": 79.5,
                    "notes": "Progressing lateral reach without shoulder shrug.",
                    "warnings": "[]"
                }
            ]
            for s in demo_historical:
                db.add(RehabilitationSession(**s))
            db.commit()

        # Check candidate ML model metadata entry
        model_meta = db.query(ModelMetadata).first()
        if not model_meta:
            meta = ModelMetadata(
                model_name="FrozenShoulder-MovementQuality-Candidate",
                version="v0.1-candidate",
                model_type="RandomForest",
                available_classes="Normal,Restricted,Irregular",
                is_active=False,
                validation_status="Pending clinical cohort data collection - unvalidated prototype"
            )
            db.add(meta)
            db.commit()
    finally:
        db.close()
