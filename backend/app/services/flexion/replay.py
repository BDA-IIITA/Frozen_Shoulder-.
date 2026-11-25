"""Catalog and load locally prepared wrist-only recordings."""

import os
from pathlib import Path
import re

import numpy as np

from .signal import FS, valid_wrist

DEFAULT_ARTIFACTS = Path(__file__).resolve().parents[4] / "artifacts/flexion-v2"
EXERCISES = {
    2: ("external_rotation", "External rotation at 90° abduction"),
    6: ("spars9x_6", "Biceps strengthening"),
    7: ("spars9x_7", "Cross-chest adduction"),
    8: ("flexion", "Active flexion"),
    9: ("spars9x_9", "Shoulder girdle stabilization"),
    10: ("spars9x_10", "Triceps pull-down"),
}
RECORDING_ID = re.compile(r"spars9x_s\d+_\d+")


def recording_path(identifier):
    if not RECORDING_ID.fullmatch(identifier):
        raise ValueError("Invalid recording identifier")
    root = Path(os.environ.get("SPARS9X_RECORDINGS", DEFAULT_ARTIFACTS / "recordings"))
    return root / f"{identifier}.npz"


def load_recording(identifier, *, samples=False):
    with np.load(recording_path(identifier), allow_pickle=False) as archive:
        label = int(archive["label"])
        raw = archive["raw"]
        if label not in EXERCISES or raw.ndim != 2 or raw.shape[1] != 6 or len(raw) == 0:
            raise ValueError("Invalid recording")
        exercise, title = EXERCISES[label]
        metadata = {
            "id": identifier, "participant": str(archive["subject"]),
            "start_row": int(archive["start"]), "side_code": int(archive["side"]),
            "label": label, "exercise_key": exercise, "exercise_name": title,
            "samples": len(raw), "sampling_hz": FS, "duration_s": len(raw) / FS,
        }
        if not samples:
            return metadata
        if not valid_wrist(raw).all():
            raise ValueError("Invalid wrist signal")
        return metadata, raw


def catalog():
    folder = recording_path("spars9x_s0_0").parent
    items = []
    for path in sorted(folder.glob("*.npz")):
        try:
            items.append(load_recording(path.stem))
        except (ValueError, KeyError, OSError):
            continue
    return items


def replay_packet(timestamp, sample):
    return {
        "timestamp": timestamp, "source": "replay", "device_id": "spars9x-replay",
        "sensors": {"wrist": {
            "accelerometer": dict(zip("xyz", map(float, sample[:3]))),
            "gyroscope": dict(zip("xyz", map(float, sample[3:]))),
        }},
    }
