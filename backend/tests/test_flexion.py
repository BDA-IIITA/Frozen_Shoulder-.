import joblib
import numpy as np
import pytest
import sklearn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from app.services.flexion.dataset import chunks, recordings
from app.services.flexion.inference import FlexionReference, WristSession
from app.services.flexion.offline import participant_split
from app.services.flexion.signal import (
    FEATURES, FS, SCHEMA, WINDOW, candidate_reps, features, filter_wrist,
)


def test_csv_boundaries_and_missing_values(tmp_path):
    path = tmp_path / "spars9x_s0.csv"
    data = np.zeros((13, 12))
    data[:, 10:] = [1, 8]
    data[5, 0] = np.nan
    data[7, 11] = 3
    data[9:11, 10] = 2
    data[11:, 11] = 6
    np.savetxt(path, data, delimiter=",")
    assert [offset for offset, _ in chunks(path, 4)] == [0, 4, 8, 12]
    report = {}
    bouts = list(recordings(path, report, size=4))
    assert [(b.start, len(b.wrist), b.side, b.label) for b in bouts] == [
        (0, 5, 1, 8), (6, 1, 1, 8), (8, 1, 1, 8), (9, 2, 2, 8), (11, 2, 1, 6),
    ]
    assert {b.subject for b in bouts} == {"spars9x_s0"}
    assert report["invalid_wrist_rows"] == 1
    assert report["label_transitions"] == {"8.0->3.0": 1, "3.0->8.0": 1, "8.0->6.0": 1}
    path.write_text("1,2,3\n")
    with pytest.raises(ValueError, match="12"):
        list(chunks(path))


def test_filter_lowpass_and_causal_state():
    clock = np.arange(250) / FS
    raw = np.zeros((len(clock), 6))
    raw[:, 0] = np.sin(2 * np.pi * clock)
    raw[:, 3] = np.sin(2 * np.pi * 15 * clock)
    filtered, _ = filter_wrist(raw)
    assert np.std(filtered[30:-30, 0] - raw[30:-30, 0]) < .01
    assert np.std(filtered[30:-30, 3]) < .01
    full, _ = filter_wrist(raw, causal=True)
    left, state = filter_wrist(raw[:100], causal=True)
    right, _ = filter_wrist(raw[100:], causal=True, state=state)
    assert np.allclose(np.vstack((left, right)), full)
    assert np.isfinite(filter_wrist(raw[:3])[0]).all()


def test_candidate_repetition_requires_return():
    theta = np.r_[np.zeros(30), np.linspace(0, 1.5, 80), np.linspace(1.5, 0, 80), np.zeros(30)]
    wrist = np.zeros((len(theta), 6))
    wrist[:, 0] = 9.81 * np.sin(theta)
    wrist[:, 2] = 9.81 * np.cos(theta)
    wrist[:, 4] = np.gradient(theta) * FS
    filtered, _ = filter_wrist(wrist)
    [(start, peak, stop)] = candidate_reps(filtered)
    assert 30 < start < peak < stop < 190
    assert candidate_reps(filtered[:160]) == []


def test_feature_units_and_stable_order():
    raw = np.tile([0., 0., 9.81, 0., 3., 4.], (WINDOW, 1))
    vector = features(raw)
    assert len(vector) == len(FEATURES)
    assert vector == pytest.approx([9.81, 0, 9.81, 5, 5, 5, 4, 0, 0])


def test_participant_split():
    ids = [str(n) for n in range(10)] * 2
    split = participant_split(ids)
    train, validation, test = map(set, split.values())
    assert list(map(len, (train, validation, test))) == [6, 2, 2]
    assert len(train | validation | test) == 10
    assert split == participant_split(reversed(ids))
    with pytest.raises(ValueError):
        participant_split(["one", "two"])


def test_persistence_and_live_feature_parity(tmp_path):
    wrist = np.tile([0., 0., 9.81, 0., 3., 4.], (WINDOW, 1))
    vector = features(wrist)
    rng = np.random.default_rng(2)
    model = make_pipeline(StandardScaler(), OneClassSVM()).fit(vector + rng.normal(size=(32, len(vector))))
    path = tmp_path / "model.joblib"
    joblib.dump(dict(model=model, schema=SCHEMA, scikit_learn=sklearn.__version__), path)
    reference = FlexionReference()
    reference.load(path)
    expected = model.decision_function([vector])[0]
    tracker = WristSession("flexion", reference)
    for idx in range(1050):
        tracker.add(idx * .05, "device", None)
    assert tracker.summary()["status"] == "wrist_data_unavailable"
    assert tracker.summary()["wrist_sample_count"] == 0
    for idx in range(WINDOW):
        tracker.add(60 + idx * .05, "device", wrist[idx])
    assert tracker.summary()["buffered_wrist_samples"] == 1
    assert tracker.summary()["last_wrist_interval_s"] == pytest.approx(.05)
    assert tracker.summary()["scored_windows"] == 0

    tracker = WristSession("flexion", reference)
    for idx, sample in enumerate(wrist):
        tracker.add(idx / FS, "device", sample)
    tracker.complete_rep(0, (WINDOW - 1) / FS)
    summary = tracker.summary(include_scores=True)
    assert summary["decision_scores"] == pytest.approx([expected])
    assert summary["latest_prediction"] == model.predict([vector])[0]
    assert list(summary["wrist_features"].values()) == pytest.approx(vector)
    assert list(summary["last_rep_features"].values()) == pytest.approx(vector)
    reference.load(tmp_path / "absent.joblib")
    assert reference.predict(vector) is None


