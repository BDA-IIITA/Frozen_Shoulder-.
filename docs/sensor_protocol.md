# Sensor Transmission Protocol & Hardware Integration

## 1. Documented JSON Sensor Schema

The ESP32 transmits telemetry packets to the backend via HTTP POST to `/api/sensor/ingest` or live WebSocket `/ws/live`.

### Packet Specification
```json
{
  "timestamp": 1790000000.0,
  "device_id": "esp32-shoulder-01",
  "source": "live",
  "sensors": {
    "chest": {
      "quaternion": {
        "x": 0.0000,
        "y": 0.0000,
        "z": 0.0000,
        "w": 1.0000
      },
      "calibration_status": 3
    },
    "upper_arm": {
      "quaternion": {
        "x": 0.0000,
        "y": 0.4226,
        "z": 0.0000,
        "w": 0.9063
      },
      "calibration_status": 3
    }
  }
}
```

### Field Definitions
- `timestamp`: Float UNIX timestamp in seconds with millisecond resolution.
- `device_id`: String identifier for the ESP32 transmitter (`esp32-shoulder-01`).
- `source`: Literal `"live"` for physical hardware, or `"demo"` for the software generator.
- `sensors.chest.quaternion`: Normalized float components `[x, y, z, w]` from Torso IMU (0x4A).
- `sensors.upper_arm.quaternion`: Normalized float components `[x, y, z, w]` from Humerus IMU (0x4B).
- `calibration_status`: Optional integer (0 = uncalibrated, 3 = fully calibrated BNO086 fusion).

---

## 2. Hardware Wiring Configuration

| ESP32 Pin | BNO086 #1 (Torso / Reference) | BNO086 #2 (Upper Arm) |
|---|---|---|
| **3.3V** | VCC | VCC |
| **GND** | GND, DI (PULLED LOW = 0x4A) | GND |
| **3.3V (Pullup)** | — | DI (PULLED HIGH = 0x4B) |
| **GPIO 21 (SDA)**| SDA | SDA |
| **GPIO 22 (SCL)**| SCL | SCL |

*Both sensors share the same I2C bus at 400kHz. The DI address select pin configures Sensor 1 at `0x4A` and Sensor 2 at `0x4B`.*
