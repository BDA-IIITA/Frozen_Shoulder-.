from pydantic import BaseModel
from typing import Optional, List
import datetime

class DeviceStatusDTO(BaseModel):
    device_id: str
    device_name: str
    device_type: str
    connection_method: str
    is_active: bool
    last_seen_at: Optional[datetime.datetime] = None
    ip_address: Optional[str] = None
    data_source_mode: str  # "demo" or "live"
    packets_received: int
    packets_invalid: int
    data_freshness_sec: Optional[float] = None
    sensors_detected: List[str]

class ConnectDeviceRequest(BaseModel):
    mode: str = "demo" # "demo" or "live"
    ip_address: Optional[str] = None

class CalibrateRequest(BaseModel):
    device_id: str = "esp32-shoulder-01"
