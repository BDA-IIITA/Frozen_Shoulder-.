"""Local model loading and per-session wrist analytics."""

from collections import deque
from hashlib import sha256
import logging
import os
from pathlib import Path
from .replay import DEFAULT_ARTIFACTS

import joblib
import numpy as np
import sklearn
from sklearn.pipeline import Pipeline

from .signal import FEATURES, FS, SCHEMA, WINDOW, features, valid_wrist

DEFAULT_MODEL = DEFAULT_ARTIFACTS / "flexion.joblib"
logger = logging.getLogger(__name__)


class FlexionReference:
    def __init__(self):
        self.model = None
        self.model_id = None

    def load(self, path=None):
        self.model = None
        self.model_id = None
        path = Path(path or os.environ.get("FLEXION_MODEL_PATH", DEFAULT_MODEL))
        if not path.is_file():
            return
        try:
            artifact = joblib.load(path)
            model = artifact["model"]
            if (artifact["schema"] != SCHEMA or artifact["scikit_learn"] != sklearn.__version__
                    or not isinstance(model, Pipeline) or model.n_features_in_ != len(FEATURES)):
                raise ValueError("Incompatible model or feature contract")
            self.model_id = sha256(path.read_bytes()).hexdigest()[:16]
            self.model = model
        except Exception as exc:
            logger.warning("Flexion model unavailable at %s: %s", path, exc)

    def predict(self, vector):
        if self.model is None:
            return None
        row = [vector]
        return int(self.model.predict(row)[0]), float(self.model.decision_function(row)[0])


reference = FlexionReference()


def wrist_axes(sensor):
    try:
        values = np.array([sensor[key][axis]
                           for key in ("accelerometer", "gyroscope") for axis in "xyz"])
    except (KeyError, TypeError):
        return None
    return values if valid_wrist(values) else None


class WristSession:
    def __init__(self, exercise, reference_model=reference):
        self.exercise = exercise
        self.reference = reference_model
        self.window = []
        self.recent = deque(maxlen=12 * FS + 1)
        self.last_time = None
        self.device = None
        self.wrist_sample_count = 0
        self.last_wrist_interval_s = None
        self.windows = 0
        self.gyro_mean_sum = 0.
        self.jerk_rms_squares = 0.
        self.gyro_peak = None
        self.scores = []
        self.score_times = []
        self.score_starts = []
        self.predictions = []
        self.score_sum = 0.
        self.first_time = None
        self.outliers = 0
        self.latest_prediction = None
        self.last_features = None
        self.last_rep = None

    def add(self, timestamp, device, values):
        if values is not None:
            self.wrist_sample_count += 1
            if self.last_time is not None and self.device == device:
                self.last_wrist_interval_s = timestamp - self.last_time
        if (values is None or device != self.device or self.last_time is None
                or not .014 <= timestamp - self.last_time <= .026):
            self.window.clear()
            self.recent.clear()
        self.last_time = timestamp
        self.device = device
        if values is None:
            return
        if self.first_time is None:
            self.first_time = timestamp
        self.recent.append((timestamp, values))
        self.window.append((timestamp, values))
        if len(self.window) == WINDOW:
            duration = self.window[-1][0] - self.window[0][0]
            if abs(duration - (WINDOW - 1) / FS) <= .08:
                vector = features([row for _, row in self.window])
                self.windows += 1
                self.gyro_mean_sum += vector[3]
                self.jerk_rms_squares += vector[7] ** 2
                self.gyro_peak = max(self.gyro_peak or 0., float(vector[5]))
                self.last_features = dict(zip(FEATURES, map(float, vector)))
                if self.reference is not None and self.exercise == "flexion":
                    result = self.reference.predict(vector)
                    if result is not None:
                        prediction, score = result
                        self.scores.append(score)
                        self.score_sum += score
                        self.predictions.append(prediction)
                        self.score_starts.append(round(self.window[0][0] - self.first_time, 3))
                        self.score_times.append(round(timestamp - self.first_time, 3))
                        self.outliers += int(prediction == -1)
                        self.latest_prediction = prediction
            self.window.clear()

    def complete_rep(self, start, end):
        selected = [(t, row) for t, row in self.recent if start - .002 <= t <= end]
        if (len(selected) < 16 or abs(start - selected[0][0]) > .003
                or abs(end - selected[-1][0]) > .003
                or abs(end - start - (len(selected) - 1) / FS) > .08):
            self.last_rep = None
            return
        vector = features([row for _, row in selected])
        self.last_rep = dict(zip(FEATURES, map(float, vector)))

    def summary(self, *, include_scores=False):
        if self.reference is None:
            return {
                "wrist_sample_count": self.wrist_sample_count,
                "buffered_wrist_samples": len(self.window),
                "last_wrist_interval_s": self.last_wrist_interval_s,
                "windows": self.windows,
                "wrist_features": self.last_features, "last_rep_features": self.last_rep,
                "wrist_gyro_peak_rad_s": self.gyro_peak,
                "wrist_gyro_mean_rad_s": float(self.gyro_mean_sum / self.windows) if self.windows else None,
                "wrist_jerk_rms_m_s3": float(np.sqrt(self.jerk_rms_squares / self.windows)) if self.windows else None,
            }
        if self.exercise != "flexion":
            status = "unsupported_exercise"
        elif self.reference.model is None:
            status = "model_unavailable"
        elif self.scores:
            status = "scored"
        elif self.wrist_sample_count:
            status = "collecting"
        else:
            status = "wrist_data_unavailable"
        scores = self.scores
        report = {
            "status": status,
            "model_id": self.reference.model_id if self.exercise == "flexion" else None,
            "wrist_sample_count": self.wrist_sample_count,
            "buffered_wrist_samples": len(self.window),
            "last_wrist_interval_s": self.last_wrist_interval_s,
            "windows": self.windows, "scored_windows": len(scores),
            "outlier_windows": self.outliers if scores else None,
            "reference_windows": len(scores) - self.outliers if scores else None,
            "latest_prediction": self.latest_prediction,
            "latest_decision_score": scores[-1] if scores else None,
            "mean_decision_score": self.score_sum / len(scores) if scores else None,
            "wrist_features": self.last_features, "last_rep_features": self.last_rep,
            "wrist_gyro_peak_rad_s": self.gyro_peak,
            "wrist_gyro_mean_rad_s": float(self.gyro_mean_sum / self.windows) if self.windows else None,
            "wrist_jerk_rms_m_s3": float(np.sqrt(self.jerk_rms_squares / self.windows)) if self.windows else None,
        }
        if include_scores:
            report["decision_scores"] = scores.copy()
            report["decision_trace"] = [
                {"start_s": start, "time_s": end, "score": score, "prediction": prediction}
                for start, end, score, prediction in zip(self.score_starts, self.score_times, scores, self.predictions)
            ]
        return report
