import numpy as np
from typing import Tuple, Optional

def normalize_quaternion(q: np.ndarray) -> np.ndarray:
    """
    Normalizes a quaternion [x, y, z, w].
    Handles zero or near-zero norms safely.
    Returns normalized [x, y, z, w] or identity [0, 0, 0, 1] if invalid.
    """
    norm = np.linalg.norm(q)
    if norm < 1e-8 or not np.isfinite(norm):
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return q / norm

def quaternion_conjugate(q: np.ndarray) -> np.ndarray:
    """
    Conjugate of quaternion [x, y, z, w] -> [-x, -y, -z, w].
    For unit quaternions, conjugate is the inverse rotation.
    """
    return np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float64)

def quaternion_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """
    Hamiltonian product of two quaternions q1 and q2, where q = [x, y, z, w].
    q_product = q1 * q2
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    
    return np.array([x, y, z, w], dtype=np.float64)

def relative_quaternion(q_chest: np.ndarray, q_arm: np.ndarray) -> np.ndarray:
    """
    Calculates the relative orientation of the upper arm relative to the chest:
    q_rel = q_chest_inv * q_arm
    where q_chest and q_arm are world-to-sensor quaternions [x, y, z, w].
    """
    q_c = normalize_quaternion(q_chest)
    q_a = normalize_quaternion(q_arm)
    q_c_inv = quaternion_conjugate(q_c)
    q_rel = quaternion_multiply(q_c_inv, q_a)
    return normalize_quaternion(q_rel)

def quaternion_to_euler_angles(q: np.ndarray) -> Tuple[float, float, float]:
    """
    Converts unit quaternion [x, y, z, w] to Euler angles (roll, pitch, yaw) in degrees.
    Sequence corresponds to anatomical shoulder motion approximations:
    - Pitch (Flexion / Extension around lateral axis): arm forward/back
    - Roll (Abduction / Adduction around sagittal axis): arm out to side
    - Yaw (Internal / External rotation around humeral longitudinal axis)
    """
    x, y, z, w = q
    
    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)
    
    # Pitch (y-axis rotation) with gimbal lock protection
    sinp = 2.0 * (w * y - z * x)
    if np.abs(sinp) >= 1.0:
        pitch = np.copysign(np.pi / 2.0, sinp)
    else:
        pitch = np.arcsin(sinp)
        
    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)
    
    return (
        float(np.degrees(roll)),
        float(np.degrees(pitch)),
        float(np.degrees(yaw))
    )

def quaternion_to_rotation_angle(q: np.ndarray) -> float:
    """
    Calculates the total angle of rotation (in degrees) from identity:
    angle = 2 * acos(|w|)
    """
    q_norm = normalize_quaternion(q)
    w = np.clip(np.abs(q_norm[3]), 0.0, 1.0)
    angle_rad = 2.0 * np.arccos(w)
    return float(np.degrees(angle_rad))
