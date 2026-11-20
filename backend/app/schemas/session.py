from pydantic import BaseModel, Field
from typing import Optional, List
import datetime

class StartSessionRequest(BaseModel):
    patient_id: int = 1
    exercise_key: str = "flexion"
    affected_side: str = "right"
    data_source: str = Field("demo", description="'demo' or 'live'")

class FinishSessionRequest(BaseModel):
    notes: Optional[str] = None
    save_samples: bool = True

class SessionSampleDTO(BaseModel):
    timestamp: float
    flexion_angle: float
    abduction_angle: float
    rotation_angle: Optional[float] = None
    angular_velocity: float
    quality_flag: str

class RehabilitationSessionResponse(BaseModel):
    id: int
    patient_id: int
    exercise_key: str
    affected_side: str
    data_source: str
    status: str
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None
    duration_seconds: float
    min_angle: float
    max_angle: float
    rom: float
    repetitions: int
    avg_rep_duration: Optional[float] = None
    rep_duration_variation: Optional[float] = None
    peak_angle_variation: Optional[float] = None
    smoothness_score: Optional[float] = None
    ml_predicted_class: Optional[str] = None
    ml_confidence: Optional[float] = None
    ml_model_info: Optional[str] = None
    notes: Optional[str] = None
    warnings: Optional[str] = None

    class Config:
        from_attributes = True

class SessionSummaryDTO(BaseModel):
    session: RehabilitationSessionResponse
    exercise_name: str
    improvement_vs_previous_rom: Optional[float] = None
    previous_session_id: Optional[int] = None
