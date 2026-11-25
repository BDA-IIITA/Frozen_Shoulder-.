from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, FiniteFloat, model_validator


class QuaternionModel(BaseModel):
    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat
    w: FiniteFloat

    @model_validator(mode="after")
    def validate_norm(self):
        from math import hypot

        if not 1e-6 <= hypot(self.x, self.y, self.z, self.w) <= 2:
            raise ValueError("Invalid orientation quaternion norm")
        return self


class SensorData(BaseModel):
    quaternion: Optional[QuaternionModel] = None
    sample_timestamp: Optional[FiniteFloat] = Field(None, ge=0, description="Per-sensor sample time in seconds on the packet device clock")
    accelerometer: Optional[Dict[str, FiniteFloat]] = None
    gyroscope: Optional[Dict[str, FiniteFloat]] = None
    calibration_status: Optional[int] = Field(None, description="BNO086 calibration status 0-3")


class SensorPacket(BaseModel):
    timestamp: FiniteFloat = Field(..., ge=0, description="Device sample time in seconds")
    device_id: str = Field("esp32-shoulder-01", min_length=1, max_length=64)
    source: Literal["live", "demo"] = "live"
    sensors: Dict[str, SensorData]


class ProcessedAngleOutput(BaseModel):
    timestamp: float
    device_id: str
    source: Literal["live", "demo"]
    exercise_key: str
    affected_side: str
    flexion_angle: float
    abduction_angle: float
    rotation_angle: Optional[float] = None
    primary_angle: float
    angular_velocity: float
    repetitions: int
    session_rom: float
    session_min_angle: float
    session_max_angle: float
    state: str
    quality_flag: str
    q_relative: list[float]
    warnings: list[str] = Field(default_factory=list)
