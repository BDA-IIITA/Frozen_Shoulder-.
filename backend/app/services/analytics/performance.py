"""Personal, experimental rehabilitation index. All inputs are session measurements."""

import json
import math
import os
from statistics import median
from datetime import date, timedelta

WEIGHTS = {"mobility": .40, "control": .25, "posture": .15, "symptoms": .20}
UNITS = {
    "median_rep_excursion_deg": "°", "median_rep_peak_deg": "°", "rep_duration_sd_s": "s", "mean_rep_duration_s": "s",
    "peak_angle_sd_deg": "°", "trunk_peak_deg": "°", "pain_rating": "/10", "stiffness_rating": "/10",
    "wrist_jerk_rms_m_s3": "m/s³", "coarse_wrist_jerk_rms_m_s3": "m/s³",
    "rep_wrist_gyro_mean_rad_s": "rad/s", "estimated_repetition_count": "reps",
}


def configured_weights(raw=None):
    raw = os.environ.get("SHOULDERSENSE_PERFORMANCE_WEIGHTS") if raw is None else raw
    if not raw:
        return WEIGHTS.copy()
    try:
        values = json.loads(raw)
        if (not isinstance(values, dict) or values.keys() != WEIGHTS.keys()
                or any(type(w) not in (int, float) or not math.isfinite(w) or w <= 0 for w in values.values())
                or not math.isfinite(sum(values.values()))):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("Performance weights must be positive finite numbers for mobility, control, posture and symptoms") from exc
    total = sum(values.values())
    return {key: values[key] / total for key in WEIGHTS}


def metric(data, key):
    value = data.get(key)
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def personal_normalization(value, baseline, *, lower=False):
    """Bounded ratio with 50 at baseline and no invented physical cutoff."""
    if value == baseline:
        return 50.
    return 100 * (baseline if lower else value) / (value + baseline)


def target_completion(count, target):
    return None if count is None or not target else count / target


def components_for(current, anchor, inputs, target):
    scores = {}
    for name, keys in inputs.items():
        parts = []
        for key in keys:
            value = metric(current, key)
            if name == "symptoms":
                parts.append(100 - 10 * value)
            elif name == "mobility" and target:
                parts.append(min(100., 100 * value / target))
            else:
                parts.append(personal_normalization(value, anchor[key], lower=name != "mobility"))
        scores[name] = sum(parts) / len(parts)
    return scores


def score_index(components, weights):
    coverage = sum(weights[key] for key in components)
    enough = len(components) >= 2 and coverage + 1e-9 >= .40 and bool(
        {"mobility", "control", "posture"} & components.keys()
    )
    score = sum(weights[key] * value for key, value in components.items()) / coverage if enough else None
    return {"score": round(score, 1) if score is not None else None,
            "coverage": round(coverage, 4), "partial": len(components) < len(weights)}


def valid_live(data):
    return bool(data.get("angle_source") and data.get("movement_metric")
                and data.get("neutral_calibrated") is True
                and data.get("rep_count_protocol") and data.get("sensor_device_id")
                and (metric(data, "estimated_repetition_count") or 0) >= 2)


def protocol(row):
    data = row["movement_analytics"] or {}
    return (row.get("patient_id"), row["exercise_key"], row["affected_side"], data.get("angle_source"),
            data.get("movement_metric"), data.get("rep_peak_deg"),
            data.get("rep_count_protocol"), data.get("sensor_device_id"))


def within_sampling_band(current, reference):
    a = metric(current, "wrist_sample_interval_median_s")
    b = metric(reference, "wrist_sample_interval_median_s")
    return a is not None and b is not None and a > 0 and b > 0 and max(a, b) / min(a, b) <= 1.25


def common_measurements(current, baseline):
    shared = {}
    for key in UNITS:
        if not baseline or metric(current, key) is None:
            continue
        if any(metric(item, key) is None or (key in ("pain_rating", "stiffness_rating") and metric(item, key) > 10) for item in baseline):
            continue
        if key in ("coarse_wrist_jerk_rms_m_s3", "rep_wrist_gyro_mean_rad_s") and not all(
                within_sampling_band(current, item) for item in baseline):
            continue
        shared[key] = [metric(item, key) for item in baseline]
    return shared


def mobility_trend(row, prior, baseline, shared):
    """Require three distinct follow-up days and non-overlapping observed ranges."""
    key = "median_rep_excursion_deg"
    if key not in shared:
        return "insufficient"
    by_date = {}
    for item in [*prior, row]:
        if item["date"] <= baseline[-1]["date"]:
            continue
        angle = metric(item["movement_analytics"], key)
        if angle is not None:
            by_date.setdefault(item["date"], []).append(angle)
    if row["date"] not in by_date or len(by_date) < 3:
        return "insufficient"
    recent = [median(angles) for angles in list(by_date.values())[-3:]]
    anchor = shared[key]
    if min(recent) > max(anchor):
        return "improving"
    if max(recent) < min(anchor):
        return "declining"
    if all(min(anchor) <= value <= max(anchor) for value in recent):
        return "stable"
    return "inconclusive"


