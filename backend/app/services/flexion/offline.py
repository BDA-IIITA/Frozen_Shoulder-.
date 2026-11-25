"""Offline SPARS9x processing, training, and held-out evaluation."""
import argparse
import csv
import json
from itertools import product
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .dataset import recordings
from .replay import DEFAULT_ARTIFACTS
from .repetitions import estimate_cycles
from .signal import (
    FEATURES, FS, LABEL, SCHEMA, WINDOW, candidate_reps, features, filter_wrist,
    wrist_tilt_proxy,
)


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def plot_recording(path, raw, filtered, reps):
    clock = np.arange(len(raw)) / FS
    proxy = wrist_tilt_proxy(filtered)
    fig, axes = plt.subplots(3 if proxy is not None else 2, 1, sharex=True, figsize=(11, 7))
    for ax, columns, unit in zip(axes[:2], (slice(0, 3), slice(3, 6)), ("m/s²", "rad/s")):
        ax.plot(clock, np.linalg.norm(raw[:, columns], axis=1), label="Raw", alpha=.5)
        ax.plot(clock, np.linalg.norm(filtered[:, columns], axis=1), label="5 Hz filtered")
        ax.set_ylabel(unit)
        ax.legend()
    if proxy is not None:
        axes[2].plot(clock, proxy, label="Wrist tilt proxy", color="tab:purple")
        axes[2].axhline(15, linestyle=":", color="grey")
        axes[2].axhline(40, linestyle=":", color="grey")
        axes[2].set_ylabel("Degrees")
        axes[2].legend()
    for ax in axes:
        for start, peak, end in reps:
            ax.axvspan(start / FS, end / FS, alpha=.15, color="green")
            ax.axvline(peak / FS, alpha=.35, color="green")
    axes[-1].set_xlabel("Seconds from bout start")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def process(dataset, output):
    sources = sorted(dataset.glob("spars9x_s*.csv"))
    if not sources:
        raise ValueError(f"No SPARS9x CSVs in {dataset}")
    folder = output / "recordings"
    folder.mkdir(exist_ok=True)
    reports = {}
    metadata = ["subject", "side", "label", "bout_start", "start", "end_exclusive"]
    with (output / "features.csv").open("w", newline="") as feature_file, \
         (output / "repetitions.csv").open("w", newline="") as rep_file:
        writer = csv.writer(feature_file)
        writer.writerow(metadata + list(FEATURES))
        rep_writer = csv.writer(rep_file)
        rep_writer.writerow(metadata + ["peak"] + list(FEATURES))

        def write_background(subject, bout_start, start, raw):
            writer.writerow([subject, 0, 0, bout_start, start, start + WINDOW, *features(raw)])
        for path in sources:
            report = reports[path.stem] = {}
            for bout in recordings(path, report, background=write_background):
                prefix = [bout.subject, bout.side, bout.label, bout.start]
                filtered, _ = filter_wrist(bout.wrist)
                name = f"{bout.subject}_{bout.start}"
                np.savez_compressed(folder / f"{name}.npz", raw=bout.wrist, filtered=filtered,
                                    subject=bout.subject, side=bout.side, label=bout.label, start=bout.start)
                if bout.label == LABEL:
                    reps = estimate_cycles(filtered).bounds
                    for start, peak, end in reps:
                        rep_writer.writerow(prefix + [bout.start + start, bout.start + end + 1,
                                                      bout.start + peak, *features(bout.wrist[start:end + 1])])
                    plot_recording(output / f"signals_{name}.png", bout.wrist, filtered, reps)
                for start in range(0, len(bout.wrist) - WINDOW + 1, WINDOW):
                    end = start + WINDOW
                    writer.writerow(prefix + [bout.start + start, bout.start + end,
                                              *features(bout.wrist[start:end])])
            print(f"{path.name}: {report['rows']:,} rows", flush=True)
    save_json(output / "dataset_report.json", reports)


