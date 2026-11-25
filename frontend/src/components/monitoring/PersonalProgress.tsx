import { useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { DatasetWristReference, RehabComponent, RehabProgress, ROMProgressItem, SessionComparison } from '../../types';
import { api } from '../../services/api';
import { measurement } from './MovementAnalytics';

const componentLabels: Record<RehabComponent, string> = {
  mobility: 'Mobility', control: 'Movement control', posture: 'Torso control', symptoms: 'Pain and stiffness',
};
const measureLabels: Record<string, string> = {
  median_rep_excursion_deg: 'Median rep excursion', median_rep_peak_deg: 'Median peak angle', peak_angle_sd_deg: 'Peak movement variation',
  rep_duration_sd_s: 'Rep duration variation', mean_rep_duration_s: 'Mean rep duration',
  trunk_peak_deg: 'Peak torso rotation', pain_rating: 'Pain', stiffness_rating: 'Stiffness',
  coarse_wrist_jerk_rms_m_s3: 'Coarse wrist jerk', wrist_jerk_rms_m_s3: '50 Hz wrist jerk',
  rep_wrist_gyro_mean_rad_s: 'Wrist speed during reps', estimated_repetition_count: 'Estimated repetitions',
  relative_excursion_deg: 'Session excursion', wrist_gyro_peak_rad_s: 'Peak wrist speed',
  movement_duration_s: 'Time in estimated reps', rom: 'Session excursion',
};
const referenceLabels: Record<string, { label: string; unit: string }> = {
  labeled_bout_duration_s: { label: 'Labeled bout duration', unit: 's' },
  gyro_mean_rad_s: { label: 'Mean wrist angular speed', unit: 'rad/s' },
  gyro_max_rad_s: { label: 'Peak wrist angular speed', unit: 'rad/s' },
  jerk_rms_m_s3: { label: 'Wrist jerk RMS', unit: 'm/s³' },
};
const panel = 'rounded-2xl border border-slate-200 bg-white p-5';
const utcToday = () => new Date().toISOString().slice(0, 10);
const demoDaily = [
  { date: '2026-11-02', score: 51 },
  { date: '2026-11-05', score: 55 },
  { date: '2026-11-09', score: 58 },
  { date: '2026-11-12', score: 56 },
  { date: '2026-11-16', score: 63 },
  { date: '2026-11-19', score: 67 },
];
const demoWeekly = [
  { date: '2026-11-02', score: 53 },
  { date: '2026-11-09', score: 57 },
  { date: '2026-11-16', score: 65 },
];
const defaultWeights = { mobility: .4, control: .25, posture: .15, symptoms: .2 };

function IndexTrend({ sessions, weights = defaultWeights }: {
  sessions: ROMProgressItem[]; weights?: RehabProgress['weights'];
}) {
  const [period, setPeriod] = useState<'daily' | 'weekly'>('daily');
  const [showExample, setShowExample] = useState(true);
  const days = new Map<string, number>();
  const weeks = new Map<string, number>();
  for (const row of sessions) {
    const progress = row.rehab_progress;
    if (progress?.daily_score != null) days.set(row.date, progress.daily_score);
    if (progress?.weekly_score != null && progress.week_start) weeks.set(progress.week_start, progress.weekly_score);
  }
  const daily = Array.from(days, ([date, score]) => ({ date, score }));
  const isExample = daily.length === 0 && showExample;
  const displayed = isExample ? (period === 'daily' ? demoDaily : demoWeekly) :
    period === 'daily' ? daily.slice(-21) : Array.from(weeks, ([date, score]) => ({ date, score })).slice(-12);
  const today = daily.find(point => point.date === utcToday());
  return (
    <section className={panel}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="font-semibold">Performance index trend</h2>
          <p className="text-xs text-slate-600">{isExample ? 'Sample data · For demonstration only' : period === 'daily' ? 'Median of comparable sessions each UTC day.' : 'Median of daily scores. Weeks start Monday (UTC).'}</p></div>
        <label className="text-sm text-slate-700">Interval{' '}
          <select aria-label="Interval" className="rounded-lg border px-2 py-1" value={period} onChange={event => setPeriod(event.target.value === 'weekly' ? 'weekly' : 'daily')}>
            <option value="daily">Daily</option><option value="weekly">Weekly</option>
          </select>
        </label>
      </div>
      {!daily.length && <label className="mt-3 inline-flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={showExample} onChange={event => setShowExample(event.target.checked)} />
        Show sample scores
      </label>}
      {today && <p className="mt-2 text-sm font-semibold">Today's score {measurement(today.score, ' pts')}</p>}
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_17rem]">
        {displayed.length ? <div className="h-44 text-xs">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayed}>
              <XAxis dataKey="date" tickFormatter={date => date.slice(5)} />
              <YAxis domain={[0, 100]} />
              <Tooltip formatter={(value: number) => [measurement(value, ' pts'), isExample ? 'Sample score' : 'Performance index']} />
              <Line type="linear" dataKey="score" stroke="#0f766e" dot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div> : <div className="flex h-44 items-stretch gap-3 text-xs text-slate-600" aria-label="Empty score graph, zero to one hundred points">
          <div className="flex flex-col justify-between py-1 text-right tabular-nums"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div>
          <div className="grid flex-1 place-items-center rounded-lg border border-slate-200 bg-slate-50 px-4 text-center">
            <p>No recorded scores yet.</p>
          </div>
        </div>}
        <div className="rounded-xl bg-teal-50 p-4 text-sm text-teal-950">
          <h3 className="font-semibold">Score formula</h3>
          <p className="mt-2 leading-relaxed">Score = {Object.entries(weights).map(([key, weight]) =>
            `${Number((weight * 100).toFixed(2))}% × ${componentLabels[key as RehabComponent]}`).join(' + ')}</p>
          <p className="mt-2 text-xs">Partial scores use the weighted average of available components. The index is experimental.</p>
        </div>
      </div>
    </section>
  );
}

