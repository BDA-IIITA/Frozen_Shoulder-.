"""Train an offline-only reference from groups of three wrist-proxy candidates."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .live_rep_reference import triplet_features

FEATURES = ("median_peak_excursion_deg", "peak_excursion_range_deg")
CONFIG = {"kernel": "rbf", "nu": .1, "gamma": "scale"}


def groups_of_three(candidates):
    recordings = defaultdict(list)
    for row in candidates:
        recordings[(row["subject"], row["recording_id"])].append(row)
    for (subject, recording), rows in sorted(recordings.items()):
        rows.sort(key=lambda row: float(row["start_s"]))
        for index in range(0, len(rows) - 2, 3):
            reps = rows[index:index + 3]
            peaks = [float(rep["peak_proxy_deg"]) -
                     (float(rep["start_proxy_deg"]) + float(rep["end_proxy_deg"])) / 2
                     for rep in reps]
            yield {
                "subject": subject, "recording_id": recording,
                "start_s": float(reps[0]["start_s"]), "end_s": float(reps[-1]["end_s"]),
                **dict(zip(FEATURES, triplet_features(peaks))),
            }


def train(candidates, output, *, input_description="SPARS9x forward flexion, three wrist gravity-direction candidates from one bout", signal_schema=None):
    with candidates.open(newline="") as file:
        rows = list(groups_of_three(csv.DictReader(file)))
    groups = np.array([row["subject"] for row in rows])
    if len(set(groups)) < 3:
        raise ValueError("At least three participants with complete candidate groups are required")
    data = np.array([[row[key] for key in FEATURES] for row in rows])
    settings = {
        "features": FEATURES, "config": CONFIG, "scikit_learn": sklearn.__version__,
        "input": input_description,
        "status": "experimental", "signal_schema": signal_schema,
    }
    folds = []
    output.mkdir(parents=True, exist_ok=True)
    for fit, test in LeaveOneGroupOut().split(data, groups=groups):
        model = make_pipeline(StandardScaler(), OneClassSVM(**CONFIG)).fit(data[fit])
        decisions = model.decision_function(data[test])
        predictions = model.predict(data[test])
        folds.append({"held_out_participant": groups[test[0]], "training_groups": len(fit),
                      "test_groups": len(test), "accepted": int(np.sum(predictions == 1))})
        for index, score, prediction in zip(test, decisions, predictions):
            rows[index].update(decision_score=float(score), prediction=int(prediction))

    accepted = sum(fold["accepted"] for fold in folds)
    report = {**settings, "participants": len(set(groups)), "groups": len(rows),
              "held_out_accepted": accepted, "held_out_rejected": len(rows) - accepted,
              "held_out_acceptance": accepted / len(rows),
              "mean_participant_acceptance": float(np.mean(
                  [fold["accepted"] / fold["test_groups"] for fold in folds])), "folds": folds}
    (output / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    with (output / "held_out_scores.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    model = make_pipeline(StandardScaler(), OneClassSVM(**CONFIG)).fit(data)
    joblib.dump({"model": model, **settings}, output / "rep_reference.joblib")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(train(args.candidates, args.output), indent=2))