def participant_split(participants, seed=42):
    names = np.random.default_rng(seed).permutation(sorted(set(participants))).tolist()
    if len(names) < 3:
        raise ValueError("Need at least three participants with active-flexion windows")
    holdout = max(1, len(names) // 5)
    return {"train": names[2 * holdout:], "validation": names[holdout:2 * holdout],
            "test": names[:holdout]}


def matrix(frame):
    return frame[list(FEATURES)].to_numpy()


def score(model, frame):
    if frame.empty:
        return {"windows": 0, "accepted": 0, "acceptance": None}
    accepted = int((model.predict(matrix(frame)) == 1).sum())
    return {"windows": len(frame), "accepted": accepted, "acceptance": accepted / len(frame),
            "rejected": len(frame) - accepted, "rejection_rate": (len(frame) - accepted) / len(frame)}


def study_split(participants):
    # Four expansion-cohort participants were never used during the ten-subject pilot.
    expansion = sorted(s for s in set(participants) if int(s.rsplit("_s", 1)[1]) >= 10)
    if len(expansion) >= 8:
        test = np.random.default_rng(42).permutation(expansion)[:4].tolist()
        rest = np.random.default_rng(43).permutation(sorted(set(participants) - set(test))).tolist()
        return {"train": rest[4:], "validation": rest[:4], "test": test}
    return participant_split(participants)


def train(output):
    data = pd.read_csv(output / "features.csv")
    flexion = data[data.label == LABEL]
    split = study_split(flexion.subject)
    training = flexion[flexion.subject.isin(split["train"])]
    validation = flexion[flexion.subject.isin(split["validation"])]
    validation_other = data[data.subject.isin(split["validation"]) & ~data.label.isin([0, LABEL])]
    validation_background = data[data.subject.isin(split["validation"]) & (data.label == 0)]
    candidates = []
    best = None
    for nu, gamma in product((.01, .05, .1, .2), (.01, .05, .1, "scale")):
        model = Pipeline([("scaler", StandardScaler()),
                          ("svm", OneClassSVM(kernel="rbf", nu=nu, gamma=gamma))])
        model.fit(matrix(training))
        result = {"nu": nu, "gamma": gamma, **score(model, validation)}
        candidates.append(result)
        rejects = [score(model, subset)["rejection_rate"]
                   for subset in (validation_other, validation_background) if len(subset)]
        result["validation_ood_rejection"] = float(np.mean(rejects)) if rejects else None
        result["selection_score"] = (
            .75 * result["acceptance"] + .25 * result["validation_ood_rejection"]
            if rejects else result["acceptance"]
        )
        if best is None or result["selection_score"] > best[0]["selection_score"]:
            best = result, model
    selected, model = best
    settings = {"schema": SCHEMA, "split": split, "seed": 42, "kernel": "rbf",
                "nu": selected["nu"], "gamma": selected["gamma"],
                "scikit_learn": sklearn.__version__, "validation_search": candidates}
    joblib.dump({"model": model, **settings}, output / "flexion.joblib")
    save_json(output / "model_config.json", settings)


def evaluate(output):
    data = pd.read_csv(output / "features.csv")
    artifact = joblib.load(output / "flexion.joblib")
    model = artifact["model"]
    metrics = {}
    baseline = Pipeline([("scaler", StandardScaler()),
                         ("svm", OneClassSVM(kernel="rbf", nu=.01, gamma=.01))])
    baseline.fit(matrix(data[data.subject.isin(artifact["split"]["train"]) & (data.label == LABEL)]))
    fig, ax = plt.subplots(figsize=(8, 4))
    for name, participants in artifact["split"].items():
        subset = data[data.subject.isin(participants)]
        flexion = subset[subset.label == LABEL]
        metrics[name] = score(model, flexion)
        metrics[name]["by_subject"] = {
            subject: score(model, frame) for subject, frame in flexion.groupby("subject")
        }
        if name == "test":
            ood = subset[~subset.label.isin([0, LABEL])]
            background = subset[subset.label == 0]
            metrics["test_background"] = score(model, background)
            metrics["baseline_same_split"] = {
                "flexion": score(baseline, flexion), "other": score(baseline, ood),
                "background": score(baseline, background),
            }
            metrics["test"]["false_rejection_rate"] = metrics["test"]["rejection_rate"]
            positive = -model.decision_function(matrix(flexion))
            metrics["novelty_ranking"] = {}
            for key, frame in (("other_exercises", ood), ("background", background)):
                if len(frame):
                    negative = -model.decision_function(matrix(frame))
                    truth = np.r_[np.zeros(len(positive)), np.ones(len(negative))]
                    scores = np.r_[positive, negative]
                    metrics["novelty_ranking"][key] = {
                        "auroc": roc_auc_score(truth, scores),
                        "average_precision": average_precision_score(truth, scores),
                    }
            metrics["test_other_exercises"] = score(model, ood)
            metrics["test_other_exercises"]["by_label"] = {
                str(label): score(model, frame) for label, frame in ood.groupby("label")
            }
            held_out = [(model.decision_function(matrix(frame)), title)
                        for frame, title in ((flexion, "Healthy flexion"), (ood, "Other exercises"),
                                             (background, "Unstructured background")) if len(frame)]
            bins = np.histogram_bin_edges(np.concatenate([values for values, _ in held_out]), bins=25)
            for values, title in held_out:
                ax.hist(values, bins=bins, weights=np.full(len(values), 1 / len(values)),
                        histtype="step", linewidth=2, label=title)
    ax.axvline(0, color="black", linewidth=1)
    ax.set(xlabel="SVM decision score", ylabel="Fraction of class windows")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "evaluation.png", dpi=140)
    plt.close(fig)
    save_json(output / "evaluation.json", metrics)
    print(json.dumps(metrics, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("process", "train", "evaluate"))
    parser.add_argument("--dataset", type=Path, default=Path("../dataset"))
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACTS)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.command == "process":
        process(args.dataset, args.output)
    elif args.command == "train":
        train(args.output)
    else:
        evaluate(args.output)


if __name__ == "__main__":
    main()
