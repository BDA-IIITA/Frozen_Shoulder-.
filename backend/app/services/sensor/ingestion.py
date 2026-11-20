import time
import asyncio
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from app.services.biomechanics.quaternion_math import normalize_quaternion
from app.services.biomechanics.angle_calculator import ShoulderAngleCalculator
from app.services.biomechanics.rep_counter import RepetitionCounter
from app.services.sensor.simulator import SensorSimulator
from app.core.logger import get_logger

logger = get_logger("SensorIngestionService")

class SensorIngestionService:
    """
    Central real-time ingestion service coordinating sensor streams
    (Demo or Live ESP32), biomechanical processing, repetition tracking,
    and live WebSocket broadcasting.
    """
    def __init__(self):
        self.angle_calculator = ShoulderAngleCalculator()
        self.rep_counter = RepetitionCounter()
        self.simulator = SensorSimulator()

        # Operational state
        self.mode: str = "demo"  # "demo" or "live"
        self.is_monitoring: bool = False
        self.current_exercise: str = "flexion"
        self.current_side: str = "right"
        self.active_session_id: Optional[int] = None

        # Diagnostics
        self.packets_received: int = 0
        self.packets_invalid: int = 0
        self.last_packet_time: Optional[float] = None
        self.detected_sensors: List[str] = []

        # Sliding window of processed outputs for live display
        self.recent_samples: List[Dict[str, Any]] = []
        self.max_buffer_size: int = 300

        # Background simulator task reference
        self._sim_task: Optional[asyncio.Task] = None
        self._subscribers: List[asyncio.Queue] = []

    def set_mode(self, mode: str):
        if mode not in ["demo", "live"]:
            raise ValueError("Mode must be 'demo' or 'live'")
        self.mode = mode
        logger.info(f"Sensor ingestion mode switched to: {mode}")

    def set_exercise(self, exercise_key: str, affected_side: str = "right"):
        self.current_exercise = exercise_key
        self.current_side = affected_side
        self.simulator.set_exercise(exercise_key)
        
        # Configure thresholds per exercise
        if exercise_key in ["external_rotation", "internal_rotation"]:
            self.rep_counter.threshold_up = 25.0
            self.rep_counter.threshold_down = 10.0
        elif exercise_key == "abduction":
            self.rep_counter.threshold_up = 40.0
            self.rep_counter.threshold_down = 18.0
        else: # flexion
            self.rep_counter.threshold_up = 45.0
            self.rep_counter.threshold_down = 20.0

    def start_monitoring(self, session_id: Optional[int] = None):
        self.is_monitoring = True
        self.active_session_id = session_id
        self.rep_counter.reset()
        self.angle_calculator.reset_state()
        self.recent_samples.clear()

        # Start background simulator generator if in demo mode and an event loop is active
        if self.mode == "demo":
            try:
                loop = asyncio.get_running_loop()
                if self._sim_task is None or self._sim_task.done():
                    self._sim_task = loop.create_task(self._run_demo_generator())
            except RuntimeError:
                pass
        logger.info(f"Started monitoring. Exercise={self.current_exercise}, Mode={self.mode}, SessionId={session_id}")

    def stop_monitoring(self):
        self.is_monitoring = False
        if self._sim_task and not self._sim_task.done():
            self._sim_task.cancel()
            self._sim_task = None
        logger.info("Stopped monitoring.")

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def process_packet(self, packet_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validates, normalizes, processes incoming sensor packet,
        and derives shoulder angles and repetition state.
        """
        self.packets_received += 1
        t = packet_dict.get("timestamp", time.time())
        self.last_packet_time = t

        sensors = packet_dict.get("sensors", {})
        self.detected_sensors = list(sensors.keys())

        # Validate mandatory sensors: chest and upper_arm
        if "chest" not in sensors or "upper_arm" not in sensors:
            self.packets_invalid += 1
            return None

        chest_q_dict = sensors["chest"].get("quaternion", {})
        arm_q_dict = sensors["upper_arm"].get("quaternion", {})

        try:
            q_chest = np.array([
                float(chest_q_dict.get("x", 0.0)),
                float(chest_q_dict.get("y", 0.0)),
                float(chest_q_dict.get("z", 0.0)),
                float(chest_q_dict.get("w", 1.0))
            ], dtype=np.float64)

            q_arm = np.array([
                float(arm_q_dict.get("x", 0.0)),
                float(arm_q_dict.get("y", 0.0)),
                float(arm_q_dict.get("z", 0.0)),
                float(arm_q_dict.get("w", 1.0))
            ], dtype=np.float64)
        except (ValueError, TypeError):
            self.packets_invalid += 1
            return None

        # Calculate biomechanical angles
        angle_result = self.angle_calculator.compute_angles(
            q_chest_raw=q_chest,
            q_arm_raw=q_arm,
            timestamp=t,
            exercise_key=self.current_exercise,
            affected_side=self.current_side
        )

        # Update repetition counter
        primary_angle = angle_result["primary_angle"]
        rep_result = self.rep_counter.process_sample(primary_angle, t)

        processed = {
            "timestamp": t,
            "device_id": packet_dict.get("device_id", "esp32-shoulder-01"),
            "source": packet_dict.get("source", self.mode),
            "exercise_key": self.current_exercise,
            "affected_side": self.current_side,
            "flexion_angle": angle_result["flexion"],
            "abduction_angle": angle_result["abduction"],
            "rotation_angle": angle_result["ext_rotation"] if self.current_exercise == "external_rotation" else angle_result["int_rotation"],
            "primary_angle": primary_angle,
            "angular_velocity": angle_result["angular_velocity"],
            "repetitions": rep_result["repetitions"],
            "rep_just_completed": rep_result["rep_just_completed"],
            "session_rom": rep_result["rom"],
            "session_min_angle": rep_result["session_min_angle"],
            "session_max_angle": rep_result["session_max_angle"],
            "state": rep_result["state"],
            "quality_flag": angle_result["quality_flag"],
            "q_relative": angle_result["q_relative"],
            "warnings": [] if angle_result["quality_flag"] == "VALID" else [angle_result["quality_flag"]]
        }

        # Keep in rolling buffer
        self.recent_samples.append(processed)
        if len(self.recent_samples) > self.max_buffer_size:
            self.recent_samples.pop(0)

        # Broadcast to all live subscribers
        self._broadcast(processed)
        return processed

    def _broadcast(self, data: Dict[str, Any]):
        for q in list(self._subscribers):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(data)
            except Exception:
                pass

    async def _run_demo_generator(self):
        """Generates demo IMU packets at 20Hz during Demo Monitoring"""
        logger.info("Demo IMU stream generator started at 20Hz.")
        try:
            while self.is_monitoring and self.mode == "demo":
                packet = self.simulator.generate_packet()
                self.process_packet(packet)
                await asyncio.sleep(0.05) # 20 Hz
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in demo generator: {e}", exc_info=True)
        finally:
            logger.info("Demo IMU stream generator ended.")

    def get_diagnostic_status(self) -> Dict[str, Any]:
        now = time.time()
        data_freshness = round(now - self.last_packet_time, 2) if self.last_packet_time else None
        
        # Determine active status based on freshness (< 2.5 seconds)
        is_fresh = data_freshness is not None and data_freshness < 2.5
        
        return {
            "device_id": "esp32-shoulder-01",
            "device_name": "ShoulderSense ESP32 IMU Hub",
            "device_type": "ESP32-BNO086 Dual-IMU",
            "connection_method": "WiFi/HTTP-WS",
            "is_active": is_fresh if self.mode == "live" else self.is_monitoring,
            "data_source_mode": self.mode,
            "is_monitoring": self.is_monitoring,
            "packets_received": self.packets_received,
            "packets_invalid": self.packets_invalid,
            "data_freshness_sec": data_freshness,
            "sensors_detected": self.detected_sensors,
            "current_exercise": self.current_exercise
        }

sensor_ingestion_service = SensorIngestionService()
