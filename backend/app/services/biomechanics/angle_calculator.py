import numpy as np
from typing import Dict, Any, Optional, Tuple
from app.services.biomechanics.quaternion_math import (
    relative_quaternion,
    quaternion_to_euler_angles,
    normalize_quaternion,
    quaternion_conjugate,
    quaternion_multiply
)

class ShoulderAngleCalculator:
    """
    Biomechanical processing engine for deriving anatomical shoulder angles
    from dual BNO086 IMUs (Chest reference + Upper Arm).
    """
    def __init__(self, calibration_offset: Optional[np.ndarray] = None):
        # Neutral pose calibration offset quaternion (relative orientation at neutral)
        self.calibration_offset = calibration_offset
        self.last_timestamp: Optional[float] = None
        self.last_angles: Optional[Dict[str, float]] = None
        self.max_angular_velocity_deg_s: float = 650.0 # Anatomical human limit to flag glitches

    def set_calibration_neutral(self, q_chest: np.ndarray, q_arm: np.ndarray):
        """
        Calibrates the zero reference: records the relative orientation when
        the patient is standing naturally with their arm at rest.
        """
        q_rel = relative_quaternion(q_chest, q_arm)
        self.calibration_offset = q_rel

    def reset_state(self):
        self.last_timestamp = None
        self.last_angles = None

    def compute_angles(
        self,
        q_chest_raw: np.ndarray,
        q_arm_raw: np.ndarray,
        timestamp: float,
        exercise_key: str = "flexion",
        affected_side: str = "right"
    ) -> Dict[str, Any]:
        """
        Calculates relative shoulder orientation and estimates:
        - flexion angle
        - abduction angle
        - rotation angle
        - primary angle for active exercise
        - angular velocity (deg/s)
        - quality flags
        """
        # 1. Compute relative rotation q_rel = q_chest^-1 * q_arm
        q_rel = relative_quaternion(q_chest_raw, q_arm_raw)
        
        # 2. If calibrated, remove the neutral offset: q_calibrated = q_cal_offset^-1 * q_rel
        if self.calibration_offset is not None:
            q_cal_inv = quaternion_conjugate(self.calibration_offset)
            q_effective = quaternion_multiply(q_cal_inv, q_rel)
            q_effective = normalize_quaternion(q_effective)
        else:
            q_effective = q_rel

        # 3. Calculate anatomical angles
        # Roll = coronal tilt (Abduction)
        # Pitch = sagittal tilt (Flexion)
        # Yaw = longitudinal humeral rotation
        roll, pitch, yaw = quaternion_to_euler_angles(q_effective)

        # Standardize signs:
        # Flexion: forward elevation is positive (0 to ~180)
        flexion_deg = abs(pitch)
        
        # Abduction: lateral elevation is positive (0 to ~180)
        abduction_deg = abs(roll)
        
        # Internal / External rotation
        # Positive yaw indicates external rotation; negative internal rotation (adapted for side)
        side_multiplier = 1.0 if affected_side == "right" else -1.0
        signed_rot = yaw * side_multiplier
        ext_rot_deg = max(0.0, signed_rot)
        int_rot_deg = max(0.0, -signed_rot)

        # Determine primary angle based on selected exercise
        if exercise_key == "flexion":
            primary_angle = flexion_deg
        elif exercise_key == "abduction":
            primary_angle = abduction_deg
        elif exercise_key == "external_rotation":
            primary_angle = ext_rot_deg
        elif exercise_key == "internal_rotation":
            primary_angle = int_rot_deg
        else:
            primary_angle = max(flexion_deg, abduction_deg)

        # 4. Calculate angular velocity: d(primary_angle) / dt
        angular_velocity = 0.0
        quality_flag = "VALID"
        
        if self.last_timestamp is not None and self.last_angles is not None:
            dt = timestamp - self.last_timestamp
            if dt > 0.001 and dt < 1.0:
                d_theta = abs(primary_angle - self.last_angles.get("primary", primary_angle))
                angular_velocity = round(d_theta / dt, 1)
                
                # Check for unrealistic spike / glitch
                if angular_velocity > self.max_angular_velocity_deg_s:
                    quality_flag = "GLITCH_SPIKE_REJECTED"
            elif dt >= 1.0:
                quality_flag = "STALE_TIME_GAP"

        self.last_timestamp = timestamp
        self.last_angles = {
            "flexion": flexion_deg,
            "abduction": abduction_deg,
            "ext_rot": ext_rot_deg,
            "int_rot": int_rot_deg,
            "primary": primary_angle
        }

        return {
            "timestamp": timestamp,
            "q_relative": [round(float(v), 4) for v in q_effective],
            "flexion": round(float(flexion_deg), 1),
            "abduction": round(float(abduction_deg), 1),
            "ext_rotation": round(float(ext_rot_deg), 1),
            "int_rotation": round(float(int_rot_deg), 1),
            "primary_angle": round(float(primary_angle), 1),
            "angular_velocity": float(angular_velocity),
            "quality_flag": quality_flag
        }
