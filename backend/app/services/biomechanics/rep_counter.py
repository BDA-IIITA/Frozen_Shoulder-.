import numpy as np
from typing import List, Dict, Any, Optional

class RepetitionCounter:
    """
    Finite State Machine for real-time repetition tracking and movement consistency
    extraction for shoulder rehabilitation exercises.
    
    States:
      - REST: Arm resting near starting threshold.
      - ASCENT: Arm actively moving upward beyond threshold_up.
      - PEAK_HOLD: Peak reached and turning downwards.
      - DESCENT: Arm moving downward toward starting threshold.
    """
    def __init__(
        self,
        threshold_up: float = 40.0,
        threshold_down: float = 20.0,
        min_rep_duration: float = 1.0,
        exercise_key: str = "flexion"
    ):
        self.threshold_up = threshold_up
        self.threshold_down = threshold_down
        self.adaptive_return = False
        self.min_rep_duration = min_rep_duration
        self.exercise_key = exercise_key

        # State tracking
        self.state: str = "REST"
        self.rep_count: int = 0
        self.rest_seen = False
        self.rest_angle = None
        self.current_rep_start_time: Optional[float] = None
        self.current_rep_peak_angle: float = 0.0
        self.current_rep_min_angle: float = 999.0

        # Session global metrics
        self.session_min_angle: float = 999.0
        self.session_max_angle: float = 0.0
        
        # Per-repetition history records
        self.completed_reps_info: List[Dict[str, float]] = []

    def reset(self):
        self.reset_partial()
        self.rep_count = 0
        self.session_min_angle = 999.0
        self.session_max_angle = 0.0
        self.completed_reps_info.clear()

    def reset_partial(self):
        self.state = "REST"
        self.rest_seen = False
        self.rest_angle = None
        self.current_rep_start_time = None
        self.current_rep_peak_angle = 0.0
        self.current_rep_min_angle = 999.0

    @property
    def ascent_floor(self):
        return max(self.threshold_down, self.rest_angle) if self.adaptive_return and self.rest_angle is not None else self.threshold_down

    @property
    def required_peak(self):
        return self.threshold_up + max(0., self.ascent_floor - self.threshold_down)

    @property
    def return_limit(self):
        if not self.adaptive_return:
            return self.threshold_down
        return max(self.ascent_floor, self.current_rep_peak_angle / 3)

    def process_sample(self, angle: float, timestamp: float) -> Dict[str, Any]:
        """
        Updates the repetition state machine with a new angle reading.
        Returns the updated repetition count, state, and current ROM.
        """
        rep_just_completed = False
        
        # Update session global boundaries
        if angle < self.session_min_angle:
            self.session_min_angle = angle
        if angle > self.session_max_angle:
            self.session_max_angle = angle

        # State Machine Transitions
        if self.state == "REST":
            if angle <= self.threshold_down:
                self.rest_seen = True
            if self.rest_seen:
                self.rest_angle = angle if self.rest_angle is None else min(angle, self.rest_angle)
            if self.rest_seen and angle > self.ascent_floor + 2.0:
                self.state = "ASCENT"
                self.current_rep_start_time = timestamp
                self.current_rep_peak_angle = angle
                self.current_rep_min_angle = min(self.current_rep_min_angle, angle)

        elif self.state == "ASCENT":
            if angle > self.current_rep_peak_angle:
                self.current_rep_peak_angle = angle

            if angle <= self.ascent_floor and self.current_rep_peak_angle < self.required_peak:
                self.reset_partial()
                self.rest_seen = True
                self.rest_angle = angle
            # A return below the lower threshold also confirms descent on sparse streams.
            elif self.current_rep_peak_angle >= self.required_peak and (angle <= self.return_limit or self.current_rep_peak_angle - angle > 3.0):
                self.state = "DESCENT"

        if self.state == "DESCENT":
            # If it continues dropping back down to threshold_down
            if angle <= self.return_limit:
                rep_duration = (timestamp - self.current_rep_start_time) if self.current_rep_start_time is not None else 0.0
                
                # Check minimum duration constraint to reject fast false twitches
                if rep_duration >= self.min_rep_duration and self.current_rep_peak_angle >= self.required_peak:
                    self.rep_count += 1
                    rep_just_completed = True
                    self.completed_reps_info.append({
                        "rep_number": self.rep_count,
                        "duration": round(rep_duration, 2),
                        "peak_angle": round(self.current_rep_peak_angle, 1),
                        "excursion_deg": round(max(0., self.current_rep_peak_angle - self.rest_angle), 1),
                        "min_angle": round(self.current_rep_min_angle if self.current_rep_min_angle < 900 else angle, 1),
                        "timestamp": timestamp
                    })
                
                # Return to REST
                self.reset_partial()
                self.rest_seen = angle <= self.threshold_down or (self.adaptive_return and rep_just_completed)
                if self.rest_seen:
                    self.rest_angle = angle
            elif angle > self.current_rep_peak_angle:
                # User pushed higher during descent
                self.current_rep_peak_angle = angle
                self.state = "ASCENT"

        current_rom = max(0.0, self.session_max_angle - (self.session_min_angle if self.session_min_angle < 900 else 0.0))

        return {
            "repetitions": self.rep_count,
            "rep_just_completed": rep_just_completed,
            "state": self.state,
            "current_angle": round(angle, 1),
            "session_min_angle": round(self.session_min_angle if self.session_min_angle < 900 else 0.0, 1),
            "session_max_angle": round(self.session_max_angle, 1),
            "rom": round(current_rom, 1)
        }

    def compute_movement_consistency(self) -> Dict[str, Any]:
        """
        Derives objective consistency metrics across all completed repetitions:
        - avg_rep_duration: Mean duration per repetition in seconds.
        - rep_duration_variation: Standard deviation of repetition durations.
        - peak_angle_variation: Standard deviation of peak elevation angles.
        - smoothness_score: Normalized consistency index [0 - 100] based on
          low variation in peak angle and duration.
          Formula: 100 - min(50, std(peak)*5) - min(50, std(dur)*25)
        """
        if len(self.completed_reps_info) < 2:
            return {
                "avg_rep_duration": self.completed_reps_info[0]["duration"] if self.completed_reps_info else 0.0,
                "rep_duration_variation": 0.0,
                "peak_angle_variation": 0.0,
                "smoothness_score": 80.0 if self.completed_reps_info else 0.0,
                "total_reps": len(self.completed_reps_info)
            }

        durations = [r["duration"] for r in self.completed_reps_info]
        peaks = [r["peak_angle"] for r in self.completed_reps_info]

        avg_dur = float(np.mean(durations))
        std_dur = float(np.std(durations))
        avg_peak = float(np.mean(peaks))
        std_peak = float(np.std(peaks))

        # Smoothness formula based on coefficient of variation
        # Higher score = more consistent, controlled repetition execution
        penalty_dur = min(40.0, (std_dur / max(avg_dur, 0.1)) * 50.0)
        penalty_peak = min(40.0, (std_peak / max(avg_peak, 0.1)) * 50.0)
        smoothness = max(20.0, round(100.0 - penalty_dur - penalty_peak, 1))

        return {
            "avg_rep_duration": round(avg_dur, 2),
            "rep_duration_variation": round(std_dur, 2),
            "peak_angle_variation": round(std_peak, 2),
            "smoothness_score": smoothness,
            "total_reps": len(self.completed_reps_info)
        }
