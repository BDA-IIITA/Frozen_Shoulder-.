import {
  DashboardSummary, DatasetWristReference,
  Exercise,
  SessionRecord,
  ROMProgressItem,
  WeeklyActivityItem,
  SessionComparison,
  PhysiotherapyReport,
  ReplayRecording, Participant, MonitoringSnapshot, PlaybackSpeed, ReplayAction,
  DeviceStatus, HardwareStreamStatus
} from '../types';

const backendHost = (typeof window !== 'undefined' && window.location.hostname) ? window.location.hostname : 'localhost';
export const backendOrigin = (import.meta.env.VITE_BACKEND_ORIGIN || `http://${backendHost}:8000`).replace(/\/$/, '');
const API_BASE = `${backendOrigin}/api`;

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errMessage = `HTTP Error ${res.status}: ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) {
        errMessage = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errMessage);
  }

  return res.json() as Promise<T>;
}

export const api = {
  // Health
  getHardwareStream: (side: 'left' | 'right' = 'right') => fetchJson<HardwareStreamStatus>(`/sensor/status?side=${side}`),
  checkHealth: () => fetchJson<{ status: string; sensor_mode: string; is_monitoring: boolean }>('/health'),

  // Dashboard
  getDashboardSummary: (patientId = 1) => fetchJson<DashboardSummary>(`/dashboard/summary?patient_id=${patientId}`),

  // Devices
  getDevices: () => fetchJson<Array<{ id: string; name: string; type: string; is_active: boolean; diagnostics: DeviceStatus }>>('/devices'),
  getDevice: (id: string) => fetchJson<{ id: string; name: string; type: string; is_active: boolean; diagnostics: DeviceStatus }>(`/devices/${id}`),
  connectDevice: (id: string, mode: 'demo' | 'live', ip_address?: string) =>
    fetchJson<{ status: string; mode: string }>(`/devices/${id}/connect`, {
      method: 'POST',
      body: JSON.stringify({ mode, ip_address }),
    }),
  captureMotionAxis: (id: string, pose: 'forward' | 'side', side: 'left' | 'right') =>
    fetchJson<{ status: string }>(`/devices/${encodeURIComponent(id)}/calibrate/axes/${pose}?side=${side}`, { method: 'POST' }),
  disconnectDevice: (id: string) =>
    fetchJson<{ status: string }>(`/devices/${id}/disconnect`, { method: 'POST' }),
  calibrateNeutral: (id: string) =>
    fetchJson<{ status: string; message: string }>(`/devices/${id}/calibrate`, { method: 'POST' }),

  // Exercises
  getExercises: () => fetchJson<Exercise[]>('/exercises'),
  getExercise: (key: string) => fetchJson<Exercise>(`/exercises/${key}`),

  // Rehabilitation Sessions
  getSessions: (params?: { patient_id?: number; exercise_key?: string; data_source?: string }) => {
    const q = new URLSearchParams();
    if (params?.patient_id) q.set('patient_id', String(params.patient_id));
    if (params?.exercise_key) q.set('exercise_key', params.exercise_key);
    if (params?.data_source) q.set('data_source', params.data_source);
    return fetchJson<SessionRecord[]>(`/sessions?${q.toString()}`);
  },
  getSession: (id: number) => fetchJson<SessionRecord>(`/sessions/${id}`),
  getParticipants: () => fetchJson<Participant[]>('/participants'),
  getActiveMonitoring: () => fetchJson<MonitoringSnapshot | null>('/monitoring/active'),
  controlReplay: (id: number, action: ReplayAction, speed?: PlaybackSpeed) =>
    fetchJson<MonitoringSnapshot>(`/sessions/${id}/replay/${action}${speed ? `?speed=${speed}` : ''}`, { method: 'POST' }),
  getReplayRecordings: () => fetchJson<ReplayRecording[]>("/replay/recordings"),
  startSession: (data: { patient_id?: number; exercise_key: string; affected_side: string; data_source: string; recording_id?: string; playback_speed?: PlaybackSpeed; rep_peak_deg?: number; prescribed_repetitions?: number; prescribed_angle_deg?: number }) =>
    fetchJson<{ status: string; session_id: number; start_time: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  finishSession: (sessionId: number, notes?: string, saveSamples = true, pain?: number, stiffness?: number) =>
    fetchJson<{ session: SessionRecord; exercise_name: string; improvement_vs_previous_rom: number | null; movement_changes?: Record<string, number> | null }>(
      `/sessions/${sessionId}/finish`,
      {
        method: 'POST',
        body: JSON.stringify({ notes, save_samples: saveSamples, pain_rating: pain, stiffness_rating: stiffness }),
      }
    ),
  discardSession: (sessionId: number) =>
    fetchJson<{ status: string; message: string }>(`/sessions/${sessionId}`, { method: 'DELETE' }),
  getSessionSamples: (sessionId: number, signal?: AbortSignal) =>
    fetchJson<Array<{ timestamp: number; flexion_angle: number; abduction_angle: number; angular_velocity: number; quality_flag: string }>>(
      `/sessions/${sessionId}/samples`, { signal }
    ),

  // Analytics
  getROMAnalytics: (patientId = 1, exerciseKey?: string) => {
    const q = new URLSearchParams({ patient_id: String(patientId) });
    if (exerciseKey) q.set('exercise_key', exerciseKey);
    return fetchJson<ROMProgressItem[]>(`/analytics/rom?${q.toString()}`);
  },
  getDatasetWristReference: () => fetchJson<DatasetWristReference | null>('/analytics/dataset-reference'),
  getWeeklyActivity: (patientId = 1) =>
    fetchJson<WeeklyActivityItem[]>(`/analytics/weekly?patient_id=${patientId}`),
  compareSessions: (sessionA: number, sessionB: number) =>
    fetchJson<SessionComparison>(`/analytics/compare?session_a=${sessionA}&session_b=${sessionB}`),

  // Reports
  getSessionReport: (sessionId: number) => fetchJson<PhysiotherapyReport>(`/reports/sessions/${sessionId}`),

  // Sensor Ingest (Direct HTTP POST testing)
  ingestSensorPacket: (packet: any) =>
    fetchJson<{ status: string; sample: any }>('/sensor/ingest', {
      method: 'POST',
      body: JSON.stringify(packet),
    }),
};
