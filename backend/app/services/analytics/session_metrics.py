"""Reuse saved wrist traces and rep records for non-ML session measurements."""
from bisect import bisect_left, bisect_right
from math import isfinite
from statistics import median


def sampled_wrist_metrics(trace, repetitions):
    if len(trace) < 2:
        return {}
    clock = [point["time_s"] for point in trace]
    if any(not isfinite(t) for t in clock) or any(b <= a for a, b in zip(clock, clock[1:])):
        return {}
    intervals = [b - a for a, b in zip(clock, clock[1:])]
    result = {"wrist_sample_interval_median_s": round(median(intervals), 4)}
    integral = duration = 0.
    for rep in repetitions:
        start, end = rep["start_s"], rep["end_s"]
        points = trace[bisect_left(clock, start - .005):bisect_right(clock, end + .005)]
        rep_integral = covered = 0.
        count = 0
        for first, last in zip(points, points[1:]):
            dt = last["time_s"] - first["time_s"]
            a, b = first["gyro_rad_s"], last["gyro_rad_s"]
            if .15 <= dt <= 1.25 and isfinite(a) and isfinite(b) and min(a, b) >= 0:
                covered += dt
                rep_integral += dt * (a + b) / 2
                count += 1
        if count >= 3 and covered >= .60 * (end - start):
            integral += rep_integral
            duration += covered
    if duration:
        result["rep_wrist_gyro_mean_rad_s"] = round(integral / duration, 4)
    return result


def saved_measurements(session):
    payload = session.movement_analytics
    if not payload:
        return payload
    result = dict(payload)
    if session.data_source == "live":
        if "wrist_sample_interval_median_s" not in payload:
            result.update(sampled_wrist_metrics(payload.get("wrist_trace") or [], payload.get("repetition_timeline") or []))
        if payload.get("estimated_repetition_count", 0) and session.avg_rep_duration is not None:
            result.setdefault("mean_rep_duration_s", session.avg_rep_duration)
        review = payload.get("repetition_review") or {}
        if review.get("completed") == review.get("required") == payload.get("estimated_repetition_count") == 3:
            result.setdefault("median_rep_peak_deg", review.get("median_peak_deg"))
    return result
