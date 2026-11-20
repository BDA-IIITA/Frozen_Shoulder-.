import time
import math
import numpy as np
from typing import Dict, Any

class SensorSimulator:
    """
    Deterministic IMU Sensor Simulator for Shoulder Rehabilitation Demo Mode.
    Generates realistic biological kinematic trajectories (quaternions)
    for torso and upper-arm BNO086 sensors without physical hardware.
    """
    def __init__(self, exercise_key: str = "flexion", cycle_duration: float = 4.0):
        self.exercise_key = exercise_key
        self.cycle_duration = cycle_duration
        self.start_epoch = time.time()

    def set_exercise(self, exercise_key: str):
        self.exercise_key = exercise_key

    def generate_packet(self, t: float = None) -> Dict[str, Any]:
        """
        Generates a synchronized sensor packet for timestamp t.
        Outputs exact SensorPacket schema.
        """
        if t is None:
            t = time.time()
        
        elapsed = t - self.start_epoch
        # Normalized phase [0.0 to 1.0] across cycle
        phase = (elapsed % self.cycle_duration) / self.cycle_duration
        
        # Smooth biological trajectory: 0.5 * (1 - cos(2 * pi * phase))
        # gives smooth rest at 0, smooth peak at 1, smooth descent back to 0
        motion_profile = 0.5 * (1.0 - math.cos(2.0 * math.pi * phase))

        # 1. Chest sensor: slight natural breathing/postural sway (1-2 degrees)
        sway_pitch = 0.015 * math.sin(elapsed * 0.8) # rad (~0.8 deg)
        sway_roll = 0.010 * math.cos(elapsed * 0.6)
        
        # Chest quaternion (Euler: roll, pitch, yaw -> quaternion)
        q_chest = self._euler_to_quaternion(sway_roll, sway_pitch, 0.0)

        # 2. Arm sensor based on exercise type
        if self.exercise_key == "flexion":
            # Forward sagittal elevation from ~8 deg to ~82 deg (typical adhesive capsulitis progression)
            min_deg, max_deg = 8.0, 82.0
            cur_deg = min_deg + (max_deg - min_deg) * motion_profile
            cur_rad = math.radians(cur_deg)
            # Arm pitch motion relative to torso + sway
            q_arm = self._euler_to_quaternion(sway_roll * 0.5, sway_pitch + cur_rad, 0.0)

        elif self.exercise_key == "abduction":
            # Lateral coronal elevation from ~10 deg to ~68 deg
            min_deg, max_deg = 10.0, 68.0
            cur_deg = min_deg + (max_deg - min_deg) * motion_profile
            cur_rad = math.radians(cur_deg)
            q_arm = self._euler_to_quaternion(sway_roll + cur_rad, sway_pitch * 0.5, 0.0)

        elif self.exercise_key == "external_rotation":
            # External rotation from ~5 deg to ~42 deg
            min_deg, max_deg = 5.0, 42.0
            cur_deg = min_deg + (max_deg - min_deg) * motion_profile
            cur_rad = math.radians(cur_deg)
            q_arm = self._euler_to_quaternion(0.0, 0.0, cur_rad)

        elif self.exercise_key == "internal_rotation":
            # Internal rotation from ~5 deg to ~38 deg
            min_deg, max_deg = 5.0, 38.0
            cur_deg = min_deg + (max_deg - min_deg) * motion_profile
            cur_rad = math.radians(cur_deg)
            q_arm = self._euler_to_quaternion(0.0, 0.0, -cur_rad)

        else:
            # Default elevation
            min_deg, max_deg = 8.0, 75.0
            cur_deg = min_deg + (max_deg - min_deg) * motion_profile
            cur_rad = math.radians(cur_deg)
            q_arm = self._euler_to_quaternion(0.0, cur_rad, 0.0)

        return {
            "timestamp": round(t, 4),
            "device_id": "esp32-shoulder-01",
            "source": "demo",
            "sensors": {
                "chest": {
                    "quaternion": {
                        "x": round(float(q_chest[0]), 5),
                        "y": round(float(q_chest[1]), 5),
                        "z": round(float(q_chest[2]), 5),
                        "w": round(float(q_chest[3]), 5)
                    },
                    "calibration_status": 3
                },
                "upper_arm": {
                    "quaternion": {
                        "x": round(float(q_arm[0]), 5),
                        "y": round(float(q_arm[1]), 5),
                        "z": round(float(q_arm[2]), 5),
                        "w": round(float(q_arm[3]), 5)
                    },
                    "calibration_status": 3
                }
            }
        }

    @staticmethod
    def _euler_to_quaternion(roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Helper to create unit quaternion [x, y, z, w] from Euler angles in radians"""
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        q = np.array([x, y, z, w], dtype=np.float64)
        norm = np.linalg.norm(q)
        return q / norm if norm > 1e-8 else np.array([0.0, 0.0, 0.0, 1.0])
