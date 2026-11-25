import numpy as np
from typing import Dict, Any, Optional, Tuple
from app.services.biomechanics.quaternion_math import (
    relative_quaternion,
    normalize_quaternion,
    quaternion_conjugate,
    quaternion_multiply
)

LIVE_MOVEMENT_GAP_S = 1.25

def motion_axis(relative, neutral):
    delta = normalize_quaternion(quaternion_multiply(relative, quaternion_conjugate(neutral)))
    if delta[3] < 0:
        delta = -delta
    length = np.linalg.norm(delta[:3])
    angle = np.degrees(2 * np.arctan2(length, delta[3]))
    if not 15 <= angle <= 110:
        raise ValueError("Capture a distinct raise from neutral between 15° and 110°.")
    return delta[:3] / length


def calibrated_axes(forward_axis, side_axis, side):
    alignment = float(np.dot(forward_axis, side_axis))
    if abs(alignment) > .5:
        raise ValueError("Forward and side raises look too similar. Capture a sideways raise.")
    forward = side_axis if side == "right" else -side_axis
    lateral = -forward_axis
    up = np.cross(forward, lateral)
    up /= np.linalg.norm(up)
    # Fit both references symmetrically rather than preserving one and moving the other.
    u, _, vh = np.linalg.svd(np.array([forward, lateral, up]))
    return u @ vh


def orientation_components(delta, basis, exercise):
    forward, lateral, up = basis
    vector, scalar = delta[:3], delta[3]
    down = -up
    # Rotate the neutral limb direction by the torso-frame motion quaternion.
    limb = down + 2 * np.cross(vector, np.cross(vector, down) + scalar * down)
    x, y, z = basis @ limb
    horizontal = np.hypot(x, y)
    elevation = float(np.degrees(np.arctan2(horizontal, -z)))
    if horizontal > 1e-7:
        flexion = float(np.degrees(np.arctan2(abs(x), -z))) if abs(x) > 1e-7 else 0.
        abduction = float(np.degrees(np.arctan2(abs(y), -z))) if abs(y) > 1e-7 else 0.
        deviation = float(np.degrees(np.arctan2(min(abs(x), abs(y)), max(abs(x), abs(y)))))
        plane = "mixed" if deviation > 25 else "flexion" if abs(x) >= abs(y) else "abduction"
    else:
        flexion = elevation if exercise == "flexion" else 0.
        abduction = elevation if exercise == "abduction" else 0.
        plane = "neutral" if z < 0 else "indeterminate"
    if elevation < 8:
        plane = "neutral"
    axial = float(np.dot(vector, up))
    twist = float(np.degrees(2 * np.arctan2(axial, scalar))) if np.hypot(axial, scalar) > 1e-7 else 0.
    return flexion, abduction, (twist + 180) % 360 - 180, plane, elevation


class ShoulderAngleCalculator:
    """
    Chest-relative limb orientation estimates from paired sensor quaternions.
    """
    def __init__(self, calibration_offset: Optional[np.ndarray] = None):
        # Neutral pose calibration offset quaternion (relative orientation at neutral)
        self.calibration_offset = calibration_offset
        self.motion_basis = None
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
        affected_side: str = "right",
        use_total_movement: bool = False
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
        
        # Right multiplication removes the neutral mounting offset in the torso frame.
        q_effective = q_rel if self.calibration_offset is None else normalize_quaternion(
            quaternion_multiply(q_rel, quaternion_conjugate(self.calibration_offset))
        )
        basis = self.motion_basis if self.motion_basis is not None else np.eye(3)
        flexion_deg, abduction_deg, twist, plane, elevation = orientation_components(q_effective, basis, exercise_key)
        signed_rot = twist if affected_side == "right" else -twist
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

        neutral_rotation = float(np.degrees(2 * np.arctan2(
            np.linalg.norm(q_effective[:3]), abs(q_effective[3])
        ))) if self.calibration_offset is not None else None
        speed_angle = primary_angle
        if use_total_movement:
            if self.motion_basis is not None:
                speed_angle = elevation
            elif neutral_rotation is not None:
                speed_angle = neutral_rotation

        # 4. Calculate angular velocity: d(primary_angle) / dt
        angular_velocity = 0.0
        quality_flag = "VALID"
        
        if self.last_timestamp is not None and self.last_angles is not None:
            dt = timestamp - self.last_timestamp
            max_gap = LIVE_MOVEMENT_GAP_S if use_total_movement else 1.0
            if 0.001 < dt < max_gap:
                d_theta = abs(speed_angle - self.last_angles.get("speed_angle", speed_angle))
                angular_velocity = round(d_theta / dt, 1)
                
                # Check for unrealistic spike / glitch
                if angular_velocity > self.max_angular_velocity_deg_s:
                    quality_flag = "GLITCH_SPIKE_REJECTED"
            elif dt <= 0:
                quality_flag = "NON_MONOTONIC_TIME"
            elif dt >= max_gap:
                quality_flag = "STALE_TIME_GAP"

        self.last_timestamp = timestamp
        self.last_angles = {
            "flexion": flexion_deg,
            "abduction": abduction_deg,
            "ext_rot": ext_rot_deg,
            "int_rot": int_rot_deg,
            "speed_angle": speed_angle
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
            "quality_flag": quality_flag,
            "movement_plane": plane,
            "total_elevation": round(elevation, 1),
            "neutral_rotation": round(neutral_rotation, 1) if neutral_rotation is not None else None,
            "off_plane": exercise_key in ("flexion", "abduction") and plane not in ("neutral", exercise_key, "indeterminate")
        }
