import { useEffect, useState } from 'react';
import { ArrowRight, CalendarDays, Compass, Repeat } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { MetricCard } from '../components/common/MetricCard';
import type { DashboardSummary, NavItemKey, ROMProgressItem } from '../types';
import { api } from '../services/api';

const sourceLabels = { live: 'Live ESP32', replay: 'Replay', demo: 'Demo' };

export function OverviewPage({ onNavigate }: { onNavigate: (tab: NavItemKey) => void }) {
  const [data, setData] = useState<{ summary: DashboardSummary; history: ROMProgressItem[] }>();
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let current = true;
    setError(false);
    Promise.all([api.getDashboardSummary(1), api.getROMAnalytics(1)]).then(([summary, history]) => {
      if (current) setData({ summary, history });
    }).catch(() => { if (current) setError(true); });
    return () => { current = false; };
  }, [retry]);

  const summary = data?.summary;
  const history = data?.history ?? [];
  const latest = [...history].reverse().find(row => row.data_source === 'live' && row.movement_analytics?.angle_source);
  const protocol = (row: ROMProgressItem) => row.movement_analytics?.movement_metric ?? 'exercise_projection';
  const comparable = latest ? history.filter(row => row.data_source === 'live' &&
    row.exercise_key === latest.exercise_key && row.affected_side === latest.affected_side &&
    row.movement_analytics?.angle_source === latest.movement_analytics?.angle_source &&
    protocol(row) === protocol(latest)) : [];
  const change = summary?.rom_change_vs_prior;
  const sides = new Map(history.map(row => [row.session_id, row.affected_side]));

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Overview</h1>
        <button onClick={() => onNavigate('monitoring')}
          className="inline-flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800">
          Start Monitoring Session <ArrowRight className="h-4 w-4" />
        </button>
      </header>
      {error ? <p role="alert" className="text-sm text-rose-800">Overview couldn’t load. <button className="font-semibold underline" onClick={() => setRetry(value => value + 1)}>Retry</button></p>
        : !summary ? <p role="status" className="text-sm text-slate-600">Loading overview…</p> : <>
          {(latest || summary.total_sessions > 0) && <div className="grid gap-3 sm:grid-cols-3">
            {latest && <MetricCard title="Latest excursion" value={summary.latest_rom.toFixed(1)} unit="°" icon={Compass}
              subtitle={change == null ? undefined : change === 0 ? 'Unchanged from last comparable session'
                : `${change > 0 ? 'Up' : 'Down'} ${Math.abs(change).toFixed(1)}° from last comparable session`} />}
            {summary.total_sessions > 0 && <>
              <MetricCard title="Repetitions" value={summary.total_repetitions} subtitle="Estimated · live sessions" icon={Repeat} />
              <MetricCard title="Live sessions" value={summary.total_sessions} icon={CalendarDays} />
            </>}
          </div>}

          <section className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Excursion over time</h2>
              <button className="text-sm font-medium text-teal-700 hover:underline" onClick={() => onNavigate('analytics')}>View progress</button>
            </div>
            {comparable.length ? <div className="h-52 w-full sm:h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={comparable} margin={{ top: 8, right: 10, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="date" tickFormatter={date => date.slice(5)} tickLine={false} axisLine={false} fontSize={12} minTickGap={24} />
                  <YAxis width={42} unit="°" tickLine={false} axisLine={false} fontSize={12} />
                  <Tooltip formatter={(value: number) => [`${value}°`, 'Excursion']} />
                  <Line dataKey="rom" stroke="#0f766e" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div> : <p className="py-5 text-sm text-slate-600">Save a live session with an angle reading to start this trend.</p>}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-semibold">Recent sessions</h2>
              <button className="text-sm font-medium text-teal-700 hover:underline" onClick={() => onNavigate('sessions')}>All sessions</button>
            </div>
            {summary.recent_sessions.length ? <ul className="mt-2 divide-y divide-slate-100">
              {summary.recent_sessions.map(session => {
                const metrics = session.movement_analytics;
                const side = metrics?.recording ? `Side ${metrics.recording.side_code}` : sides.get(session.id);
                const excursion = metrics?.relative_excursion_deg;
                const reps = metrics?.estimated_repetition_count;
                return <li key={session.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 text-sm">
                  <div><p className="font-medium text-slate-900">{session.exercise_name}</p>
                    <p className="text-slate-600">{session.date}{side && ` · ${side}`}</p></div>
                  <div className="sm:text-right">
                    {(excursion != null || reps != null) && <p className="font-medium text-slate-900">{[
                      excursion == null ? null : `${excursion.toFixed(1)}°`, reps == null ? null : `${reps} est. reps`,
                    ].filter(Boolean).join(' · ')}</p>}
                    <p className="text-slate-600">{sourceLabels[session.data_source]} · Saved</p>
                  </div>
                </li>;
              })}
            </ul> : <p className="py-4 text-sm text-slate-600">No saved sessions yet.</p>}
          </section>
        </>}
    </div>
  );
}