export function PersonalProgress({ sessions }: { sessions: ROMProgressItem[] }) {
  const lastSaved = sessions[sessions.length - 1];
  const latest = [...sessions].reverse().find(row => row.rehab_progress?.eligible) ?? lastSaved;
  const progress = latest?.rehab_progress;
  const metrics = latest?.movement_analytics;
  const values = progress?.compared ?? {};
  const latestScored = [...sessions].reverse().find(row => row.rehab_progress?.score != null
    && (!progress?.measurement_protocol_key || row.rehab_progress.measurement_protocol_key === progress.measurement_protocol_key));
  const scoreRows = latestScored ? sessions.filter(row =>
    row.rehab_progress?.score_comparison_key === latestScored.rehab_progress?.score_comparison_key) : [];
  const direction = {
    improving: 'Median movement was above the baseline range on the last three measured days.',
    declining: 'Median movement was below the baseline range on the last three measured days.',
    stable: 'Median movement remained within the baseline range on the last three measured days.',
    inconclusive: 'Recent median movement spans the baseline range. A direction is inconclusive.',
    insufficient: 'A trend classification needs three measured days after the baseline.',
  }[progress?.mobility_trend ?? 'insufficient'];
  const components = (Object.keys(componentLabels) as RehabComponent[]).filter(key => progress?.components?.[key] != null);
  const priority = ['median_rep_excursion_deg', 'coarse_wrist_jerk_rms_m_s3', 'wrist_jerk_rms_m_s3', 'pain_rating',
    'peak_angle_sd_deg', 'rep_duration_sd_s', 'stiffness_rating'];
  const deltas = Object.entries(values);
  const highlights = priority.flatMap(key => deltas.filter(([id]) => id === key)).slice(0, 3);
  const otherDeltas = deltas.filter(([key]) => !highlights.some(([primary]) => key === primary));
  const deltaRows = (entries: typeof deltas) => entries.map(([key, value]) => <div className="flex flex-wrap justify-between gap-2 border-b border-slate-100 py-2 text-sm" key={key}>
    <dt className="text-slate-700">{measureLabels[key] ?? key}</dt>
    <dd className="font-medium tabular-nums">{measurement(value.baseline, value.unit === '/10' ? '' : ` ${value.unit}`, 2)} → {measurement(value.current, ` ${value.unit}`, 2)} ({value.change > 0 ? '+' : ''}{value.change.toFixed(2)})</dd>
  </div>);
  if (!latest) return <IndexTrend sessions={[]} />;

  return (
    <>
      <IndexTrend sessions={scoreRows} weights={progress?.weights} />
      <section className={panel}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><h2 className="text-lg font-semibold">Personal progress</h2>
            <p className="text-sm text-slate-600">{latest !== lastSaved ? 'Latest comparable session' : 'Latest session'} #{latest.session_id} · {latest.date}</p>
            {progress?.is_baseline_session ? <p className="mt-2 text-sm text-slate-600">This session contributes to your baseline.</p>
              : progress?.score_change != null && <p className="mt-2 text-sm font-semibold text-teal-800">
                {progress.score_change > 0 ? '+' : ''}{measurement(progress.score_change, ' points')} vs baseline
              </p>}
          </div>
          {progress?.score != null && <div className="rounded-xl bg-teal-50 px-4 py-3">
            <p className="text-xs font-semibold text-teal-900">{progress?.partial ? 'Partial performance index' : 'Experimental performance index'}</p>
            <p className="mt-1 text-2xl font-semibold text-teal-950">{measurement(progress.score, ' / 100')}</p>
            {progress?.score != null && progress.partial && <p className="text-xs text-teal-800">{Math.round((progress.coverage ?? 0) * 100)}% of planned weight measured</p>}
          </div>}
        </div>
        <p className="my-3 text-sm text-slate-600">
          {progress?.baseline_ready ? `Baseline: sessions ${progress.baseline_session_ids.map(id => '#' + id).join(', ')}.`
            : progress?.eligible ? `Establishing baseline · ${progress.baseline_session_ids.length}/3 comparable sessions.`
            : 'A comparable live session is needed to start the baseline.'}
        </p>
        {metrics?.prescribed_repetitions != null && <p className="my-2 text-sm text-slate-700">
          Prescribed reps {metrics.prescribed_repetitions} · Estimated completed {metrics.estimated_repetition_count ?? '—'}
          {progress?.rep_completion != null && ` · ${Math.round(100 * progress.rep_completion)}% of plan`}
        </p>}
        {metrics?.prescribed_angle_deg != null && <p className="my-2 text-sm text-slate-700">Prescribed rep excursion target {metrics.prescribed_angle_deg}°</p>}
        {components.length > 0 && <dl className="flex flex-wrap gap-x-6 gap-y-3 border-t border-slate-100 pt-3">
          {components.map(key => <div key={key}>
            <dt className="text-xs font-semibold text-slate-700">{componentLabels[key]}</dt>
            <dd className="text-lg font-semibold">{measurement(progress?.components?.[key], ' pts')}</dd>
          </div>)}
        </dl>}
        <details className="mt-4 text-xs text-slate-600">
          <summary className="cursor-pointer font-semibold">How the index is calculated</summary>
          <p className="mt-2">Mobility uses the prescribed angle when supplied, capped at 100 points. Otherwise, it uses the personal baseline. Control and torso rotation are scored relative to baseline, with 50 points at baseline. Pain and stiffness convert from 0–10 ratings to 100–0 points. Components with data are weighted proportionally. A partial index needs at least two components including a measured movement component and at least 40% of configured weight. This is an experimental index for recorded performance.</p>
        </details>
      </section>
      {progress?.baseline_ready && <section className={panel}>
        <h2 className="font-semibold">Change from your baseline</h2>
        <p className="mt-1 text-sm text-slate-600">{direction}</p>
        {highlights.length > 0 && <dl className="mt-2">{deltaRows(highlights)}</dl>}
        {otherDeltas.length > 0 && <details className="mt-3">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">More baseline changes</summary>
          <dl className="mt-1">{deltaRows(otherDeltas)}</dl>
        </details>}
      </section>}
    </>
  );
}