def enrich_progress(rows, weights=None):
    """Attach live-only comparisons to chronologically ordered analytics rows."""
    weights = configured_weights() if weights is None else weights
    cohorts = {}
    for row in rows:
        data = row["movement_analytics"] or {}
        if row["data_source"] == "live" and valid_live(data):
            cohorts.setdefault(protocol(row), []).append(row)
        elif row["data_source"] == "live":
            row["rehab_progress"] = {
                "eligible": False, "baseline_session_ids": [],
                "rep_completion": target_completion(metric(data, "estimated_repetition_count"),
                                                    metric(data, "prescribed_repetitions")),
            }

    for history in cohorts.values():
        annotate_cohort(history, weights)
        aggregate_scores(history)


def annotate_cohort(history, weights):
    for position, row in enumerate(history):
        data = row["movement_analytics"]
        baseline_rows = history[:3]
        ready = len(baseline_rows) == 3
        is_baseline = any(item["session_id"] == row["session_id"] for item in baseline_rows)
        baseline = [item["movement_analytics"] for item in baseline_rows] if ready else []
        shared = common_measurements(data, baseline)
        anchor = {key: median(values) for key, values in shared.items()}
        target = metric(data, "prescribed_angle_deg")
        inputs = {}
        if metric(data, "median_rep_excursion_deg") is not None and (target or "median_rep_excursion_deg" in shared):
            inputs["mobility"] = ["median_rep_excursion_deg"]
        control = [key for key in ("peak_angle_sd_deg", "rep_duration_sd_s") if key in shared]
        jerk = next((key for key in ("wrist_jerk_rms_m_s3", "coarse_wrist_jerk_rms_m_s3") if key in shared), None)
        if jerk:
            control.append(jerk)
        if control:
            inputs["control"] = control
        if "trunk_peak_deg" in shared:
            inputs["posture"] = ["trunk_peak_deg"]
        symptoms = [key for key in ("pain_rating", "stiffness_rating") if
                    metric(data, key) is not None and metric(data, key) <= 10]
        if symptoms:
            inputs["symptoms"] = symptoms
        components = components_for(data, anchor, inputs, target)
        result = score_index(components, weights)
        comparable_score = None
        if result["score"] is not None and ready and all(key in shared for keys in inputs.values() for key in keys):
            baseline_scores = [score_index(components_for(item, anchor, inputs, target), weights)["score"]
                               for item in baseline]
            comparable_score = round(median(baseline_scores), 1)
        row["rehab_progress"] = {
            "eligible": True,
            "baseline_session_ids": [item["session_id"] for item in baseline_rows],
            "baseline_ready": ready,
            "is_baseline_session": is_baseline,
            "compared": {key: {"baseline": round(value, 4), "current": metric(data, key),
                               "change": round(metric(data, key) - value, 4), "unit": UNITS[key]}
                         for key, value in anchor.items()},
            "mobility_trend": mobility_trend(row, history[3:position], baseline_rows, shared) if ready and not is_baseline else "insufficient",
            "components": {key: round(value, 1) for key, value in components.items()},
            "component_metrics": inputs, "weights": weights,
            "measurement_protocol_key": json.dumps(protocol(row)),
            "score_comparison_key": json.dumps([protocol(row), inputs, target], sort_keys=True),
            **result,
            "baseline_score": comparable_score,
            "score_change": round(result["score"] - comparable_score, 1) if comparable_score is not None else None,
            "rep_completion": target_completion(metric(data, "estimated_repetition_count"),
                                                metric(data, "prescribed_repetitions")),
        }


def aggregate_scores(history):
    days = {}
    for row in history:
        progress = row["rehab_progress"]
        if progress["score"] is not None:
            key = (progress["score_comparison_key"], row["date"])
            days.setdefault(key, []).append(progress)
    weeks = {}
    for (protocol_key, day), points in days.items():
        day_score = median(point["score"] for point in points)
        parsed_day = date.fromisoformat(day)
        monday = (parsed_day - timedelta(days=parsed_day.weekday())).isoformat()
        weeks.setdefault((protocol_key, monday), []).append(day_score)
        for point in points:
            point.update(daily_score=round(day_score, 1), week_start=monday)
    for (protocol_key, _), points in days.items():
        for point in points:
            point["weekly_score"] = round(median(weeks[protocol_key, point["week_start"]]), 1)
