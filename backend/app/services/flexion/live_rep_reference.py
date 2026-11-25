"""Shared sparse wrist features and live scoring for completed groups of three."""

import logging
import os
from pathlib import Path

import joblib
import numpy as np
import sklearn
from scipy.integrate import cumulative_trapezoid

from .replay import DEFAULT_ARTIFACTS

logger = logging.getLogger(__name__)
SCHEMA = "projected-gyro-sparse-triplet-v2"
# The app's other shoulder protocols lack a confirmed matching exercise label.
EXERCISES = {"flexion": 8}
NOMINAL_GAP_LIMIT_S = .85
MAX_SAMPLE_GAP_S = 1.25


def rep_excursion(samples):
    """Estimate one cycle's wrist excursion from timestamped angular velocity."""
    if len(samples) < 4:
        return None
    values = np.asarray(samples, dtype=float)
    clock, gyro = values[:, 0], values[:, 1:]
    gaps = np.diff(clock)
    if not np.isfinite(values).all() or np.any(gaps <= 0) or gaps.max() > MAX_SAMPLE_GAP_S:
        return None
    if gaps.max() > max(NOMINAL_GAP_LIMIT_S, .30 * (clock[-1] - clock[0])):
        return None
    _, singular, basis = np.linalg.svd(gyro - np.mean(gyro, axis=0), full_matrices=False)
    if singular[0] < .05:
        return None
    displacement = np.degrees(cumulative_trapezoid(gyro @ basis[0], clock, initial=0))
    # Remove endpoint drift. Either mounting direction yields the same excursion.
    displacement -= displacement[-1] * (clock - clock[0]) / (clock[-1] - clock[0])
    peak = float(np.max(np.abs(displacement)))
    return peak if peak >= 3 else None


def triplet_features(peaks):
    return [float(np.median(peaks)), float(np.ptp(peaks))]


class LiveRepReference:
    def __init__(self, exercise):
        self.label = EXERCISES.get(exercise)
        self.model = None
        self.reps = []
        self.trace = []
        self.status = "unsupported_exercise"
        if self.label is not None:
            self.status = "model_unavailable"
            self.model = models.get(self.label)
            if self.model is not None:
                self.status = "collecting"

    def add(self, samples, time_s):
        if self.model is None:
            return
        self.reps.append(rep_excursion(samples))
        if len(self.reps) < 3:
            return
        group = len(self.trace) + 1
        row = {"group": group, "first_rep": 3 * group - 2, "last_rep": 3 * group,
               "time_s": round(time_s, 3), "score": None, "prediction": None}
        invalid_reps = [row["first_rep"] + index for index, peak in enumerate(self.reps) if peak is None]
        if invalid_reps:
            row["invalid_reps"] = invalid_reps
            self.status = "insufficient_wrist_samples"
        else:
            features = [triplet_features(self.reps)]
            row.update(score=float(self.model.decision_function(features)[0]),
                       prediction=int(self.model.predict(features)[0]))
            self.status = "scored"
        self.trace.append(row)
        self.reps.clear()

    def summary(self):
        return {"status": self.status, "pending_reps": len(self.reps), "trace": self.trace.copy()}


models = {}


def load_models():
    root = Path(os.environ.get("LIVE_REP_MODELS", DEFAULT_ARTIFACTS.parent / "live-exercise-reps"))
    models.clear()
    for label in set(EXERCISES.values()):
        path = root / f"label_{label:02}" / "rep_reference.joblib"
        if not path.is_file():
            continue
        try:
            artifact = joblib.load(path)
            if artifact.get("signal_schema") == SCHEMA and artifact.get("scikit_learn") == sklearn.__version__:
                models[label] = artifact["model"]
        except Exception:
            logger.exception("Unable to load the three-rep reference for activity %s", label)
