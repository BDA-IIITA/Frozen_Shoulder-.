from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Dict, Any, List, Optional
import datetime
from app.database.models import RehabilitationSession, ExerciseConfiguration, Patient
from .performance import enrich_progress, within_sampling_band
from .session_metrics import saved_measurements

def same_movement_measure(first, second, *, count=False):
    if not first.get("angle_source") or first["angle_source"] != second.get("angle_source"):
        return False
    fallback = "exercise_projection"
    if (first.get("movement_metric") or fallback) != (second.get("movement_metric") or fallback):
        return False
    return not count or first.get("rep_peak_deg") == second.get("rep_peak_deg")


class ProgressAnalyticsService:
    """
    Computes recovery analytics, objective session comparisons,
    and factual, data-grounded progress summaries.
    """
    @staticmethod
    def get_dashboard_summary(db: Session, patient_id: int = 1) -> Dict[str, Any]:
        sessions = (
            db.query(RehabilitationSession)
            .filter(
                RehabilitationSession.patient_id == patient_id,
                RehabilitationSession.status == "completed"
            )
            .order_by(RehabilitationSession.start_time.asc())
            .all()
        )

        total_sessions = len(sessions)
        if total_sessions == 0:
            return {
                "latest_rom": 0.0,
                "best_rom": 0.0,
                "total_repetitions": 0,
                "total_sessions": 0,
                "avg_movement_quality": None,
                "rom_change_vs_prior": None,
                "rom_change_percentage": None,
                "recovery_summary_text": "No completed rehabilitation sessions recorded yet. Complete a session to begin tracking range-of-motion progress.",
                "recent_sessions": []
            }

        live_sessions = [s for s in sessions if s.data_source == "live"]
        total_reps = sum(s.repetitions for s in live_sessions)
        oriented = [s for s in live_sessions if (s.movement_analytics or {}).get("angle_source")]
        latest = oriented[-1] if oriented else None
        comparable = [s for s in oriented if latest and (
            s.exercise_key, s.affected_side, s.data_source
        ) == (latest.exercise_key, latest.affected_side, latest.data_source)
            and same_movement_measure(s.movement_analytics, latest.movement_analytics)]
        rom_change = rom_change_pct = None
        if len(comparable) > 1:
            prior = comparable[-2]
            rom_change = round(latest.rom - prior.rom, 1)
            if prior.rom > 0:
                rom_change_pct = round(100 * rom_change / prior.rom, 1)
            summary_text = f"Relative sensor excursion changed by {rom_change:+.1f}° from the prior comparable session."
        elif latest:
            summary_text = "A second comparable session is needed to calculate a change in sensor excursion."
        else:
            summary_text = "Sensor excursion is unavailable for the recorded sessions."

        # Format recent sessions list
        recent_list = []
        for s in reversed(sessions[-6:]):
            ex = db.query(ExerciseConfiguration).filter(ExerciseConfiguration.exercise_key == s.exercise_key).first()
            recording = (s.movement_analytics or {}).get("recording") or {}
            ex_name = recording.get("exercise_name") or (ex.display_name if ex else s.exercise_key)
            recent_list.append({
                "id": s.id,
                "date": s.start_time.strftime("%b %d, %Y %H:%M"),
                "exercise_key": s.exercise_key,
                "exercise_name": ex_name,
                "repetitions": s.repetitions,
                "rom": round(s.rom, 1),
                "max_angle": round(s.max_angle, 1),
                "min_angle": round(s.min_angle, 1),
                "duration_seconds": round(s.duration_seconds, 1),
                "smoothness_score": s.smoothness_score,
                "data_source": s.data_source,
                "movement_analytics": {
                    key: value for key, value in s.movement_analytics.items()
                    if key not in {"wrist_trace", "decision_scores", "decision_trace"}
                } if s.movement_analytics else None,
                "status": s.status
            })

        return {
            "latest_rom": round(latest.rom, 1) if latest else 0.,
            "best_rom": round(max(s.rom for s in comparable), 1) if comparable else 0.,
            "total_repetitions": total_reps,
            "total_sessions": len(live_sessions),
            "avg_movement_quality": None,
            "rom_change_vs_prior": rom_change,
            "rom_change_percentage": rom_change_pct,
            "recovery_summary_text": summary_text,
            "recent_sessions": recent_list
        }

    @staticmethod
    def get_rom_analytics(
        db: Session,
        patient_id: int = 1,
        exercise_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = (
            db.query(RehabilitationSession)
            .filter(
                RehabilitationSession.patient_id == patient_id,
                RehabilitationSession.status == "completed"
            )
        )
        if exercise_key and exercise_key != "all":
            query = query.filter(RehabilitationSession.exercise_key == exercise_key)

        sessions = query.order_by(RehabilitationSession.start_time.asc(), RehabilitationSession.id.asc()).all()

        results = []
        for idx, s in enumerate(sessions, start=1):
            measurements = saved_measurements(s)
            results.append({
                "session_id": s.id,
                "session_number": idx,
                "affected_side": s.affected_side,
                "movement_analytics": {
                    key: value for key, value in measurements.items()
                    if key not in {"wrist_trace", "decision_scores", "decision_trace"}
                } if measurements else None,
                "date": s.start_time.strftime("%Y-%m-%d"),
                "exercise_key": s.exercise_key,
                "rom": round(s.rom, 1),
                "max_angle": round(s.max_angle, 1),
                "min_angle": round(s.min_angle, 1),
                "repetitions": s.repetitions,
                "duration_seconds": round(s.duration_seconds, 1),
                "smoothness_score": s.smoothness_score,
                "data_source": s.data_source
            })
        enrich_progress(results)
        return results

    @staticmethod
    def get_weekly_activity(db: Session, patient_id: int = 1) -> List[Dict[str, Any]]:
        # Last 7 calendar days
        today = datetime.date.today()
        activity = []
        for i in range(6, -1, -1):
            day_date = today - datetime.timedelta(days=i)
            start_dt = datetime.datetime.combine(day_date, datetime.time.min)
            end_dt = datetime.datetime.combine(day_date, datetime.time.max)

            day_sessions = (
                db.query(RehabilitationSession)
                .filter(
                    RehabilitationSession.patient_id == patient_id,
                    RehabilitationSession.status == "completed",
                    RehabilitationSession.data_source == "live",
                    RehabilitationSession.start_time >= start_dt,
                    RehabilitationSession.start_time <= end_dt
                )
                .all()
            )

            activity.append({
                "day": day_date.strftime("%a"),
                "date": day_date.strftime("%b %d"),
                "sessions_count": len(day_sessions),
                "total_repetitions": sum(s.repetitions for s in day_sessions)
            })
        return activity

    @staticmethod
    def compare_sessions(db: Session, session_id_a: int, session_id_b: int) -> Dict[str, Any]:
        s_a = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id_a).first()
        s_b = db.query(RehabilitationSession).filter(RehabilitationSession.id == session_id_b).first()

        if not s_a or not s_b:
            raise ValueError("One or both sessions not found.")

        warnings = []
        if s_a.patient_id != s_b.patient_id:
            warnings.append("Sessions belong to different participants.")
        if s_a.exercise_key != s_b.exercise_key:
            warnings.append(f"Exercises differ ({s_a.exercise_key} vs {s_b.exercise_key}). Angle comparisons are not directly equivalent.")
        if s_a.data_source != s_b.data_source:
            warnings.append(f"Data sources differ ({s_a.data_source.upper()} vs {s_b.data_source.upper()}). Direct numerical comparison is unreliable.")
        a = saved_measurements(s_a) or {}
        b = saved_measurements(s_b) or {}
        if s_a.data_source == s_b.data_source == "replay":
            a_record, b_record = a.get("recording") or {}, b.get("recording") or {}
            if not a_record or any(a_record.get(key) != b_record.get(key) for key in ("participant", "side_code")):
                warnings.append("Replay participant or side code differs.")
            if not a.get("replay_complete") or not b.get("replay_complete"):
                warnings.append("Both replay sessions must contain complete recordings for comparison.")
        elif s_a.affected_side != s_b.affected_side:
            warnings.append(f"Affected side differs ({s_a.affected_side} vs {s_b.affected_side}).")

        measures = (
            "estimated_repetition_count", "movement_duration_s", "rep_duration_sd_s",
            "wrist_gyro_peak_rad_s", "wrist_jerk_rms_m_s3", "pain_rating", "stiffness_rating",
            "median_rep_peak_deg", "median_rep_excursion_deg", "mean_rep_duration_s", "peak_angle_sd_deg", "trunk_peak_deg",
            "coarse_wrist_jerk_rms_m_s3", "rep_wrist_gyro_mean_rad_s",
        )
        rep_measures = {"estimated_repetition_count", "movement_duration_s", "rep_duration_sd_s",
                        "median_rep_peak_deg", "median_rep_excursion_deg", "mean_rep_duration_s", "peak_angle_sd_deg", "trunk_peak_deg",
                        "coarse_wrist_jerk_rms_m_s3", "rep_wrist_gyro_mean_rad_s"}
        same_counter = (same_movement_measure(a, b, count=True)
                        and a.get("rep_count_protocol") == b.get("rep_count_protocol")
                        and a.get("sensor_device_id") == b.get("sensor_device_id"))
        comparable = not warnings
        changes = {
            key: round(b[key] - a[key], 4) for key in measures
            if comparable and a.get(key) is not None and b.get(key) is not None
            and (key not in rep_measures or s_a.data_source == "replay" or same_counter)
            and (key not in {"coarse_wrist_jerk_rms_m_s3", "rep_wrist_gyro_mean_rad_s"} or within_sampling_band(a, b))
        }
        if comparable and a.get("model_id") and a["model_id"] == b.get("model_id"):
            if a.get("mean_decision_score") is not None and b.get("mean_decision_score") is not None:
                changes["mean_decision_score"] = round(b["mean_decision_score"] - a["mean_decision_score"], 4)
        rom_diff = round(s_b.rom - s_a.rom, 1) if comparable and same_movement_measure(a, b) else None
        rom_pct = round((rom_diff / s_a.rom) * 100.0, 1) if rom_diff is not None and s_a.rom > 0 else None

        return {
            "session_a": {
                "id": s_a.id,
                "date": s_a.start_time.strftime("%b %d, %Y %H:%M"),
                "exercise_key": s_a.exercise_key,
                "rom": round(s_a.rom, 1),
                "max_angle": round(s_a.max_angle, 1),
                "min_angle": round(s_a.min_angle, 1),
                "repetitions": s_a.repetitions,
                "duration_seconds": round(s_a.duration_seconds, 1),
                "smoothness_score": s_a.smoothness_score,
                "movement_analytics": s_a.movement_analytics,
                "data_source": s_a.data_source
            },
            "session_b": {
                "id": s_b.id,
                "date": s_b.start_time.strftime("%b %d, %Y %H:%M"),
                "exercise_key": s_b.exercise_key,
                "rom": round(s_b.rom, 1),
                "max_angle": round(s_b.max_angle, 1),
                "min_angle": round(s_b.min_angle, 1),
                "repetitions": s_b.repetitions,
                "duration_seconds": round(s_b.duration_seconds, 1),
                "smoothness_score": s_b.smoothness_score,
                "movement_analytics": s_b.movement_analytics,
                "data_source": s_b.data_source
            },
            "rom_difference": rom_diff,
            "rom_change_percentage": rom_pct,
            "repetitions_difference": changes.get("estimated_repetition_count"),
            "movement_changes": changes,
            "warnings": warnings,
            "is_comparable": len(warnings) == 0
        }
