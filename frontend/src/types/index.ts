export type NavItemKey = 
  | 'overview'
  | 'monitoring'
  | 'exercises'
  | 'sessions'
  | 'analytics'
  | 'reports'
  | 'settings';

export type DataSourceMode = 'demo' | 'live' | 'replay';
export type AffectedSide = 'left' | 'right';

export interface Exercise {
  id: number;
  exercise_key: string;
  display_name: string;
  category: string;
  target_movement: string;
  primary_metric: string;
  threshold_up: number;
  threshold_down: number;
  min_rep_duration_sec: number;
  default_target_angle: number;
  description: string;
  instructions: string;
}

export interface ReplayRecording {
  id: string;
  participant: string;
  side_code: number;
  label?: number;
  exercise_key: string;
  exercise_name: string;
  duration_s: number;
  samples: number;
  sampling_hz: number;
}

export interface WristSignal {
  acceleration_m_s2: number;
  gyro_rad_s: number;
}

export interface MovementAnalytics {
  status: 'model_unavailable' | 'unsupported_exercise' | 'collecting' | 'scored' | 'wrist_data_unavailable';
  scored_windows: number;
  rep_reference?: {
    status: 'unsupported_exercise' | 'model_unavailable' | 'collecting' | 'insufficient_wrist_samples' | 'scored';
    pending_reps: number;
    trace: Array<{ group: number; first_rep: number; last_rep: number; time_s: number; invalid_reps?: number[]; score: number | null; prediction: -1 | 1 | null }>;
  };
  repetition_review?: { completed: number; required: number; median_peak_deg: number | null; median_duration_s: number | null };
  wrist_sample_count?: number;
  buffered_wrist_samples?: number;
  last_wrist_interval_s?: number | null;
  reference_windows?: number | null;
  mean_decision_score?: number | null;
  model_id?: string | null;
  recording?: ReplayRecording;
  samples_replayed?: number;
  replay_complete?: boolean;
  wrist_trace?: Array<WristSignal & { time_s: number }>;
  decision_trace?: Array<{ start_s?: number; time_s: number; score: number; prediction?: -1 | 1 }>;
  repetition_timeline?: Array<{ start_s: number; marker_s?: number; end_s: number }>;
  pain_rating?: number | null;
  movement_baseline?: { session_id: number; changes: Record<string, number> } | null;
  wrist_gyro_mean_rad_s?: number | null;
  outlier_windows: number | null;
  latest_decision_score: number | null;
  latest_prediction: -1 | 1 | null;
  wrist_gyro_peak_rad_s: number | null;
  wrist_jerk_rms_m_s3: number | null;
  median_rep_excursion_deg?: number | null;
  median_rep_peak_deg?: number | null;
  mean_rep_duration_s?: number | null;
  rep_wrist_gyro_mean_rad_s?: number | null;
  wrist_sample_interval_median_s?: number | null;
  prescribed_repetitions?: number | null;
  prescribed_angle_deg?: number | null;
  stiffness_rating?: number | null;
  coarse_wrist_jerk_rms_m_s3?: number | null;
  coarse_wrist_jerk_covered_reps?: number;
  coarse_wrist_jerk_coverage_s?: number;
  trunk_peak_deg: number | null;
  relative_excursion_deg: number | null;
  movement_metric?: 'total_tilt' | 'neutral_rotation' | 'exercise_projection' | null;
  rep_peak_deg?: number | null;
  angle_source: 'wrist' | 'upper_arm' | null;
  estimated_repetition_count?: number | null;
  movement_duration_s?: number | null;
  peak_angle_sd_deg?: number | null;
  rep_duration_sd_s?: number | null;
}

export interface LiveSensorSample {
  timestamp: number;
  device_id: string;
  source: DataSourceMode;
  wrist_sample?: WristSignal | null;
  exercise_key: string;
  affected_side: string;
  flexion_angle: number;
  abduction_angle: number;
  rotation_angle: number | null;
  primary_angle: number;
  angular_velocity: number;
  repetitions: number;
  rep_just_completed?: boolean;
  session_rom: number;
  session_min_angle: number;
  session_max_angle: number;
  state: 'REST' | 'ASCENT' | 'DESCENT' | string;
  quality_flag: string;
  q_relative: number[];
  analytics?: MovementAnalytics | null;
  warnings: string[];
}

export interface DeviceStatus {
  device_id: string;
  device_name: string;
  device_type: string;
  connection_method: string;
  is_active: boolean;
  hardware_active?: boolean;
  data_source_mode: DataSourceMode;
  is_monitoring: boolean;
  packets_received: number;
  packets_invalid: number;
  data_freshness_sec: number | null;
  sensors_detected: string[];
  current_exercise: string;
}

export interface SessionRecord {
  id: number;
  patient_id: number;
  exercise_key: string;
  exercise_name?: string;
  affected_side: string;
  data_source: DataSourceMode;
  status: 'completed' | 'in_progress' | 'discarded';
  start_time: string;
  end_time?: string;
  duration_seconds: number;
  min_angle: number;
  max_angle: number;
  rom: number;
  repetitions: number;
  avg_rep_duration?: number;
  rep_duration_variation?: number;
  peak_angle_variation?: number;
  smoothness_score?: number;
  ml_predicted_class?: string;
  ml_confidence?: number;
  ml_model_info?: string;
  movement_analytics?: MovementAnalytics | null;
  notes?: string;
  warnings?: string;
}

