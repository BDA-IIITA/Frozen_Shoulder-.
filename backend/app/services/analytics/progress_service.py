from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Dict, Any, List, Optional
import datetime
from app.database.models import RehabilitationSession, ExerciseConfiguration, Patient

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

        latest_session = sessions[-1]
        best_rom = max(s.rom for s in sessions)
        total_reps = sum(s.repetitions for s in sessions)

        # Average smoothness / movement quality
        quality_scores = [s.smoothness_score for s in sessions if s.smoothness_score is not None]
        avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None

        # Compare with the most recent previous session OF THE SAME EXERCISE
        comparable_prev: Optional[RehabilitationSession] = None
        for s in reversed(sessions[:-1]):
            if s.exercise_key == latest_session.exercise_key:
                comparable_prev = s
                break

        rom_change = None
        rom_change_pct = None
        summary_text = ""

        if comparable_prev:
            rom_change = round(latest_session.rom - comparable_prev.rom, 1)
            if comparable_prev.rom > 0:
                rom_change_pct = round((rom_change / comparable_prev.rom) * 100.0, 1)

            if rom_change > 0:
                summary_text = (
                    f"Your recorded {latest_session.exercise_key.replace('_', ' ')} ROM changed from "
                    f"{comparable_prev.rom}° to {latest_session.rom}° (+{rom_change}°) across comparable sessions."
                )
            elif rom_change < 0:
                summary_text = (
                    f"Your recorded {latest_session.exercise_key.replace('_', ' ')} ROM measured {latest_session.rom}°, "
                    f"compared to {comparable_prev.rom}° in the prior session ({rom_change}° change)."
                )
            else:
                summary_text = (
                    f"Your recorded {latest_session.exercise_key.replace('_', ' ')} ROM remained stable at "
                    f"{latest_session.rom}° across the last two sessions."
                )
        else:
            summary_text = (
                f"Latest recorded session ({latest_session.exercise_key.replace('_', ' ')}) achieved {latest_session.rom}° ROM. "
                "Additional sessions are needed for comparative trend analysis."
            )

        # Format recent sessions list
        recent_list = []
        for s in reversed(sessions[-6:]):
            ex = db.query(ExerciseConfiguration).filter(ExerciseConfiguration.exercise_key == s.exercise_key).first()
            ex_name = ex.display_name if ex else s.exercise_key
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
                "status": s.status
            })

        return {
            "latest_rom": round(latest_session.rom, 1),
            "best_rom": round(best_rom, 1),
            "total_repetitions": total_reps,
            "total_sessions": total_sessions,
            "avg_movement_quality": avg_quality,
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

        sessions = query.order_by(RehabilitationSession.start_time.asc()).all()

        results = []
        for idx, s in enumerate(sessions, start=1):
            results.append({
                "session_id": s.id,
                "session_number": idx,
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
        if s_a.exercise_key != s_b.exercise_key:
            warnings.append(f"Exercises differ ({s_a.exercise_key} vs {s_b.exercise_key}). Angle comparisons are not directly equivalent.")
        if s_a.data_source != s_b.data_source:
            warnings.append(f"Data sources differ ({s_a.data_source.upper()} vs {s_b.data_source.upper()}). Direct numerical comparison is unreliable.")
        if s_a.affected_side != s_b.affected_side:
            warnings.append(f"Affected side differs ({s_a.affected_side} vs {s_b.affected_side}).")

        rom_diff = round(s_b.rom - s_a.rom, 1)
        rom_pct = round((rom_diff / s_a.rom) * 100.0, 1) if s_a.rom > 0 else None

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
                "data_source": s_b.data_source
            },
            "rom_difference": rom_diff,
            "rom_change_percentage": rom_pct,
            "repetitions_difference": s_b.repetitions - s_a.repetitions,
            "warnings": warnings,
            "is_comparable": len(warnings) == 0
        }
