"""Shared wrist processing contract for the offline pipeline and live inference."""

import numpy as np
from scipy.signal import butter, find_peaks, sosfilt, sosfilt_zi, sosfiltfilt

FS = 50
WINDOW = 200
LABEL = 8
CUTOFF = 5
ORDER = 4
SOS = butter(ORDER, CUTOFF, fs=FS, output="sos")
FEATURES = (
    "acc_mean_m_s2", "acc_std_m_s2", "acc_rms_m_s2",
    "gyro_mean_rad_s", "gyro_rms_rad_s", "gyro_max_rad_s",
    "duration_s", "jerk_rms_m_s3", "gyro_std_rad_s",
)
SCHEMA = {
    "version": 1, "features": list(FEATURES), "sampling_hz": FS,
    "window_samples": WINDOW, "cutoff_hz": CUTOFF, "filter_order": ORDER,
    "filter": "zero_phase_per_window", "activity_label": LABEL,
    "acceleration": "gravity_inclusive_m_s2", "gyroscope": "rad_s",
}


def valid_wrist(values):
    """Broad sanity bounds per axis, in SI units."""
    limits = [200, 200, 200, 40, 40, 40]
    return (np.isfinite(values) & (np.abs(values) <= limits)).all(axis=-1)


def filter_wrist(values, *, causal=False, state=None):
    """Zero-phase on ≥16 samples, otherwise causal. Return next causal state."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != 6 or not len(values) or not valid_wrist(values).all():
        raise ValueError("Expected a nonempty, valid six-axis wrist recording")
    if not causal and len(values) > 15:
        return sosfiltfilt(SOS, values, axis=0), None
    if state is None:
        state = sosfilt_zi(SOS)[:, :, None] * values[0]
    return sosfilt(SOS, values, axis=0, zi=state)


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def features(raw):
    """Extract features from one independently filtered sample span."""
    values, _ = filter_wrist(raw)
    acc = np.linalg.norm(values[:, :3], axis=1)
    gyro = np.linalg.norm(values[:, 3:], axis=1)
    jerk = np.linalg.norm(np.diff(values[:, :3], axis=0) * FS, axis=1)
    return np.array([
        acc.mean(), acc.std(), rms(acc), gyro.mean(), rms(gyro), gyro.max(),
        len(values) / FS, rms(jerk) if len(jerk) else 0., gyro.std(),
    ])


def wrist_tilt_proxy(filtered):
    """Angle between low-pass wrist acceleration and its initial reference."""
    acc = filtered[:, :3]
    gyro = np.linalg.norm(filtered[:, 3:], axis=1)
    if len(acc) < FS * 2 or np.median(gyro[:25]) > 0.25:
        return None
    baseline = np.median(acc[:25], axis=0)
    denominator = np.linalg.norm(acc, axis=1) * np.linalg.norm(baseline)
    if np.any(denominator < 1):
        return None
    return np.degrees(np.arccos(np.clip((acc @ baseline) / denominator, -1, 1)))


def candidate_reps(filtered):
    """Exploratory gravity-direction proxy, with complete return and motion checks."""
    angle = wrist_tilt_proxy(filtered)
    if angle is None:
        return []
    gyro = np.linalg.norm(filtered[:, 3:], axis=1)
    peaks, _ = find_peaks(angle, height=40, prominence=25, distance=FS)
    rest = np.flatnonzero(angle <= 15)
    bounds = []
    for peak in peaks:
        pos = np.searchsorted(rest, peak)
        if 0 < pos < len(rest):
            start, end = rest[pos - 1], rest[pos]
            if FS <= end - start <= 12 * FS and gyro[start:end].max() >= 0.25:
                if bounds and start < bounds[-1][2]:
                    if angle[peak] > angle[bounds[-1][1]]:
                        bounds[-1] = (start, peak, end)
                else:
                    bounds.append((start, peak, end))
    return bounds
