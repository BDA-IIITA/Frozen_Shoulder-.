"""Create blinded signal plots and compare estimates with reviewer-marked cycles."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .repetitions import estimate_cycles
from .signal import FS, LABEL, candidate_reps, filter_wrist, wrist_tilt_proxy


def plot(path, output, start, end):
    with np.load(path, allow_pickle=False) as archive:
        raw = archive["raw"]
    first = round(start * FS)
    last = len(raw) if end is None else round(end * FS)
    filtered, _ = filter_wrist(raw)
    fig, plots = plt.subplots(2, 1, sharex=True, figsize=(13, 5), layout="constrained")
    time = np.arange(first, last) / FS
    for plot, columns, units in zip(plots, (slice(0, 3), slice(3, 6)), ("m/s²", "rad/s")):
        for axis, series in zip("xyz", filtered[first:last, columns].T):
            plot.plot(time, series, label=axis)
        plot.set_ylabel(units)
        plot.set_xticks(np.arange(start, last / FS, .5 if last - first < 1250 else 2))
        plot.grid(alpha=.3)
        plot.legend()
    plots[-1].set_xlabel("Time in the original bout (s)")
    fig.savefig(output, dpi=130)
    plt.close(fig)


def evaluate(recordings, annotations):
    rows = []
    with annotations.open(newline="") as file:
        for row in csv.DictReader(file):
            with np.load(recordings / f"{row['recording_id']}.npz", allow_pickle=False) as archive:
                filtered = archive["filtered"]
            first, last = [round(float(row[key]) * FS) for key in ("start_s", "end_s")]
            anchors = [float(value) for value in row["phase_markers_s"].split()]
            if (not 0 <= first < last <= len(filtered)
                    or any(not first <= round(value * FS) < last for value in anchors)
                    or any(a >= b for a, b in zip(anchors, anchors[1:]))):
                raise ValueError(f"Invalid annotation for {row['recording_id']}")
            reviewed = max(0, len(anchors) - 1)
            estimates = {
                "initial_fsm": len(candidate_reps(filtered[first:last])),
                **{key: estimate_cycles(filtered[first:last], key).count
                   for key in ("signed_gyro", "gyro_magnitude", "acceleration")},
            }
            rows.append(dict(recording_id=row["recording_id"], start_s=first / FS,
                             end_s=last / FS, reviewer_cycles=reviewed, estimates=estimates,
                             errors={key: value - reviewed if value is not None else None
                                     for key, value in estimates.items()}))
    return rows


def coverage(recordings):
    methods = ("signed_gyro", "gyro_magnitude", "acceleration")
    stats = {method: {"bouts_reporting": 0, "cycle_proposals": 0} for method in ("initial_fsm", *methods)}
    bouts = no_quiet_reference = 0
    for path in sorted(recordings.glob("*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            if int(archive["label"]) != LABEL:
                continue
            filtered = archive["filtered"]
        bouts += 1
        no_quiet_reference += int(wrist_tilt_proxy(filtered) is None)
        old = len(candidate_reps(filtered))
        counts = {"initial_fsm": old if old else None,
                  **{method: estimate_cycles(filtered, method).count for method in methods}}
        for method, count in counts.items():
            if count is not None:
                stats[method]["bouts_reporting"] += 1
                stats[method]["cycle_proposals"] += count
    return {"flexion_bouts": bouts, "initial_reference_unavailable": no_quiet_reference, "methods": stats}



def neutral_candidates(recordings, output):
    """Export ordered wrist-proxy candidates without marking anatomical validation."""
    by_subject = {}
    rows = []
    bouts = 0
    for path in sorted(recordings.glob("*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            if int(archive["label"]) != LABEL:
                continue
            subject = str(archive["subject"])
            filtered = archive["filtered"]
        bouts += 1
        stats = by_subject.setdefault(subject, {"bouts": 0, "candidates": 0, "groups_of_three": 0})
        stats["bouts"] += 1
        angle = wrist_tilt_proxy(filtered)
        bounds = candidate_reps(filtered) if angle is not None else []
        stats["candidates"] += len(bounds)
        stats["groups_of_three"] += len(bounds) // 3
        for start, peak, end in bounds:
            rows.append((path.stem, subject, start / FS, peak / FS, end / FS,
                         round(float(angle[start]), 2), round(float(angle[peak]), 2),
                         round(float(angle[end]), 2)))
    with output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("recording_id", "subject", "start_s", "peak_s", "end_s", "start_proxy_deg",
                         "peak_proxy_deg", "end_proxy_deg"))
        writer.writerows(rows)
    return {"bouts": bouts, "wrist_proxy_candidates": len(rows),
            "groups_of_three": sum(row["groups_of_three"] for row in by_subject.values()),
            "subjects_with_groups": sum(row["groups_of_three"] > 0 for row in by_subject.values()),
            "by_subject": by_subject}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plotting = commands.add_parser("plot")
    plotting.add_argument("recording", type=Path)
    plotting.add_argument("output", type=Path)
    plotting.add_argument("--start", type=float, default=0.)
    plotting.add_argument("--end", type=float)
    scoring = commands.add_parser("evaluate")
    scoring.add_argument("recordings", type=Path)
    scoring.add_argument("annotations", type=Path)
    overview = commands.add_parser("coverage")
    overview.add_argument("recordings", type=Path)
    candidates = commands.add_parser("neutral-candidates")
    candidates.add_argument("recordings", type=Path)
    candidates.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "plot":
        plot(args.recording, args.output, args.start, args.end)
    elif args.command == "evaluate":
        print(json.dumps(evaluate(args.recordings, args.annotations), indent=2))
    elif args.command == "neutral-candidates":
        print(json.dumps(neutral_candidates(args.recordings, args.output), indent=2))
    else:
        print(json.dumps(coverage(args.recordings), indent=2))


if __name__ == "__main__":
    main()
