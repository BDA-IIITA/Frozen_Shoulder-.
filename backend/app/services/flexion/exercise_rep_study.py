"""Train offline three-cycle reference models for all labeled SPARS9x exercises."""

import argparse
import csv
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import butter, find_peaks, sosfiltfilt

from .dataset import recordings
from .live_rep_reference import SCHEMA, rep_excursion
from .rep_study import train
from .repetitions import estimate_cycles
from .signal import FS, filter_wrist

LABELS = range(1, 11)
FIELDS = ("recording_id", "subject", "start_s", "peak_s", "end_s",
          "start_proxy_deg", "peak_proxy_deg", "end_proxy_deg")


def cycle_chains(filtered):
    """Find displacement excursions between consecutive low-phase landmarks."""
    periods = [estimate_cycles(filtered, method) for method in ("signed_gyro", "acceleration")]
    usable = [estimate for estimate in periods if estimate.period_s is not None]
    if not usable:
        return None, []
    period = max(usable, key=lambda estimate: estimate.periodicity).period_s * FS
    gyro = filtered[:, 3:]
    _, _, basis = np.linalg.svd(gyro - np.median(gyro, axis=0), full_matrices=False)
    axis = basis[0]
    axis *= np.sign(axis[np.argmax(np.abs(axis))])
    angle = np.degrees(cumulative_trapezoid(gyro @ axis, dx=1 / FS, initial=0))
    angle = sosfiltfilt(butter(2, .12, btype="highpass", fs=FS, output="sos"), angle)
    # Orient the displacement so the bout's initial phase is nearer the lower landmark.
    if np.median(angle[:FS // 4]) > np.median(angle):
        angle = -angle
    amplitude = np.quantile(angle, .9) - np.quantile(angle, .1)
    if amplitude < 5:
        return angle, []
    troughs, _ = find_peaks(-angle, prominence=.25 * amplitude, distance=max(1, int(.55 * period)))
    chains = []
    chain = []
    for start, end in zip(troughs[:-1], troughs[1:]):
        peak = start + int(np.argmax(angle[start:end + 1]))
        valid = (.65 * period <= end - start <= 1.45 * period
                 and start + .12 * period <= peak <= end - .12 * period
                 and angle[peak] - max(angle[start], angle[end]) >= max(5, .35 * amplitude)
                 and abs(angle[end] - angle[start]) <= .25 * amplitude)
        if not valid:
            if chain:
                chains.append(chain)
                chain = []
            continue
        chain.append((start, peak, end))
    if chain:
        chains.append(chain)
    return angle, chains


def study(dataset, output, *, sparse=False):
    sources = sorted(dataset.glob("spars9x_s*.csv"))
    if not sources:
        raise ValueError(f"No SPARS9x participant files found in {dataset}")
    rng = np.random.default_rng(42)
    collected = {label: [] for label in LABELS}
    coverage = {label: {"bouts": 0, "cycle_candidates": 0} for label in LABELS}
    for path in sources:
        for bout in recordings(path, {}, exercise_labels=LABELS):
            coverage[bout.label]["bouts"] += 1
            filtered, _ = filter_wrist(bout.wrist)
            angle, chains = cycle_chains(filtered)
            for index, chain in enumerate(chains):
                coverage[bout.label]["cycle_candidates"] += len(chain)
                sequence = 0
                for start, peak, end in chain:
                    identifier = f"{bout.subject}_{bout.start}_chain{index}_{sequence}"
                    if sparse:
                        # Simulate the currently observed 1.67 Hz wrist transmission.
                        # Keep actual samples and discard a tail shorter than one interval.
                        sample_indices = np.arange(start, end + 1, 30)
                        if len(sample_indices) >= 7 and rng.random() < .5:
                            # One missed interior packet produces a 1.2 s interval.
                            sample_indices = np.delete(sample_indices, rng.integers(1, len(sample_indices) - 1))
                        samples = np.column_stack((sample_indices / FS, bout.wrist[sample_indices, 3:]))
                        excursion = rep_excursion(samples)
                        if excursion is None:
                            sequence += 1
                            continue
                        landmarks = (0., excursion, 0.)
                    else:
                        landmarks = (angle[start], angle[peak], angle[end])
                    collected[bout.label].append((identifier, bout.subject, start / FS, peak / FS, end / FS,
                                                  *landmarks))
    results = {}
    for label, rows in collected.items():
        folder = output / f"label_{label:02}"
        folder.mkdir(parents=True, exist_ok=True)
        candidates = folder / "candidates.csv"
        with candidates.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(FIELDS)
            writer.writerows(rows)
        chain_counts = Counter(row[0] for row in rows)
        participants = {row[1] for row in rows if chain_counts[row[0]] >= 3}
        results[label] = {**coverage[label], "participants_with_groups": len(participants)}
        if len(participants) >= 3:
            report = train(candidates, folder, input_description=(
                f"SPARS9x activity {label}, three consecutive wrist projected-gyro displacement cycles"),
                signal_schema=SCHEMA if sparse else None)
            results[label].update({key: report[key] for key in (
                "groups", "held_out_accepted", "held_out_rejected", "held_out_acceptance",
                "mean_participant_acceptance")})
        else:
            results[label]["status"] = "insufficient_participants"
    report = {"participant_files": len(sources), "labels": results}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--sparse", action="store_true")
    args = parser.parse_args()
    print(json.dumps(study(args.dataset, args.output, sparse=args.sparse), indent=2))
