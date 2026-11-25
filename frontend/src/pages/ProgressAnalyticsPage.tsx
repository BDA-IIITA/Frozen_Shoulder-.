import { useEffect, useState } from 'react';
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../services/api';
import { DatasetContext, PersonalProgress, SessionComparisonPanel } from '../components/monitoring/PersonalProgress';
import type { DataSourceMode, DatasetWristReference, Exercise, MovementAnalytics, Participant, ROMProgressItem } from '../types';

type Metric = {
  key: string; baselineKey?: string; label: string; unit: string; description: string; decimals: number;
  value: (item: MovementAnalytics) => number | null | undefined;
};

const metrics: Metric[] = [
  { key: 'median', baselineKey: 'median_rep_excursion_deg', label: 'Median rep excursion', unit: '°', decimals: 1, description: 'Typical rise from the measured starting position to the peak of a completed estimated rep.', value: m => m.median_rep_excursion_deg },
  { key: 'medianPeak', baselineKey: 'median_rep_peak_deg', label: 'Median peak angle', unit: '°', decimals: 1, description: 'Median of the peaks across all completed estimated reps.', value: m => m.median_rep_peak_deg },
  { key: 'reps', baselineKey: 'estimated_repetition_count', label: 'Estimated repetitions', unit: '', decimals: 0, description: 'Sensor-based movement estimates.', value: m => m.estimated_repetition_count },
  { key: 'repSpeed', baselineKey: 'rep_wrist_gyro_mean_rad_s', label: 'Wrist speed during reps', unit: ' rad/s', decimals: 2, description: 'Time-weighted angular speed from recorded rep samples.', value: m => m.rep_wrist_gyro_mean_rad_s },
  { key: 'speed', label: 'Mean wrist speed', unit: ' rad/s', decimals: 2, description: 'Average angular speed across complete windows.', value: m => m.wrist_gyro_mean_rad_s },
  { key: 'jerk', baselineKey: 'wrist_jerk_rms_m_s3', label: '50 Hz wrist jerk RMS', unit: ' m/s³', decimals: 2, description: 'Wrist jerk RMS measures how quickly acceleration changes.', value: m => m.wrist_jerk_rms_m_s3 },
  { key: 'coarseJerk', baselineKey: 'coarse_wrist_jerk_rms_m_s3', label: 'Coarse wrist jerk', unit: ' m/s³', decimals: 2, description: 'Acceleration-magnitude changes during reps with enough wrist samples. Compare sessions captured at similar sampling rates.', value: m => m.coarse_wrist_jerk_rms_m_s3 },
  { key: 'variation', baselineKey: 'rep_duration_sd_s', label: 'Repetition consistency', unit: ' s', decimals: 2, description: 'Variation in estimated repetition duration (standard deviation).', value: m => m.rep_duration_sd_s },
  { key: 'peakVariation', baselineKey: 'peak_angle_sd_deg', label: 'Peak movement consistency', unit: '°', decimals: 1, description: 'Standard deviation of estimated peak movement across repetitions.', value: m => m.peak_angle_sd_deg },
  { key: 'pain', baselineKey: 'pain_rating', label: 'Self-reported pain', unit: '/10', decimals: 0, description: 'Optional rating entered after a live session.', value: m => m.pain_rating },
  { key: 'stiffness', baselineKey: 'stiffness_rating', label: 'Self-reported stiffness', unit: '/10', decimals: 0, description: 'Optional rating entered after a live session.', value: m => m.stiffness_rating },
  { key: 'duration', baselineKey: 'mean_rep_duration_s', label: 'Mean rep duration', unit: ' s', decimals: 2, description: 'Mean elapsed time across completed estimated reps.', value: m => m.mean_rep_duration_s },
  { key: 'torso', baselineKey: 'trunk_peak_deg', label: 'Peak torso rotation', unit: '°', decimals: 1, description: 'Largest recorded change in chest orientation during the session.', value: m => m.trunk_peak_deg },
  { key: 'angle', label: 'Chest-relative excursion', unit: '°', decimals: 1, description: 'Sensor estimate from paired orientation measurements.', value: m => m.relative_excursion_deg },
];

const input = 'mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900';
const replayGroup = (row: ROMProgressItem) => {
  const record = row.movement_analytics?.recording;
  return record ? `${record.participant} · side code ${record.side_code}` : '';
};

