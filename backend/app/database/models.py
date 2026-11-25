import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.database.connection import Base
from app.services.analytics.wrist_jerk import coarse_wrist_jerk

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String(100), nullable=False)
    affected_side = Column(String(10), default="right")  # "left" or "right"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)
    
    sessions = relationship("RehabilitationSession", back_populates="patient", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String(64), primary_key=True, index=True)  # e.g., "esp32-shoulder-01"
    device_name = Column(String(100), nullable=False)
    device_type = Column(String(50), default="ESP32-BNO086")
    connection_method = Column(String(50), default="WiFi/HTTP-WS")
    last_seen_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False)
    ip_address = Column(String(45), nullable=True)
    calibration_offset = Column(Text, nullable=True)  # JSON-encoded reference neutral quaternion

class ExerciseConfiguration(Base):
    __tablename__ = "exercise_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    exercise_key = Column(String(50), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    target_movement = Column(String(100), nullable=False)
    primary_metric = Column(String(50), nullable=False)
    threshold_up = Column(Float, default=45.0)    # Deg to count ascending inflection
    threshold_down = Column(Float, default=15.0)  # Deg to count return to base
    min_rep_duration_sec = Column(Float, default=1.2)
    default_target_angle = Column(Float, default=90.0) # Clinician-defined reference target
    description = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)

class RehabilitationSession(Base):
    __tablename__ = "rehabilitation_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    exercise_key = Column(String(50), nullable=False, index=True)
    affected_side = Column(String(10), default="right")
    data_source = Column(String(20), nullable=False)  # "live" or "demo"
    status = Column(String(20), default="completed")  # "completed", "in_progress", "discarded"
    
    start_time = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0.0)
    
    # Biomechanical outcomes
    min_angle = Column(Float, default=0.0)
    max_angle = Column(Float, default=0.0)
    rom = Column(Float, default=0.0)
    repetitions = Column(Integer, default=0)
    
    # Consistency & Quality metrics (derived objectively)
    avg_rep_duration = Column(Float, nullable=True)
    rep_duration_variation = Column(Float, nullable=True)
    peak_angle_variation = Column(Float, nullable=True)
    smoothness_score = Column(Float, nullable=True)
    
    # ML Assessment metadata (if model configured)
    ml_predicted_class = Column(String(50), nullable=True)
    ml_confidence = Column(Float, nullable=True)
    ml_model_info = Column(String(100), nullable=True)
    
    notes = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)  # JSON-encoded array of warnings (e.g. glitches, stales)
    
    patient = relationship("Patient", back_populates="sessions")
    movement_record = relationship("SessionMovementAnalytics", uselist=False, cascade="all, delete-orphan")

    @property
    def movement_analytics(self):
        payload = self.movement_record.payload if self.movement_record else None
        if (self.data_source == "live" and payload and "coarse_wrist_jerk_rms_m_s3" not in payload
                and payload.get("wrist_trace") and payload.get("repetition_timeline")):
            return {**payload, **coarse_wrist_jerk(payload["wrist_trace"], payload["repetition_timeline"])}
        return payload

    samples = relationship("SensorSample", back_populates="session", cascade="all, delete-orphan")

class SensorSample(Base):
    __tablename__ = "sensor_samples"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("rehabilitation_sessions.id"), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    
    # Relative & Derived angles
    flexion_angle = Column(Float, nullable=False)
    abduction_angle = Column(Float, nullable=False)
    rotation_angle = Column(Float, nullable=True)
    angular_velocity = Column(Float, default=0.0)
    
    # Raw orientation storage for reference (optional sub-sampling)
    chest_qw = Column(Float, default=1.0)
    chest_qx = Column(Float, default=0.0)
    chest_qy = Column(Float, default=0.0)
    chest_qz = Column(Float, default=0.0)
    
    arm_qw = Column(Float, default=1.0)
    arm_qx = Column(Float, default=0.0)
    arm_qy = Column(Float, default=0.0)
    arm_qz = Column(Float, default=0.0)
    
    quality_flag = Column(String(30), default="VALID")
    
    session = relationship("RehabilitationSession", back_populates="samples")

class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    model_type = Column(String(50), nullable=False)  # "RandomForest", "SVM", "XGBoost"
    available_classes = Column(String(255), default="Normal,Restricted,Irregular")
    is_active = Column(Boolean, default=False)
    validation_status = Column(String(100), default="Unvalidated experimental candidate")
    trained_at = Column(DateTime, nullable=True)


class SessionMovementAnalytics(Base):
    __tablename__ = "session_movement_analytics"

    session_id = Column(Integer, ForeignKey("rehabilitation_sessions.id"), primary_key=True)
    payload = Column(JSON, nullable=False)