export interface DashboardSummary {
  latest_rom: number;
  best_rom: number;
  total_repetitions: number;
  total_sessions: number;
  avg_movement_quality: number | null;
  rom_change_vs_prior: number | null;
  rom_change_percentage: number | null;
  recovery_summary_text: string;
  device_status: DeviceStatus;
  recent_sessions: Array<{
    id: number;
    date: string;
    exercise_key: string;
    exercise_name: string;
    repetitions: number;
    rom: number;
    max_angle: number;
    min_angle: number;
    duration_seconds: number;
    smoothness_score: number | null;
    data_source: DataSourceMode;
    status: string;
    movement_analytics?: MovementAnalytics | null;
  }>;
}

export type RehabComponent = 'mobility' | 'control' | 'posture' | 'symptoms';
export interface RehabProgress {
  eligible: boolean;
  baseline_session_ids: number[];
  baseline_ready?: boolean;
  is_baseline_session?: boolean;
  compared?: Record<string, { baseline: number; current: number; change: number; unit: string }>;
  components?: Partial<Record<RehabComponent, number>>;
  component_metrics?: Partial<Record<RehabComponent, string[]>>;
  weights?: Record<RehabComponent, number>;
  mobility_trend?: 'improving' | 'declining' | 'stable' | 'inconclusive' | 'insufficient';
  score?: number | null;
  coverage?: number;
  partial?: boolean;
  baseline_score?: number | null;
  score_change?: number | null;
  rep_completion?: number | null;
  measurement_protocol_key?: string;
  score_comparison_key?: string;
  daily_score?: number;
  weekly_score?: number;
  week_start?: string;
}

export interface DatasetWristReference {
  sampling_hz: number;
  window_s: number;
  participant_files: number;
  labels: Record<number, { participants: number; windows: number; metrics: Record<string, { p10: number; median: number; p90: number }> }>;
}

export interface ROMProgressItem {
  session_id: number;
  session_number: number;
  date: string;
  exercise_key: string;
  rom: number;
  max_angle: number;
  min_angle: number;
  repetitions: number;
  duration_seconds: number;
  smoothness_score: number | null;
  data_source: DataSourceMode;
  affected_side: string;
  movement_analytics?: MovementAnalytics | null;
  rehab_progress?: RehabProgress | null;
}

export interface WeeklyActivityItem {
  day: string;
  date: string;
  sessions_count: number;
  total_repetitions: number;
}

export interface SessionComparison {
  session_a: SessionRecord;
  session_b: SessionRecord;
  rom_difference: number | null;
  rom_change_percentage: number | null;
  repetitions_difference: number | null;
  movement_changes?: Record<string, number>;
  warnings: string[];
  is_comparable: boolean;
}

export interface PhysiotherapyReport {
  report_id: string;
  generated_at: string;
  patient: {
    id: number;
    display_name: string;
    affected_side: string;
    notes: string;
  };
  session: {
    id: number;
    date: string;
    data_source: DataSourceMode;
    exercise_name: string;
    exercise_category: string;
    duration_seconds: number;
    repetitions: number;
    min_angle: number;
    max_angle: number;
    rom: number;
    rom_change_vs_prior: number | null;
    avg_rep_duration: number | null;
    rep_duration_variation: number | null;
    peak_angle_variation: number | null;
    smoothness_score: number | null;
    notes: string | null;
    warnings: string;
  };
  movement_analytics?: MovementAnalytics | null;
  clinical_summary: string;
  disclaimer: string;
}

export type PlaybackSpeed = 1 | 2 | 4;
export type ReplayAction = 'pause' | 'resume' | 'restart' | 'speed';

export interface Participant {
  id: number;
  name: string;
  affected_side: 'left' | 'right';
}

export interface MonitoringSnapshot {
  session_id: number;
  patient_id?: number | null;
  source: DataSourceMode;
  exercise_key: string;
  affected_side: string;
  elapsed_s: number;
  status: 'playing' | 'paused' | 'complete' | 'recording' | 'stopped';
  playback_speed: PlaybackSpeed;
  analytics: MovementAnalytics;
  wrist_trace: Array<WristSignal & { time_s: number }>;
  wrist_sample: WristSignal | null;
  orientation: LiveOrientation | null;
}

export interface HardwareStreamStatus {
  receiving: boolean;
  last_packet_age_s: number | null;
  valid_packets: number;
  rejected_packets: number;
  device_id: string | null;
  sensors: string[];
  has_wrist_vectors: boolean;
  has_orientation: boolean;
  axes_calibrated?: boolean;
  neutral_calibrated?: boolean;
  captured_poses?: Array<'forward' | 'side'>;
  diagnostic?: OrientationDiagnostic | null;
  orientation_preview?: { flexion: number; abduction: number; ext_rotation: number; int_rotation: number; movement_plane?: string; total_elevation?: number; neutral_rotation?: number | null } | null;
}

export type LiveOrientation = Pick<LiveSensorSample, 'primary_angle' | 'flexion_angle' |
  'abduction_angle' | 'rotation_angle' | 'angular_velocity' | 'session_max_angle' | 'quality_flag'> & { off_plane?: boolean; movement_angle_deg?: number | null; movement_metric?: MovementAnalytics["movement_metric"] };

export interface OrientationDiagnostic {
  chest: number[];
  limb: number[];
  limb_key: string;
  relative: number[];
  angle_deg: number;
  total_elevation_deg?: number;
  axes_calibrated?: boolean;
  movement_plane: string;
  off_plane: boolean;
  quality: string;
  packet_timestamp_s: number;
  sensor_timestamps_s: Array<number | null>;
  skew_s: number | null;
  sync: 'unknown' | 'within_tolerance' | 'out_of_sync';
  sample_age_s: number;
}
