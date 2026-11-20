export type NavItemKey = 
  | 'overview'
  | 'monitoring'
  | 'exercises'
  | 'sessions'
  | 'analytics'
  | 'reports'
  | 'settings';

export type DataSourceMode = 'demo' | 'live';
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

export interface LiveSensorSample {
  timestamp: number;
  device_id: string;
  source: DataSourceMode;
  exercise_key: string;
  affected_side: AffectedSide;
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
  warnings: string[];
}

export interface DeviceStatus {
  device_id: string;
  device_name: string;
  device_type: string;
  connection_method: string;
  is_active: boolean;
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
  }>;
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
  rom_difference: number;
  rom_change_percentage: number | null;
  repetitions_difference: number;
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
  ml_status: {
    predicted_class: string | null;
    confidence: number | null;
    status_message: string;
  };
  rule_based_demonstration: {
    type: string;
    disclaimer: string;
    heuristic_score: number;
    demonstration_category: string;
  };
  clinical_summary: string;
  disclaimer: string;
}