export function SessionComparisonPanel({ sessions }: { sessions: ROMProgressItem[] }) {
  const current = sessions[sessions.length - 1]?.session_id;
  const [selection, setSelection] = useState<number>();
  const prior = sessions.slice(0, -1);
  const other = prior.find(row => row.session_id === selection)?.session_id ?? prior[prior.length - 1]?.session_id;
  const [result, setResult] = useState<SessionComparison | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setResult(null);
    setError(false);
    if (current && other) api.compareSessions(other, current).then(value => {
      if (active) setResult(value);
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [current, other]);

  if (!current || !other) return null;
  return (
    <details className={panel}>
      <summary className="cursor-pointer font-semibold">Compare saved sessions</summary>
      <label className="mt-3 block text-sm">Compare latest session #{current} with{' '}
        <select className="rounded-lg border px-2 py-1" value={other} onChange={event => setSelection(Number(event.target.value))}>
          {prior.map(row => <option key={row.session_id} value={row.session_id}>#{row.session_id} · {row.date}</option>)}
        </select>
      </label>
      {error ? <p role="status" className="mt-2 text-sm">Comparison could not be loaded.</p>
        : !result ? <p role="status" className="mt-2 text-sm">Loading comparison…</p>
        : <div className="mt-2 space-y-1 text-sm text-slate-700">
          {result.warnings?.map(warning => <p key={warning}>{warning}</p>)}
          {Object.entries(result.movement_changes ?? {}).filter(([key]) => !!measureLabels[key]).map(([key, value]) =>
            <p key={key}>{measureLabels[key]} changed by {value > 0 ? '+' : ''}{value}</p>)}
          {!Object.keys(result.movement_changes ?? {}).some(key => !!measureLabels[key]) && <p>No compatible measurements for these sessions.</p>}
        </div>}
    </details>
  );
}

export function DatasetContext({ dataset, label }: { dataset: DatasetWristReference | null; label?: number }) {
  if (label == null) return null;
  const reference = dataset?.labels?.[label];
  return (
    <details className={panel}>
      <summary className="cursor-pointer font-semibold">SPARS9x wrist context · activity {label}</summary>
      {reference ? <>
        <p className="mt-3 text-sm text-slate-600">{reference.participants} recorded participants · {reference.windows} windows at {dataset?.sampling_hz} Hz. The range is the 10th to 90th percentile of participant medians.</p>
        <dl className="mt-2 text-sm">
          {Object.entries(reference.metrics).map(([key, value]) => <div key={key} className="flex flex-wrap justify-between gap-2 border-b border-slate-100 py-2">
            <dt>{referenceLabels[key]?.label ?? key}</dt>
            <dd>Median {measurement(value.median, ` ${referenceLabels[key]?.unit ?? ''}`, 2)} · Range {value.p10.toFixed(2)}–{value.p90.toFixed(2)}</dd>
          </div>)}
        </dl>
        <p className="mt-3 text-xs text-slate-600">Bout duration may include pauses. These smartwatch values provide context for replay. Hardware, placement and sampling affect measurements, so they are kept separate from live scores and personal goals.</p>
      </> : <p className="mt-2 text-sm text-slate-600">Dataset wrist ranges are unavailable.</p>}
    </details>
  );
}
