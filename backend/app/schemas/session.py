from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal, Optional
import datetime

class StartSessionRequest(BaseModel):
    patient_id: int = 1
    exercise_key: str = "flexion"
    affected_side: Literal["left", "right"] = "right"
    data_source: Literal["demo", "live", "replay"] = "demo"
    recording_id: str | None = None
    rep_peak_deg: float | None = Field(None, ge=5, le=120, allow_inf_nan=False)
    prescribed_repetitions: int | None = Field(None, ge=1, le=500)
    prescribed_angle_deg: float | None = Field(None, gt=0, le=180, allow_inf_nan=False)
    playback_speed: Literal[1, 2, 4] = 1

class FinishSessionRequest(BaseModel):
    notes: Optional[str] = None
    save_samples: bool = True
    pain_rating: int | None = Field(None, ge=0, le=10)
    stiffness_rating: int | None = Field(None, ge=0, le=10)

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
    movement_analytics: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class SessionSummaryDTO(BaseModel):
    session: RehabilitationSessionResponse
    exercise_name: str
    improvement_vs_previous_rom: Optional[float] = None
    previous_session_id: Optional[int] = None
    movement_changes: Optional[dict[str, float]] = None