function Trend({ metric, data, baseline, personal }: {
  metric: Metric; data: Array<{ session: string; date: string; value: number | null }>; baseline?: number; personal: boolean;
}) {
  const measured = data.filter(row => row.value != null);
  const first = measured[0]?.value;
  const latest = measured[measured.length - 1]?.value;
  const anchor = personal ? baseline : measured.length >= 2 ? first : undefined;
  const change = anchor != null && latest != null ? latest - anchor : null;
  const recent: number[] = [];
  const rolling = data.map(point => {
    if (point.value == null) return { ...point, rolling: null };
    recent.push(point.value);
    const lastThree = recent.slice(-3).sort((a, b) => a - b);
    return { ...point, rolling: lastThree.length === 3 ? lastThree[1] : null };
  });
  const format = (value: number) => `${value.toFixed(metric.decimals)}${metric.unit}`;

  return (
    <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-semibold text-slate-900">{metric.label}</h2>
          </div>
        <div className="text-right"><p className="text-xl font-semibold text-slate-900">{latest != null ? format(latest) : '—'}</p>
          {change != null && <p className="text-xs text-slate-600">{change > 0 ? '+' : ''}{format(change).replace(/%$/, ' pp')} from {personal ? 'personal baseline' : 'first measured recording'}</p>}</div>
      </div>
      {measured.length < 2 ? (
        <p className="mt-2 text-sm text-slate-600">
          First measurement in session {measured[0]?.session}
        </p>
      ) : <div className="mt-4 h-36 text-xs">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rolling} margin={{ left: -18, right: 15, top: 8 }}>
            <CartesianGrid stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="session" tickLine={false} />
            <YAxis domain={['pain', 'stiffness'].includes(metric.key) ? [0, 10] : [0, 'auto']} tickLine={false} />
            <Tooltip formatter={(value: number, name: string) => [format(value), name]}
              labelFormatter={(label, payload) => `${label} · ${payload?.[0]?.payload?.date ?? ''}`} />
            {baseline != null && <ReferenceLine y={baseline} stroke="#64748b" strokeDasharray="3 3" ifOverflow="extendDomain" />}
            {personal && baseline != null && measured.length >= 3 && <Line dataKey="rolling" name="Three-session median" stroke="#64748b" strokeDasharray="4 3" dot={false} isAnimationActive={false} />}
            <Line name={metric.label} type="linear" dataKey="value" stroke="#0f766e" strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>}
    </section>
  );
}

