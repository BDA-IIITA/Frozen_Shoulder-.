"""Exploratory cycle estimates for labeled wrist recordings."""

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, correlate, find_peaks, sosfiltfilt

from .signal import FS


@dataclass
class CycleEstimate:
    bounds: list[tuple[int, int, int]]
    period_s: float | None = None
    periodicity: float | None = None

    @property
    def count(self):
        return len(self.bounds) if self.period_s is not None else None


def estimate_cycles(filtered, method="signed_gyro"):
    """Find same-phase intervals with a prominent opposite phase inside.

    Coherence gate and local checks abstain on weak/noisy recordings. Bounds
    are cycle phase markers, not labeled anatomical start or peak angles.
    """
    if len(filtered) < 5 * FS:
        return CycleEstimate([])
    accel, gyro = filtered[:, :3], filtered[:, 3:]
    if method == "signed_gyro":
        _, _, basis = np.linalg.svd(gyro - np.median(gyro, axis=0), full_matrices=False)
        motion = gyro @ basis[0]
        # Choose a consistent sign in the device frame.
        motion *= np.sign(basis[0, np.argmax(np.abs(basis[0]))])
    elif method == "gyro_magnitude":
        motion = np.linalg.norm(gyro, axis=1)
    elif method == "acceleration":
        _, _, basis = np.linalg.svd(accel - np.median(accel, axis=0), full_matrices=False)
        motion = accel @ basis[0]
    else:
        raise ValueError(f"Unknown cycle signal: {method}")
    band = butter(2, [.18, 2.0], btype="bandpass", fs=FS, output="sos")
    motion = sosfiltfilt(band, motion)
    scale = float(np.quantile(motion, .9) - np.quantile(motion, .1))
    if scale < (.6 if method == "acceleration" else .18):
        return CycleEstimate([])
    centered = motion - motion.mean()
    correlation = correlate(centered, centered, method="fft")[len(motion) - 1:]
    correlation /= correlation[0]
    min_lag, max_lag = int(.85 * FS), min(5 * FS, len(motion) // 3)
    candidates, _ = find_peaks(correlation[min_lag:max_lag + 1], height=.28, prominence=.12)
    if not len(candidates):
        return CycleEstimate([])
    lags = candidates + min_lag
    strongest = np.max(correlation[lags])
    if strongest < .35:
        return CycleEstimate([], periodicity=float(strongest))
    period = int(lags[correlation[lags] >= .8 * strongest][0])
    peaks, _ = find_peaks(motion, distance=max(1, int(.62 * period)), prominence=.34 * scale)
    troughs, _ = find_peaks(-motion, distance=max(1, int(.45 * period)), prominence=.30 * scale)
    bounds = []
    for start, end in zip(peaks[:-1], peaks[1:]):
        if not .63 * period <= end - start <= 1.47 * period:
            continue
        opposite = troughs[(troughs > start + .15 * period) & (troughs < end - .15 * period)]
        if len(opposite):
            middle = opposite[np.argmin(motion[opposite])]
            if min(motion[start], motion[end]) - motion[middle] >= .37 * scale:
                bounds.append((int(start), int(middle), int(end)))
    if len(bounds) < 2:
        return CycleEstimate([], periodicity=float(correlation[period]))
    return CycleEstimate(bounds, period / FS, float(correlation[period]))
