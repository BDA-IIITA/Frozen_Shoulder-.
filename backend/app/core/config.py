import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings:
    PROJECT_NAME: str = "ShoulderSense"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{DATA_DIR}/shouldersense.db"
    )
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]
    
    # Sensor processing defaults
    DEFAULT_SAMPLE_RATE_HZ: float = 20.0
    STALE_DATA_TIMEOUT_SEC: float = 2.5
    MAX_SAMPLE_HISTORY: int = 600  # in-memory sliding window for charts
    
    # Demo sensor settings
    DEMO_SAMPLE_INTERVAL_SEC: float = 0.05  # 20 Hz

settings = Settings()
