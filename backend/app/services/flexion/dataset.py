"""Chunked SPARS9x inspection and boundary-preserving recording extraction."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .signal import LABEL, WINDOW, valid_wrist

OTHER_EXERCISES = {2, 6, 7, 9, 10}
WRIST = [0, 1, 2, 6, 7, 8]


@dataclass
class Recording:
    subject: str
    side: int
    label: int
    start: int
    wrist: np.ndarray


def chunks(path, size=100_000):
    offset = 0
    with path.open() as source:
        if len(source.readline().rstrip().split(",")) != 12:
            raise ValueError(f"{path}: expected 12 headerless columns")
    for frame in pd.read_csv(path, header=None, chunksize=size, skip_blank_lines=False):
        if frame.shape[1] != 12:
            raise ValueError(f"{path}: expected 12 columns")
        numeric = frame.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        yield offset, numeric
        offset += len(numeric)


def counts(values, counter):
    unique, frequencies = np.unique(values, return_counts=True)
    counter.update({str(value): int(n) for value, n in zip(unique, frequencies)})


def recordings(path: Path, report, size=100_000, *, background=None, exercise_labels=OTHER_EXERCISES | {LABEL}):
    labels, sides, transitions, bouts = (Counter() for _ in range(4))
    rows = invalid_wrist = 0
    missing = np.zeros(12, dtype=np.int64)
    infinite = missing.copy()
    minimum = np.full(12, np.inf)
    maximum = -minimum
    previous = None
    raw_bout_start = 0
    pending = []
    pending_key = None
    pending_stop = None
    for offset, data in chunks(path, size):
        rows += len(data)
        missing += np.isnan(data).sum(axis=0)
        infinite += np.isinf(data).sum(axis=0)
        finite = np.isfinite(data)
        minimum = np.minimum(minimum, np.where(finite, data, np.inf).min(axis=0))
        maximum = np.maximum(maximum, np.where(finite, data, -np.inf).max(axis=0))
        side, label = data[:, 10], data[:, 11]
        counts(label, labels)
        counts(side, sides)
        key = np.where(np.isfinite(data[:, 10:12]), data[:, 10:12], -999)
        starts = np.r_[0, np.flatnonzero(np.any(key[1:] != key[:-1], axis=1)) + 1]
        for index, start in enumerate(starts):
            current = tuple(key[start])
            if current != previous:
                raw_bout_start = offset + start
                bouts[f"{current[1]}:{current[0]}"] += 1
                if previous and previous[1] != current[1]:
                    transitions[f"{previous[1]}->{current[1]}"] += 1
            previous = current
            if background is not None and current == (0., 0.):
                # One four-second probe per 100 seconds, on an absolute row grid.
                stop = starts[index + 1] if index + 1 < len(starts) else len(data)
                interval = 5000
                first = (-offset - start) % interval + start
                for position in range(first, stop - WINDOW + 1, interval):
                    raw = data[position:position + WINDOW, WRIST]
                    if valid_wrist(raw).all():
                        background(path.stem, int(raw_bout_start), offset + position, raw)

        wrist = data[:, WRIST]
        valid = valid_wrist(wrist)
        invalid_wrist += int((~valid).sum())
        selected = np.flatnonzero(valid & np.isin(label, list(exercise_labels))
                                  & np.isin(side, [1, 2]))
        selected_groups = np.split(selected, np.flatnonzero(
            (np.diff(selected) != 1) |
            (np.diff(side[selected]) != 0) |
            (np.diff(label[selected]) != 0)
        ) + 1)
        for indices in selected_groups:
            if not len(indices):
                continue
            start, stop = offset + indices[0], offset + indices[-1] + 1
            current = (int(side[indices[0]]), int(label[indices[0]]))
            if pending and (start != pending_stop or current != pending_key):
                yield Recording(path.stem, *pending_key, int(pending_start), np.concatenate(pending))
                pending.clear()
            if not pending:
                pending_start, pending_key = start, current
            pending.append(wrist[indices])
            pending_stop = stop
        if pending and pending_stop != offset + len(data):
            yield Recording(path.stem, *pending_key, int(pending_start), np.concatenate(pending))
            pending.clear()
    if pending:
        yield Recording(path.stem, *pending_key, int(pending_start), np.concatenate(pending))
    report.update(rows=rows, labels=dict(labels), sides=dict(sides), bouts=dict(bouts),
                  label_transitions=dict(transitions), nan_by_column=missing.tolist(),
                  infinite_by_column=infinite.tolist(), invalid_wrist_rows=invalid_wrist,
                  min_by_column=[float(v) if np.isfinite(v) else None for v in minimum],
                  max_by_column=[float(v) if np.isfinite(v) else None for v in maximum])
