import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { WristSignal, MovementAnalytics as Metrics } from '../../types';

export function measurement(value: number | null | undefined, unit: string, decimals = 1) {
  return value == null ? 'Unavailable' : `${value.toFixed(decimals)}${unit}`;
}

export function WristChart({ data }: { data: Array<WristSignal & { time_s: number }> }) {
  return (
    <div className="h-56 w-full text-xs">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="time_s" tickFormatter={time => `${time}s`} />
          <YAxis yAxisId="acc" unit=" m/s²" width={65} />
          <YAxis yAxisId="gyro" orientation="right" unit=" rad/s" width={65} />
          <Tooltip />
          <Line yAxisId="acc" dataKey="acceleration_m_s2" name="Acceleration (m/s²)" stroke="#0d9488" dot={false} isAnimationActive={false} />
          <Line yAxisId="gyro" dataKey="gyro_rad_s" name="Angular speed (rad/s)" stroke="#d97706" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export const movementLabels: Record<string, string> = {
  estimated_repetition_count: 'Estimated repetitions',
  movement_duration_s: 'Movement time (s)',
  rep_duration_sd_s: 'Rep duration SD (s)',
  wrist_gyro_peak_rad_s: 'Peak wrist speed (rad/s)',
  wrist_jerk_rms_m_s3: 'Wrist jerk RMS (m/s³)',
  pain_rating: 'Pain rating',
  relative_excursion_deg: 'Relative excursion (°)',
};

export function MovementAnalytics({ metrics }: { metrics?: Metrics | null }) {
  const entries = [
    ['Peak wrist speed', metrics?.wrist_gyro_peak_rad_s, ' rad/s', 2],
    ['Mean wrist speed', metrics?.wrist_gyro_mean_rad_s, ' rad/s', 2],
    ['50 Hz wrist jerk', metrics?.wrist_jerk_rms_m_s3, ' m/s³', 2],
    ['Coarse wrist jerk', metrics?.coarse_wrist_jerk_rms_m_s3, ' m/s³', 2],
    ['Peak torso rotation', metrics?.trunk_peak_deg, '°', 1],
    ['Typical rep duration (last 3)', metrics?.repetition_review?.median_duration_s, ' s', 2],
    ['Time in estimated reps', metrics?.movement_duration_s, ' s', 1],
    ['Rep duration variation', metrics?.rep_duration_sd_s, ' s', 2],
    ['Pain', metrics?.pain_rating, '/10', 0],
    ['Stiffness', metrics?.stiffness_rating, '/10', 0],
  ] as const;
  return (
    <section className="space-y-3 text-sm">
      {entries.some(([, value]) => value != null) && <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {entries.map(([label, value, unit, digits]) => value != null && <div key={label}>
          <dt className="text-slate-600">{label}</dt>
          <dd className="font-semibold">{measurement(value, unit, digits)}</dd>
        </div>)}
      </dl>}
      {metrics?.movement_baseline && (
        <div className="text-slate-600">
          <p className="font-semibold">Change from session #{metrics.movement_baseline.session_id}</p>
          <ul>{Object.entries(metrics.movement_baseline.changes).map(([key, value]) =>
            <li key={key}>{movementLabels[key] ?? key.replace(/_/g, ' ')} {value > 0 ? '+' : ''}{value}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
