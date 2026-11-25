"""Low-rate change in wrist acceleration magnitude over completed reps."""

from bisect import bisect_left, bisect_right
from math import isfinite, sqrt


def coarse_wrist_jerk(trace, repetitions):
    """Time-weighted RMS of adjacent magnitude slopes within covered reps.

    This is a coarse scalar estimate from the saved chart samples. It cannot
    capture high-frequency motion or changes in acceleration direction.
    """
    times = [point["time_s"] for point in trace]
    if any(not isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        return {}
    energy = duration = 0.
    covered_reps = 0
    for rep in repetitions:
        start, end = rep["start_s"], rep["end_s"]
        if end <= start:
            continue
        points = trace[bisect_left(times, start - .005):bisect_right(times, end + .005)]
        rep_energy = rep_duration = 0.
        intervals = 0
        for first, second in zip(points, points[1:]):
            dt = second["time_s"] - first["time_s"]
            a, b = first["acceleration_m_s2"], second["acceleration_m_s2"]
            if .15 <= dt <= 1.25 and isfinite(a) and isfinite(b):
                intervals += 1
                rep_energy += (b - a) ** 2 / dt
                rep_duration += dt
        if intervals >= 3 and rep_duration >= .60 * (end - start):
            covered_reps += 1
            energy += rep_energy
            duration += rep_duration
    return {
        "coarse_wrist_jerk_rms_m_s3": round(sqrt(energy / duration), 3),
        "coarse_wrist_jerk_covered_reps": covered_reps,
        "coarse_wrist_jerk_coverage_s": round(duration, 3),
    } if covered_reps else {}
