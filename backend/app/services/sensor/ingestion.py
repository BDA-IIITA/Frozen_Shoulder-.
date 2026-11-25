import time
import asyncio
import numpy as np
from typing import Dict, Any, List, Optional
from app.services.flexion.inference import WristSession, wrist_axes
from app.services.flexion.signal import FS, filter_wrist
from app.services.flexion.replay import replay_packet
from app.services.flexion.repetitions import CycleEstimate, estimate_cycles
from app.services.biomechanics.angle_calculator import LIVE_MOVEMENT_GAP_S, ShoulderAngleCalculator, calibrated_axes, motion_axis
from app.services.biomechanics.quaternion_math import relative_quaternion
from app.services.biomechanics.rep_counter import RepetitionCounter
from app.services.sensor.simulator import SensorSimulator
from app.core.logger import get_logger
from app.services.analytics.wrist_jerk import coarse_wrist_jerk

logger = get_logger("SensorIngestionService")

class SensorIngestionService:
    """
    Central real-time ingestion service coordinating sensor streams
    (Demo or Live ESP32), biomechanical processing, repetition tracking,
    and live WebSocket broadcasting.
    """
    def __init__(self):
        self.angle_calculator = ShoulderAngleCalculator()
        self.rep_counter = RepetitionCounter()
        self.simulator = SensorSimulator()
        self.wrist = WristSession("flexion", None)
        self.chest_baseline = None
        self.trunk_peak = None
        self.orientation_kind = None
        self.movement_metric = None
        self.session_device = None
        self.session_source = None
        self.previous_orientation_time = None
        self.last_orientation_pair = None
        self.calibrations = {}
        self.reference_axes = {}
        self.last_pair_diagnostic = None
        self.motion_bases = {}

        # Operational state
        self.mode: str = "demo"  # "demo" or "live"
        self.is_monitoring: bool = False
        self.current_exercise: str = "flexion"
        self.current_side: str = "right"
        self.active_session_id: Optional[int] = None

        # Diagnostics
        self.packets_received: int = 0
        self.packets_invalid: int = 0
        self.last_packet_time: Optional[float] = None
        self.last_hardware_packet: Optional[float] = None
        self.hardware_packets = 0
        self.hardware_rejected = 0
        self.hardware_sensors = []
        self.hardware_device = None
        self.hardware_has_wrist_vectors = False
        self.hardware_has_orientation = False
        self.detected_sensors: List[str] = []

        # Sliding window of processed outputs for live display
        self.recent_samples: List[Dict[str, Any]] = []
        self.max_buffer_size: int = 300

        # Background simulator task reference
        self._sim_task: Optional[asyncio.Task] = None
        self._replay_task: Optional[asyncio.Task] = None
        self.replay_metadata = None
        self.replay_samples = None
        self.replay_position = 0
        self.replay_paused = False
        self.playback_speed = 1
        self.replay_epoch = None
        self.first_session_sample = None
        self.replay_cycles = CycleEstimate([])
        self.wrist_trace = []
        self._subscribers: List[asyncio.Queue] = []

    def set_mode(self, mode: str):
        if mode not in ["demo", "live", "replay"]:
            raise ValueError("Invalid sensor mode")
        self.mode = mode
        logger.info(f"Sensor ingestion mode switched to: {mode}")

    def set_exercise(self, exercise_key: str, affected_side: str = "right"):
        self.current_exercise = exercise_key
        self.current_side = affected_side
        self.simulator.set_exercise(exercise_key)
        
        # Configure thresholds per exercise
        if exercise_key in ["external_rotation", "internal_rotation"]:
            self.rep_counter.threshold_up = 25.0
            self.rep_counter.threshold_down = 10.0
        elif exercise_key == "abduction":
            self.rep_counter.threshold_up = 40.0
            self.rep_counter.threshold_down = 18.0
        else: # flexion
            self.rep_counter.threshold_up = 45.0
            self.rep_counter.threshold_down = 20.0

    def start_monitoring(self, session_id: Optional[int] = None, replay=None, playback_speed=1):
        self.is_monitoring = True
        self.active_session_id = session_id
        self.rep_counter.adaptive_return = self.mode == "live" and self.current_exercise in ("flexion", "abduction")
        self.rep_counter.reset()
        self.angle_calculator.reset_state()
        self.recent_samples.clear()
        self.wrist = WristSession(self.current_exercise, None)
        self.chest_baseline = None
        self.trunk_peak = None
        self.orientation_kind = None
        self.movement_metric = None
        self.session_device = None
        self.previous_orientation_time = None
        self.session_source = self.mode
        self.simulator.start_epoch = time.time()
        self.replay_metadata, self.replay_samples = replay if replay is not None else (None, None)
        self.replay_position = 0
        self.replay_paused = False
        self.playback_speed = playback_speed
        self.replay_epoch = time.time()
        self.first_session_sample = None
        self.replay_cycles = CycleEstimate([])
        self.wrist_trace = []
        if replay is not None:
            self._replay_task = asyncio.create_task(self._run_replay())

        # Start background simulator generator if in demo mode and an event loop is active
        if self.mode == "demo":
            try:
                loop = asyncio.get_running_loop()
                if self._sim_task is None or self._sim_task.done():
                    self._sim_task = loop.create_task(self._run_demo_generator())
            except RuntimeError:
                pass
        logger.info(f"Started monitoring. Exercise={self.current_exercise}, Mode={self.mode}, SessionId={session_id}")

    def _cancel_replay_task(self):
        if self._replay_task and not self._replay_task.done():
            self._replay_task.cancel()
        self._replay_task = None

    def stop_monitoring(self):
        self.is_monitoring = False
        self._cancel_replay_task()
        if self._sim_task and not self._sim_task.done():
            self._sim_task.cancel()
            self._sim_task = None
        logger.info("Stopped monitoring.")

    def update_replay_cycles(self):
        if self.current_exercise == "flexion" and self.replay_position >= 5 * FS:
            raw = self.replay_samples[:self.replay_position]
            self.replay_cycles = estimate_cycles(filter_wrist(raw)[0])

    def replay_metrics(self):
        if self.replay_metadata is None:
            return {}
        cycles = self.replay_cycles
        count = cycles.count
        durations = [(end - start) / FS for start, _, end in cycles.bounds]
        return {
            "recording": self.replay_metadata, "samples_replayed": self.replay_position,
            "replay_complete": self.replay_position == len(self.replay_samples),
            "estimated_repetition_count": count,
            "rep_method": "signed_gyro_cycles" if count is not None else None,
            "cycle_period_s": cycles.period_s, "cycle_periodicity": cycles.periodicity,
            "movement_duration_s": sum(durations) if durations else None,
            "rep_duration_sd_s": float(np.std(durations)) if len(durations) >= 2 else None,
        }

    def control_replay(self, action, speed=None):
        if action == "restart":
            self._cancel_replay_task()
            self.mode = "replay"
            self.start_monitoring(self.active_session_id, (self.replay_metadata, self.replay_samples),
                                  speed or self.playback_speed)
        elif action == "pause":
            self.replay_paused = True
            self._cancel_replay_task()
        elif action == "resume" and self.replay_paused:
            self.replay_paused = False
            self._replay_task = asyncio.create_task(self._run_replay())
        elif action == "speed" and speed != self.playback_speed:
            self.playback_speed = speed
            if not self.replay_paused and self.replay_position < len(self.replay_samples):
                self._cancel_replay_task()
                self._replay_task = asyncio.create_task(self._run_replay())

    async def _run_replay(self):
        loop = asyncio.get_running_loop()
        started = loop.time()
        first = self.replay_position
        for index in range(first, len(self.replay_samples)):
            # Playback speed changes delivery time. Recorded time remains at 50 Hz.
            await asyncio.sleep(max(0, started + (index - first + 1) / (FS * self.playback_speed) - loop.time()))
            self.replay_position = index + 1
            if self.replay_position % (2 * FS) == 0 or self.replay_position == len(self.replay_samples):
                self.update_replay_cycles()
            self.process_packet(replay_packet(self.replay_epoch + index / FS, self.replay_samples[index]))

    def repetition_timeline(self):
        if self.replay_metadata is not None:
            return [{"start_s": start / FS, "marker_s": marker / FS, "end_s": end / FS}
                    for start, marker, end in self.replay_cycles.bounds]
        if self.first_session_sample is None:
            return []
        return [{"start_s": rep["timestamp"] - self.first_session_sample - rep["duration"],
                 "end_s": rep["timestamp"] - self.first_session_sample}
                for rep in self.rep_counter.completed_reps_info]

    def repetition_review(self):
        if self.session_source != "live":
            return {}
        reps = self.rep_counter.completed_reps_info
        target = 3
        recent = reps[-target:]
        ready = len(recent) == target
        return {"repetition_review": {
            "completed": len(reps),
            "required": target,
            "median_peak_deg": round(float(np.median([rep["peak_angle"] for rep in recent])), 1) if ready else None,
            "median_duration_s": round(float(np.median([rep["duration"] for rep in recent])), 2) if ready else None,
        }}

    def coarse_jerk_metrics(self):
        if self.session_source != "live":
            return {}
        return coarse_wrist_jerk(self.wrist_trace, self.repetition_timeline())

    def monitoring_snapshot(self):
        if self.active_session_id is None:
            return None
        latest = self.recent_samples[-1] if self.recent_samples else None
        if self.replay_metadata is not None:
            elapsed = self.replay_position / FS
        elif latest and self.first_session_sample is not None:
            elapsed = max(0., latest["timestamp"] - self.first_session_sample)
        else:
            elapsed = 0.
        durations = [rep["duration"] for rep in self.rep_counter.completed_reps_info]
        analytics = {
            **self.wrist.summary(include_scores=True),
            "movement_duration_s": round(sum(durations), 2) if durations else None,
            "rep_duration_sd_s": float(np.std(durations)) if len(durations) >= 2 else None,
            **(latest["analytics"] if latest and latest["analytics"] else {}),
            **self.replay_metrics(),
            **self.repetition_review(),
            **self.coarse_jerk_metrics(),
            "repetition_timeline": self.repetition_timeline(),
        }
        return {
            "session_id": self.active_session_id, "source": self.session_source,
            "exercise_key": self.current_exercise, "affected_side": self.current_side,
            "elapsed_s": elapsed,
            "status": ("complete" if analytics.get("replay_complete") else "paused" if self.replay_paused
                       else "playing" if self.replay_metadata else "recording" if self.is_monitoring else "stopped"),
            "playback_speed": self.playback_speed,
            "analytics": analytics, "wrist_trace": self.wrist_trace[-120:],
            "wrist_sample": latest["wrist_sample"] if latest else None,
            "orientation": {key: latest[key] for key in (
                "primary_angle", "flexion_angle", "abduction_angle", "rotation_angle",
                "angular_velocity", "session_max_angle", "quality_flag", "off_plane",
                "movement_angle_deg", "movement_metric"
            )} if latest and latest["source"] != "replay" and time.time() - (self.last_packet_time or 0) < 2.5 else None,
        }

    def calibrate_neutral(self, device_id: str) -> bool:
        if self.active_session_id is not None or self.last_orientation_pair is None:
            return False
        key, received, chest, limb = self.last_orientation_pair
        if key[0] != device_id or key[2] != "live" or time.monotonic() - received > 2.5:
            return False
        self.angle_calculator.set_calibration_neutral(chest, limb)
        self.calibrations[key] = self.angle_calculator.calibration_offset
        for side in ("left", "right"):
            self.reference_axes.pop((*key, side), None)
            self.motion_bases.pop((*key, side), None)
        self.angle_calculator.reset_state()
        return True

    def capture_motion_axis(self, device_id, pose, side):
        if self.active_session_id is not None or self.last_orientation_pair is None:
            raise ValueError("Capture calibration poses before recording with both sensors connected.")
        key, received, chest, limb = self.last_orientation_pair
        if key[0] != device_id or key[2] != "live" or time.monotonic() - received > 2.5:
            raise ValueError("Waiting for a recent paired ESP32 orientation packet.")
        if key not in self.calibrations:
            raise ValueError("Set neutral first with your arm down.")
        side_key = (*key, side)
        axis = motion_axis(relative_quaternion(chest, limb), self.calibrations[key])
        poses = {**self.reference_axes.get(side_key, {}), pose: axis}
        if "forward" in poses and "side" in poses:
            self.motion_bases[side_key] = calibrated_axes(poses["forward"], poses["side"], side)
        self.reference_axes[side_key] = poses

    async def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def process_packet(self, packet_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validates, normalizes, processes incoming sensor packet,
        and derives shoulder angles and repetition state.
        """
        self.packets_received += 1
        t = packet_dict.get("timestamp", time.time())

        sensors = packet_dict.get("sensors", {})
        self.detected_sensors = list(sensors.keys())

        source = packet_dict.get("source", self.mode)
        # Live ESP32 firmware can label the wrist-mounted IMU "upper_arm".
        # Keep synthetic upper-arm data separate from the wrist model inputs.
        wrist_sensor = sensors.get("wrist", sensors.get("upper_arm", {}) if source == "live" else {})
        wrist = wrist_axes(wrist_sensor)
        chest_q = sensors.get("chest", {}).get("quaternion")
        # Keep the legacy upper-arm protocol. Explicit wrist packets use a wrist proxy.
        kind = "upper_arm" if "upper_arm" in sensors else "wrist"
        arm_q = sensors.get(kind, {}).get("quaternion")
        device = packet_dict.get("device_id", "esp32-shoulder-01")
        if source == "live":
            if wrist is not None or (chest_q and arm_q):
                self.last_hardware_packet = time.time()
                self.hardware_packets += 1
                self.hardware_sensors = list(sensors)
                self.hardware_device = device
                self.hardware_has_wrist_vectors = wrist is not None
                self.hardware_has_orientation = bool(chest_q and arm_q)
            else:
                self.hardware_rejected += 1
        if self.is_monitoring and source != self.session_source:
            return None

        if self.is_monitoring:
            if self.session_device is not None and device != self.session_device:
                return None
            if wrist is not None or (chest_q and arm_q):
                self.session_device = device
                if self.first_session_sample is None:
                    self.first_session_sample = t
                    self.wrist.first_time = t
            self.wrist.add(t, device, wrist)
        if wrist is None and not (chest_q and arm_q):
            self.packets_invalid += 1
            return None

        self.last_packet_time = time.time()

        def quaternion(data):
            return np.array([data.get(axis, 1. if axis == "w" else 0.) for axis in "xyzw"])

        if chest_q and self.is_monitoring:
            chest = quaternion(chest_q)
            chest = chest / np.linalg.norm(chest)
            if self.chest_baseline is None:
                self.chest_baseline = chest
            displacement = float(np.degrees(2 * np.arccos(
                np.clip(abs(np.dot(chest, self.chest_baseline)), 0, 1))))
            self.trunk_peak = max(self.trunk_peak or 0., displacement)

        angle_result = dict.fromkeys(
            ("flexion", "abduction", "ext_rotation", "int_rotation", "primary_angle", "angular_velocity"), 0.)
        angle_result.update(quality_flag="ORIENTATION_UNAVAILABLE", q_relative=[0., 0., 0., 1.], off_plane=False)
        sample_times = [sensors.get(sensor, {}).get("sample_timestamp") for sensor in ("chest", kind)]
        skew = abs(sample_times[0] - sample_times[1]) if None not in sample_times else None
        out_of_sync = skew is not None and (skew > .030 or any(
            stamp > t + .030 or t - stamp > .100 for stamp in sample_times
        ))
        if chest_q and arm_q and (not self.is_monitoring or self.orientation_kind in (None, kind)):
            chest, limb = quaternion(chest_q), quaternion(arm_q)
            key = (device, kind, source)
            if not out_of_sync:
                self.last_orientation_pair = (key, time.monotonic(), chest, limb)
            elif source == "live":
                self.last_orientation_pair = None
            self.angle_calculator.calibration_offset = self.calibrations.get(key)
            self.angle_calculator.motion_basis = self.motion_bases.get((*key, self.current_side))
            angle_result = self.angle_calculator.compute_angles(
                q_chest_raw=chest, q_arm_raw=limb, timestamp=t,
                exercise_key=self.current_exercise, affected_side=self.current_side,
                use_total_movement=source == "live" and self.current_exercise in ("flexion", "abduction"),
            )
            if out_of_sync:
                angle_result["quality_flag"] = "UNSYNCHRONIZED_ORIENTATION"
                self.angle_calculator.reset_state()
            if source == "live":
                self.last_pair_diagnostic = {
                    "chest": chest.tolist(), "limb": limb.tolist(), "limb_key": kind,
                    "relative": angle_result["q_relative"], "angle_deg": angle_result["primary_angle"],
                    "total_elevation_deg": angle_result["total_elevation"],
                    "axes_calibrated": self.angle_calculator.motion_basis is not None,
                    "movement_plane": angle_result["movement_plane"], "off_plane": angle_result["off_plane"],
                    "quality": angle_result["quality_flag"], "packet_timestamp_s": t,
                    "sensor_timestamps_s": sample_times, "skew_s": skew,
                    "sync": "out_of_sync" if out_of_sync else "unknown" if skew is None else "within_tolerance",
                    "received": time.monotonic(),
                }
        gap_limit = LIVE_MOVEMENT_GAP_S if source == "live" and self.current_exercise in ("flexion", "abduction") else .25
        if (self.is_monitoring and self.previous_orientation_time is not None
                and not 0 < t - self.previous_orientation_time < gap_limit):
            self.rep_counter.reset_partial()
        start = self.rep_counter.current_rep_start_time
        rep_result = {
            "repetitions": self.rep_counter.rep_count, "rep_just_completed": False,
            "rom": max(0., self.rep_counter.session_max_angle - self.rep_counter.session_min_angle),
            "session_min_angle": 0., "session_max_angle": self.rep_counter.session_max_angle,
            "state": self.rep_counter.state,
        }
        movement_angle = None
        movement_metric = None
        if angle_result["quality_flag"] == "VALID":
            if source == "live" and self.current_exercise in ("flexion", "abduction"):
                if self.angle_calculator.motion_basis is not None:
                    movement_angle, movement_metric = angle_result["total_elevation"], "total_tilt"
                elif angle_result["neutral_rotation"] is not None:
                    movement_angle, movement_metric = angle_result["neutral_rotation"], "neutral_rotation"
            else:
                movement_angle, movement_metric = angle_result["primary_angle"], "exercise_projection"
        if self.is_monitoring and movement_angle is not None:
            if self.orientation_kind in (None, kind):
                self.orientation_kind = kind
                self.previous_orientation_time = t
                self.movement_metric = movement_metric
                rep_result = self.rep_counter.process_sample(movement_angle, t)
                if rep_result["rep_just_completed"] and start is not None:
                    self.wrist.complete_rep(start, t)
        elif self.is_monitoring and (source != "live" or self.current_exercise not in ("flexion", "abduction")):
            self.rep_counter.reset_partial()

        wrist_sample = None
        if wrist is not None:
            wrist_sample = {
                "acceleration_m_s2": float(np.linalg.norm(wrist[:3])),
                "gyro_rad_s": float(np.linalg.norm(wrist[3:])),
            }
            if self.is_monitoring and self.wrist.first_time is not None:
                relative_time = round(t - self.wrist.first_time, 3)
                if relative_time >= 0 and (not self.wrist_trace or relative_time >= self.wrist_trace[-1]["time_s"] + .199):
                    if len(self.wrist_trace) < 18000:
                        self.wrist_trace.append({"time_s": relative_time, **wrist_sample})

        processed = {
            "timestamp": t,
            "wrist_sample": wrist_sample,
            "movement_angle_deg": movement_angle,
            "movement_metric": movement_metric,
            "device_id": packet_dict.get("device_id", "esp32-shoulder-01"),
            "source": packet_dict.get("source", self.mode),
            "exercise_key": self.current_exercise,
            "affected_side": self.current_side,
            "flexion_angle": angle_result["flexion"],
            "abduction_angle": angle_result["abduction"],
            "rotation_angle": angle_result["ext_rotation"] if self.current_exercise == "external_rotation" else angle_result["int_rotation"],
            "primary_angle": angle_result["primary_angle"],
            "angular_velocity": angle_result["angular_velocity"],
            "repetitions": rep_result["repetitions"],
            "rep_just_completed": rep_result["rep_just_completed"],
            "session_rom": rep_result["rom"],
            "session_min_angle": rep_result["session_min_angle"],
            "session_max_angle": rep_result["session_max_angle"],
            "state": rep_result["state"],
            "quality_flag": angle_result["quality_flag"],
            "off_plane": angle_result["off_plane"],
            "q_relative": angle_result["q_relative"],
            "analytics": {
                **self.wrist.summary(),
                "trunk_peak_deg": self.trunk_peak,
                "angle_source": self.orientation_kind,
                "movement_metric": self.movement_metric,
                "rep_peak_deg": self.rep_counter.threshold_up if self.movement_metric else None,
                "relative_excursion_deg": rep_result["rom"] if self.orientation_kind else None,
                "estimated_repetition_count": rep_result["repetitions"] if self.orientation_kind else None,
                **self.replay_metrics(),
            } if self.is_monitoring else None,
            "warnings": [] if angle_result["quality_flag"] == "VALID" else [angle_result["quality_flag"]]
        }

        # Keep in rolling buffer
        if self.is_monitoring:
            self.recent_samples.append(processed)
        if len(self.recent_samples) > self.max_buffer_size:
            self.recent_samples.pop(0)

        # Broadcast to all live subscribers
        self._broadcast(processed)
        return processed

    def _broadcast(self, data: Dict[str, Any]):
        for q in list(self._subscribers):
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(data)
            except Exception:
                pass

    async def _run_demo_generator(self):
        """Generates synthetic demo IMU packets at 50 Hz during Demo Monitoring"""
        logger.info("Demo IMU stream generator started at 50 Hz.")
        try:
            loop = asyncio.get_running_loop()
            start = loop.time()
            index = 0
            while self.is_monitoring and self.session_source == "demo":
                packet = self.simulator.generate_packet(self.simulator.start_epoch + index / FS)
                self.process_packet(packet)
                index += 1
                await asyncio.sleep(max(0, start + index / FS - loop.time()))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in demo generator: {e}", exc_info=True)
        finally:
            logger.info("Demo IMU stream generator ended.")

    def hardware_preview(self, side="right"):
        if self.active_session_id is not None or self.last_orientation_pair is None:
            return None
        key, received, chest, limb = self.last_orientation_pair
        if key[2] != "live" or time.monotonic() - received >= 2.5:
            return None
        calculator = ShoulderAngleCalculator(self.calibrations.get(key))
        calculator.motion_basis = self.motion_bases.get((*key, side))
        angles = calculator.compute_angles(chest, limb, timestamp=0, affected_side=side)
        return {name: angles[name] for name in ("flexion", "abduction", "ext_rotation", "int_rotation", "movement_plane", "total_elevation", "neutral_rotation")}

    def hardware_status(self, side="right"):
        age = max(0, time.time() - self.last_hardware_packet) if self.last_hardware_packet is not None else None
        key = self.last_orientation_pair[0] if self.last_orientation_pair else None
        calibrated = key is not None and (*key, side) in self.motion_bases
        diagnostic = self.last_pair_diagnostic
        if diagnostic:
            diagnostic = {**diagnostic, "sample_age_s": round(time.monotonic() - diagnostic["received"], 3)}
            diagnostic.pop("received")
        return {
            "receiving": age is not None and age < 2.5,
            "last_packet_age_s": round(age, 2) if age is not None else None,
            "valid_packets": self.hardware_packets, "rejected_packets": self.hardware_rejected,
            "device_id": self.hardware_device, "sensors": self.hardware_sensors,
            "has_wrist_vectors": self.hardware_has_wrist_vectors, "has_orientation": self.hardware_has_orientation,
            "orientation_preview": self.hardware_preview(side),
            "axes_calibrated": calibrated,
            "neutral_calibrated": key in self.calibrations,
            "captured_poses": list(self.reference_axes.get((*key, side), {})) if key else [],
            "diagnostic": diagnostic,
        }

    def get_diagnostic_status(self) -> Dict[str, Any]:
        now = time.time()
        data_freshness = round(now - self.last_packet_time, 2) if self.last_packet_time else None
        
        # Determine active status based on freshness (< 2.5 seconds)
        hardware_active = self.last_hardware_packet is not None and now - self.last_hardware_packet < 2.5
        
        source = self.session_source if self.is_monitoring else self.mode
        return {
            "device_id": "esp32-shoulder-01",
            "device_name": "ShoulderSense ESP32 IMU Hub",
            "device_type": "ESP32-BNO086 Dual-IMU",
            "connection_method": "WiFi/HTTP-WS",
            "is_active": hardware_active if source == "live" else self.is_monitoring,
            "hardware_active": hardware_active,
            "data_source_mode": source,
            "is_monitoring": self.is_monitoring,
            "packets_received": self.packets_received,
            "packets_invalid": self.packets_invalid,
            "data_freshness_sec": data_freshness,
            "sensors_detected": self.detected_sensors,
            "current_exercise": self.current_exercise
        }

sensor_ingestion_service = SensorIngestionService()
