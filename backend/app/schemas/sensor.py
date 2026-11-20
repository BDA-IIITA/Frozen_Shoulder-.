from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Literal

class QuaternionModel(BaseModel):
    x: float = Field(0.0, description="Quaternion X component")
    y: float = Field(0.0, description="Quaternion Y component")
    z: float = Field(0.0, description="Quaternion Z component")
    w: float = Field(1.0, description="Quaternion W component")

    @field_validator("w")
    def validate_non_zero(cls, v, values):
        # Full validation happens in quaternion normalizer
        return v

class SensorData(BaseModel):
    quaternion: QuaternionModel
    accelerometer: Optional[Dict[str, float]] = None
    gyroscope: Optional[Dict[str, float]] = None
    calibration_status: Optional[int] = Field(None, description="BNO086 calibration status 0-3")

class SensorPacket(BaseModel):
    timestamp: float = Field(..., description="UNIX epoch timestamp in seconds")
    device_id: str = Field("esp32-shoulder-01", description="Identifier of the transmitting ESP32")
    source: Literal["live", "demo"] = Field("live", description="Origin of packet: live hardware or demo generator")
    sensors: Dict[str, SensorData] = Field(..., description="Mapping of sensor locations: chest, upper_arm, etc.")

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
    warnings: list[str] = []