def test_live_gap_and_missing_model():
    tracker = WristSession("flexion", FlexionReference())
    row = np.array([0., 0., 9.81, 0., 0., 0.])
    for idx in range(WINDOW - 1):
        tracker.add(idx / FS, "device", row)
    tracker.add(4, "device", None)
    tracker.add(4.02, "device", row)
    assert tracker.summary()["windows"] == 0
    for idx in range(2, WINDOW + 1):
        tracker.add(4 + idx / FS, "device", row)
    assert tracker.summary()["windows"] == 1
    assert tracker.summary()["status"] == "model_unavailable"
    assert tracker.summary()["outlier_windows"] is None


def test_signed_gyro_cycle_estimates_and_abstention():
    from app.services.flexion.repetitions import estimate_cycles

    clock = np.arange(20 * FS) / FS
    theta = .8 * (1 - np.cos(2 * np.pi * clock / 2))
    raw = np.column_stack((9.81 * np.sin(theta), clock * 0, 9.81 * np.cos(theta),
                           clock * 0, .8 * np.pi * np.sin(np.pi * clock), clock * 0))
    estimate = estimate_cycles(filter_wrist(raw)[0])
    assert estimate.period_s == pytest.approx(2, abs=.12)
    assert estimate.count == 9  # Complete same-phase intervals between ten signed peaks.
    assert all(a < b < c for a, b, c in estimate.bounds)
    assert estimate_cycles(np.tile([0., 0., 9.81, 0., 0., 0.], (1000, 1))).count is None
    assert estimate_cycles(raw[:200]).count is None


def test_expansion_holdout_is_new_and_disjoint():
    from app.services.flexion.offline import study_split

    subjects = [f"spars9x_s{i}" for i in range(20)]
    split = study_split(subjects)
    assert [len(value) for value in split.values()] == [12, 4, 4]
    assert all(int(value.rsplit("_s", 1)[1]) >= 10 for value in split["test"])
    assert len(set(sum(split.values(), []))) == 20


def test_real_prepared_bout_matches_exported_features_and_reference():
    import pandas as pd
    from app.services.flexion.replay import DEFAULT_ARTIFACTS, load_recording

    path = DEFAULT_ARTIFACTS / "features.csv"
    if not path.exists():
        pytest.skip("Run offline process and train to generate the real-data fixtures")
    key = "spars9x_s10_15108"
    try:
        metadata, raw = load_recording(key, samples=True)
    except FileNotFoundError:
        pytest.skip("This check uses the 20-participant release")
    exported = pd.read_csv(path).query(
        "subject == @subject and bout_start == @start",
        local_dict={"subject": metadata["participant"], "start": metadata["start_row"]},
    ).sort_values("start")
    reference = FlexionReference()
    reference.load(DEFAULT_ARTIFACTS / "flexion.joblib")
    if not reference.model:
        pytest.skip("Run offline train to generate the reference artifact")
    tracker = WristSession("flexion", reference)
    for index, row in enumerate(raw):
        tracker.add(index / FS, key, row)
        if (index + 1) % WINDOW == 0:
            window = (index + 1) // WINDOW - 1
            offline_row = exported.iloc[window][list(FEATURES)].to_numpy(float)
            summary = tracker.summary()
            np.testing.assert_allclose(list(summary["wrist_features"].values()), offline_row)
            sign, score = reference.predict(offline_row)
            assert summary["latest_prediction"] == sign
            assert summary["latest_decision_score"] == pytest.approx(score)
    assert tracker.windows == len(exported) == 6


def test_live_rep_excursion_tolerates_one_missing_packet_in_long_rep():
    from app.services.flexion.live_rep_reference import rep_excursion

    times = np.arange(11) * .6
    gyro = np.sin(2 * np.pi * times / times[-1])
    samples = np.column_stack((times, gyro, np.zeros((len(times), 2))))
    with_gap = np.delete(samples, 4, axis=0)
    assert rep_excursion(with_gap) == pytest.approx(rep_excursion(samples), rel=.15)
    assert rep_excursion(np.delete(samples, [4, 5], axis=0)) is None
    assert rep_excursion(np.delete(samples[:6], 2, axis=0)) is None
