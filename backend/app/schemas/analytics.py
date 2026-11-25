from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import datetime

class ROMProgressItem(BaseModel):
    session_id: int
    date: str
    exercise_key: str
    rom: float
    max_angle: float
    min_angle: float
    repetitions: int
    data_source: str
    affected_side: str
    session_number: int
    duration_seconds: float
    movement_analytics: Optional[Dict[str, Any]] = None
    rehab_progress: Optional[Dict[str, Any]] = None

class WeeklyActivityItem(BaseModel):
    day: str
    date: str
    sessions_count: int
    total_repetitions: int

class MovementQualityItem(BaseModel):
    session_id: int
    date: str
    smoothness_score: Optional[float]
    rep_duration_variation: Optional[float]
    peak_angle_variation: Optional[float]
    exercise_key: str

class DashboardSummaryResponse(BaseModel):
    latest_rom: float
    best_rom: float
    total_repetitions: int
    total_sessions: int
    avg_movement_quality: Optional[float]
    rom_change_vs_prior: Optional[float]
    rom_change_percentage: Optional[float]
    recovery_summary_text: str
    device_status: Dict[str, Any]
    recent_sessions: List[Dict[str, Any]]
