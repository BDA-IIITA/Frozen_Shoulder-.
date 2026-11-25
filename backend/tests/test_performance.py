import pytest

from app.services.analytics.performance import configured_weights, enrich_progress, score_index
from app.services.analytics.session_metrics import sampled_wrist_metrics


def session(number, *, date=None, exercise="flexion", side="right", source="live", patient=1, **metrics):
    data = dict(angle_source="wrist", movement_metric="total_tilt", rep_peak_deg=15,
                estimated_repetition_count=4, median_rep_excursion_deg=60, neutral_calibrated=True,
                rep_count_protocol="adaptive-return-v1", sensor_device_id="test-device",
                peak_angle_sd_deg=4, rep_duration_sd_s=.4, trunk_peak_deg=10,
                coarse_wrist_jerk_rms_m_s3=2, wrist_sample_interval_median_s=.6)
    data.update(metrics)
    return dict(session_id=number, patient_id=patient, date=date or f"2026-11-{number:02}",
                exercise_key=exercise, affected_side=side, data_source=source, movement_analytics=data)


def test_weighted_formula_and_missing_components():
    weights = configured_weights(raw="")
    assert score_index({"mobility": 80, "control": 60, "posture": 40, "symptoms": 50}, weights) == {
        "score": 63., "coverage": 1., "partial": False}
    assert score_index({"control": 40, "posture": 60}, weights) == {
        "score": 47.5, "coverage": .4, "partial": True}
    assert score_index({"mobility": 90}, weights)["score"] is None
    assert score_index({"posture": 90, "symptoms": 90}, weights)["score"] is None
    assert configured_weights('{"mobility":2,"control":2,"posture":2,"symptoms":2}')["control"] == .25
    with pytest.raises(ValueError):
        configured_weights('{"mobility":0}')


def test_baseline_absolute_deltas_and_comparable_score():
    rows = [session(index, pain_rating=5-index) for index in range(1, 4)]
    rows.append(session(4, median_rep_excursion_deg=80, prescribed_angle_deg=100,
                        prescribed_repetitions=5, pain_rating=1,
                        peak_angle_sd_deg=2, rep_duration_sd_s=.2, trunk_peak_deg=5,
                        coarse_wrist_jerk_rms_m_s3=1))
    enrich_progress(rows)
    result = rows[-1]["rehab_progress"]
    assert result["baseline_session_ids"] == [1, 2, 3]
    assert result["rep_completion"] == .8
    assert result["compared"]["median_rep_excursion_deg"] == {"baseline": 60, "current": 80, "change": 20, "unit": "°"}
    assert result["compared"]["pain_rating"]["change"] == -2
    assert result["compared"]["coarse_wrist_jerk_rms_m_s3"]["change"] == -1
    assert result["components"] == {"mobility": 80, "control": 66.7, "posture": 66.7, "symptoms": 90}
    assert result["baseline_score"] == 58
    assert result["score_change"] == 18.7


def test_protocol_patient_side_exercise_and_source_separation():
    rows = [session(1, neutral_calibrated=False), session(2), session(3, side="left"),
            session(4, exercise="abduction"), session(5, source="replay"),
            session(6, patient=2), session(7, rep_peak_deg=30), session(8)]
    enrich_progress(rows)
    assert rows[0]["rehab_progress"]["eligible"] is False
    assert "rehab_progress" not in rows[4]
    progress = rows[-1]["rehab_progress"]
    assert progress["baseline_session_ids"] == [2, 8]
    assert progress["baseline_ready"] is False
    assert progress["score"] is None


def test_conservative_trend_and_rate_mismatch():
    rows = [session(index) for index in range(1, 4)]
    rows.extend(session(n, median_rep_excursion_deg=70, wrist_sample_interval_median_s=.2) for n in (4, 5, 6))
    enrich_progress(rows)
    assert rows[-2]["rehab_progress"]["mobility_trend"] == "insufficient"
    result = rows[-1]["rehab_progress"]
    assert result["mobility_trend"] == "improving"
    assert "coarse_wrist_jerk_rms_m_s3" not in result["component_metrics"]["control"]
    assert rows[0]["rehab_progress"]["is_baseline_session"]


def test_sampled_wrist_speed_is_time_weighted_and_gaps_are_excluded():
    times = [0, .5, 1, 2, 2.5, 5, 5.5]
    trace = [{"time_s": t, "gyro_rad_s": t} for t in times]
    result = sampled_wrist_metrics(trace, [{"start_s": 0, "end_s": 2.5}, {"start_s": 2.5, "end_s": 5.5}])
    assert result["wrist_sample_interval_median_s"] == .5
    assert result["rep_wrist_gyro_mean_rad_s"] == pytest.approx(1.25)


def test_aggregation_weights_days_equally_and_excludes_other_score_definitions():
    from app.services.analytics.performance import aggregate_scores

    rows = []
    for day, score, definition in [
        ("2026-11-02", 30, "A"), ("2026-11-02", 40, "A"), ("2026-11-02", 50, "A"),
        ("2026-11-03", 60, "A"), ("2026-11-04", 24, "B"),
    ]:
        rows.append({"date": day, "rehab_progress": {"score": score, "score_comparison_key": definition}})
    aggregate_scores(rows)
    scores = [row["rehab_progress"] for row in rows]
    assert scores[0]["daily_score"] == 40
    assert scores[3]["daily_score"] == 60
    assert scores[3]["weekly_score"] == 50
    assert scores[4]["weekly_score"] == scores[4]["daily_score"] == 24
