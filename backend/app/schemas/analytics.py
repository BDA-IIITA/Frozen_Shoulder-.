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
