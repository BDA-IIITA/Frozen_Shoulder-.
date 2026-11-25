"""Generate descriptive SPARS9x wrist reference ranges using shared preprocessing."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.services.flexion.dataset import recordings
from app.services.flexion.replay import DEFAULT_ARTIFACTS
from app.services.flexion.signal import FEATURES, FS, WINDOW, features

OUTPUT = DEFAULT_ARTIFACTS.parent / "spars9x-wrist-reference.json"
LABELS = range(1, 11)
WRIST_FEATURES = ("gyro_mean_rad_s", "gyro_max_rad_s", "jerk_rms_m_s3")


def build(dataset):
    paths = sorted(dataset.glob("spars9x_s*.csv"))
    if not paths:
        raise ValueError("No SPARS9x participant files found")
    feature_indices = [FEATURES.index(key) for key in WRIST_FEATURES]
    durations = {label: defaultdict(list) for label in LABELS}
    collections = {label: defaultdict(list) for label in LABELS}
    for path in paths:
        for bout in recordings(path, {}, exercise_labels=LABELS):
            durations[bout.label][bout.subject].append(len(bout.wrist) / FS)
            collections[bout.label][bout.subject].extend(
                features(bout.wrist[start:start + WINDOW])[feature_indices]
                for start in range(0, len(bout.wrist) - WINDOW + 1, WINDOW)
            )
    labels = {}
    for label, subjects in collections.items():
        included = [windows for windows in subjects.values() if windows]
        if not included:
            continue
        participant_medians = np.array([np.median(windows, axis=0) for windows in included])
        quantiles = np.percentile(participant_medians, [10, 50, 90], axis=0)
        labels[label] = {"participants": len(included), "windows": sum(map(len, included)),
                         "metrics": {name: dict(zip(("p10", "median", "p90"), map(float, column)))
                                     for name, column in zip(WRIST_FEATURES, quantiles.T)}}
        bout_medians = [np.median(values) for values in durations[label].values()]
        labels[label]["metrics"]["labeled_bout_duration_s"] = dict(
            zip(("p10", "median", "p90"), map(float, np.percentile(bout_medians, [10, 50, 90]))))
    return {"sampling_hz": FS, "window_s": WINDOW / FS, "participant_files": len(paths), "labels": labels}


def load():
    try:
        return json.loads(OUTPUT.read_text())
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = build(args.dataset)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['participant_files']} participants, {len(report['labels'])} exercise labels")