export function ProgressAnalyticsPage({ initialSource = 'live' }: { initialSource?: DataSourceMode }) {
  const [source, setSource] = useState<DataSourceMode>(initialSource);
  const [dataset, setDataset] = useState<DatasetWristReference | null>(null);
  const [patients, setPatients] = useState<Participant[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [rows, setRows] = useState<ROMProgressItem[]>([]);
  const [patient, setPatient] = useState<number>();
  const [exercise, setExercise] = useState('');
  const [group, setGroup] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    api.getDatasetWristReference().then(data => { if (current) setDataset(data); }).catch(() => {});
    return () => { current = false; };
  }, []);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError(false);
    Promise.all([api.getParticipants(), api.getExercises()]).then(([people, library]) => {
      if (!current) return;
      setPatients(people);
      setExercises(library);
      setPatient(value => value ?? people[0]?.id);
      if (!people.length) setLoading(false);
    }).catch(() => { if (current) { setError(true); setLoading(false); } });
    return () => { current = false; };
  }, [retry]);

  useEffect(() => {
    if (patient == null) return;
    let current = true;
    setLoading(true);
    setError(false);
    api.getROMAnalytics(patient).then(data => { if (current) setRows(data); })
      .catch(() => { if (current) { setError(true); setRows([]); } })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [patient, retry]);

  const matchingSource = rows.filter(row => row.data_source === source && row.movement_analytics);
  const exerciseOptions = [...new Set(matchingSource.map(row => row.exercise_key))];
  const selectedExercise = exerciseOptions.includes(exercise) ? exercise : exerciseOptions[exerciseOptions.length - 1] ?? '';
  const matchingExercise = matchingSource.filter(row => row.exercise_key === selectedExercise);
  const groupKey = (row: ROMProgressItem) => source === 'replay' ? replayGroup(row) : row.affected_side;
  const groups = [...new Set(matchingExercise.map(groupKey))];
  const selectedGroup = groups.includes(group) ? group : groups[groups.length - 1];
  const cohort = matchingExercise.filter(row => groupKey(row) === selectedGroup);
  const complete = cohort.filter(row => source !== 'replay' || row.movement_analytics?.replay_complete === true);
  const latestOrientation = [...complete].reverse().find(row => row.movement_analytics?.angle_source)?.movement_analytics;
  const metricKey = (item?: MovementAnalytics | null) => item?.movement_metric ?? 'exercise_projection';
  const personal = source === 'live';
  const latestProgress = [...complete].reverse().find(row => row.rehab_progress?.eligible)?.rehab_progress;
  const anchorInterval = [...complete].reverse().find(row =>
    row.rehab_progress?.measurement_protocol_key === latestProgress?.measurement_protocol_key
    && row.movement_analytics?.wrist_sample_interval_median_s)?.movement_analytics?.wrist_sample_interval_median_s;
  const prepared = metrics.flatMap(metric => {
    const data = complete.map(row => {
      const item = row.movement_analytics!;
      const countSensitive = ['reps', 'variation', 'peakVariation', 'coarseJerk', 'median', 'medianPeak', 'duration', 'repSpeed', 'torso'].includes(metric.key);
      const sameProtocol = latestProgress?.measurement_protocol_key != null
        && row.rehab_progress?.measurement_protocol_key === latestProgress.measurement_protocol_key;
      const sampled = ['coarseJerk', 'repSpeed'].includes(metric.key);
      const interval = item.wrist_sample_interval_median_s;
      const sameRate = !sampled || (!!interval && !!anchorInterval && Math.max(interval, anchorInterval) / Math.min(interval, anchorInterval) <= 1.25);
      const compatible = personal && countSensitive && latestProgress ? sameProtocol && sameRate
        : metric.key !== 'angle' || (item.angle_source === latestOrientation?.angle_source && metricKey(item) === metricKey(latestOrientation));
      return { session: `#${row.session_id}`, date: row.date, value: compatible ? metric.value(item) ?? null : null };
    });
    return data.some(point => point.value != null) ? [{ metric, data, personal, baseline: metric.baselineKey ? latestProgress?.compared?.[metric.baselineKey]?.baseline : undefined }] : [];
  });
  const priorities = personal ? ['median', 'angle', 'medianPeak', 'reps', 'repSpeed', 'speed']
    : ['reps', 'speed', 'jerk', 'angle'];
  const primary = priorities.map(key => prepared.find(item => item.metric.key === key)).find(Boolean) ?? prepared[0];
  const additional = prepared.filter(item => item !== primary);
  const exerciseName = (key: string) => matchingSource.find(row => row.exercise_key === key)?.movement_analytics?.recording?.exercise_name
    ?? exercises.find(item => item.exercise_key === key)?.display_name ?? key;

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Progress Analytics</h1>
      </header>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm font-medium text-slate-600">Data source
          <select aria-label="Data source" className={input} value={source} onChange={event => { setSource(event.target.value as DataSourceMode); setGroup(''); setExercise(''); }}>
            <option value="live">Live ESP32</option><option value="replay">SPARS9x replay</option><option value="demo">Synthetic demo</option>
          </select>
        </label>
        {source !== 'replay' && <label className="text-sm font-medium text-slate-600">Participant
          <select className={input} value={patient ?? ''} onChange={event => setPatient(Number(event.target.value))}>
            {!patients.length && <option value="">No participants</option>}
            {patients.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}
          </select>
        </label>}
        <label className="text-sm font-medium text-slate-600">Exercise
          <select className={input} value={selectedExercise} onChange={event => setExercise(event.target.value)}>
            {!exerciseOptions.length && <option value="">No saved exercises</option>}
            {exerciseOptions.map(key => <option key={key} value={key}>{exerciseName(key)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-600">{source === 'replay' ? 'Recorded participant and side' : 'Shoulder'}
          <select className={input} value={selectedGroup ?? ''} onChange={event => setGroup(event.target.value)}>
            {!groups.length && <option value="">No saved sessions</option>}
            {groups.map(key => <option key={key} value={key}>{key.replace('spars9x_', '').replace(/^./, letter => letter.toUpperCase())}</option>)}
          </select>
        </label>
      </div>

      {loading ? <p role="status" className="text-sm text-slate-600">Loading saved sessions…</p> : error ?
        <p role="alert" className="rounded-xl border bg-white p-5 text-sm text-rose-800">Saved sessions could not be loaded. <button className="font-semibold underline" onClick={() => setRetry(value => value + 1)}>Retry</button></p> :
        <>
          {source !== 'live' && cohort.length > 0 && <p className="text-sm text-slate-600">
            {source === 'replay' ? 'Dataset replay · Complete recordings only' : 'Synthetic demo'}
          </p>}
          {personal && <PersonalProgress sessions={complete} />}
          {primary ? <Trend {...primary} /> : <p className="rounded-xl border bg-white p-5 text-sm text-slate-600">No comparable measurements yet.</p>}
          {additional.length > 0 && <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-semibold">More measurements</summary>
            <div className="mt-4 grid gap-3 md:grid-cols-2">{additional.map(item => <div key={item.metric.key}><Trend {...item} /><p className="mt-1 px-2 text-xs text-slate-600">{item.metric.description}</p></div>)}</div>
          </details>}
          <DatasetContext dataset={dataset} label={source === 'replay' ? cohort[0]?.movement_analytics?.recording?.label
            : source === 'live' && selectedExercise === 'flexion' ? 8 : undefined} />
          <SessionComparisonPanel sessions={personal && latestProgress ? complete.filter(row =>
            row.rehab_progress?.measurement_protocol_key === latestProgress.measurement_protocol_key) : complete} />
          {!!cohort.length && <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-semibold">Saved sessions · {cohort.length}</summary>
            <ul className="mt-2 divide-y divide-slate-100 text-sm">
              {[...cohort].reverse().map(row => <li key={row.session_id} className="flex flex-wrap justify-between gap-2 py-2.5 text-slate-600">
                <span><b className="text-slate-900">Session #{row.session_id}</b> · {row.date}</span>
                <span>{Number.isFinite(row.duration_seconds) ? `${row.duration_seconds.toFixed(1)} s` : "Duration unavailable"}{source === 'replay' && !row.movement_analytics?.replay_complete ? ' · partial replay' : ''}</span>
              </li>)}
            </ul>
          </details>}
        </>}
      <p className="text-xs text-slate-500">Academic prototype · Experimental performance index</p>
    </div>
  );
}
