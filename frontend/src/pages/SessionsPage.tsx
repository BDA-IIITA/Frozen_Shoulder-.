import { SessionTimeline } from '../components/monitoring/SessionTimeline';
import { MovementAnalytics, measurement, WristChart, movementLabels } from '../components/monitoring/MovementAnalytics';
import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  X,
  Eye,
  Columns
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from 'recharts';
import { SessionRecord, SessionComparison } from '../types';
import { api } from '../services/api';

export const SessionsPage: React.FC = () => {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [filterExercise, setFilterExercise] = useState<string>('all');
  const [filterSource, setFilterSource] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  // Detail Modal
  const [activeSession, setActiveSession] = useState<SessionRecord | null>(null);
  const [sessionSamples, setSessionSamples] = useState<Array<{ index: number; angle: number }>>([]);
  const [sampleStatus, setSampleStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const detailDialog = useRef<HTMLDialogElement>(null);

  // Comparison State
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [sessionAId, setSessionAId] = useState<number | ''>('');
  const [sessionBId, setSessionBId] = useState<number | ''>('');
  const [comparisonResult, setComparisonResult] = useState<SessionComparison | null>(null);
  const [comparingLoading, setComparingLoading] = useState(false);

  const loadSessions = async () => {
    try {
      setLoading(true);
      setLoadError(false);
      const data = await api.getSessions({
        exercise_key: filterExercise !== 'all' ? filterExercise : undefined,
        data_source: filterSource !== 'all' ? filterSource : undefined,
      });
      setSessions(data);
      if (data.length >= 2) {
        setSessionAId(data[1].id);
        setSessionBId(data[0].id);
      }
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [filterExercise, filterSource]);

  useEffect(() => {
    if (!activeSession) return;
    const dialog = detailDialog.current;
    dialog?.showModal();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setSampleStatus('error');
      controller.abort();
    }, 10000);
    api.getSessionSamples(activeSession.id, controller.signal).then(samples => {
      if (controller.signal.aborted) return;
      setSessionSamples(samples.map((sample, index) => ({
        index: index + 1,
        angle: activeSession.exercise_key === 'abduction' ? sample.abduction_angle : sample.flexion_angle,
      })));
      setSampleStatus('ready');
    }).catch(() => {
      if (!controller.signal.aborted) setSampleStatus('error');
    }).finally(() => window.clearTimeout(timeout));
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
      dialog?.close();
    };
  }, [activeSession]);

  function handleViewDetails(session: SessionRecord) {
    setSampleStatus('loading');
    setSessionSamples([]);
    setActiveSession(session);
  }

  // Run Comparison
  const handleRunComparison = async () => {
    if (!sessionAId || !sessionBId) return;
    try {
      setComparingLoading(true);
      const res = await api.compareSessions(Number(sessionAId), Number(sessionBId));
      setComparisonResult(res);
    } catch (err: any) {
      alert(`Comparison failed: ${err.message}`);
    } finally {
      setComparingLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6">
      {/* Title & Comparison Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Rehabilitation Sessions</h1>
        <button
          onClick={() => {
            setCompareModalOpen(true);
            if (sessionAId && sessionBId) handleRunComparison();
          }}
          disabled={sessions.length < 2}
          className="inline-flex items-center space-x-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          <Columns className="w-4 h-4" />
          <span>Compare sessions</span>
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <select aria-label="Exercise filter" value={filterExercise} onChange={event => setFilterExercise(event.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="all">All exercises</option>
          <option value="flexion">Shoulder flexion</option>
          <option value="abduction">Shoulder abduction</option>
          <option value="external_rotation">External rotation</option>
          <option value="internal_rotation">Internal rotation</option>
        </select>
        <select aria-label="Source filter" value={filterSource} onChange={event => setFilterSource(event.target.value)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="all">All sources</option>
          <option value="live">Live ESP32</option><option value="replay">Dataset replay</option><option value="demo">Synthetic demo</option>
        </select>
      </div>

      <section aria-label="Saved sessions" className="rounded-2xl border border-slate-200 bg-white px-4 sm:px-6">
        {loading ? <p role="status" className="py-5 text-sm text-slate-600">Loading sessions…</p>
          : loadError ? <p role="alert" className="py-5 text-sm text-rose-800">Sessions couldn’t load. <button className="font-semibold underline" onClick={loadSessions}>Retry</button></p>
          : !sessions.length ? <p className="py-5 text-sm text-slate-600">No sessions match these filters.</p>
          : <ul className="divide-y divide-slate-100">
            {sessions.map(session => {
              const metrics = session.movement_analytics;
              const reps = metrics?.estimated_repetition_count;
              const excursion = metrics?.relative_excursion_deg;
              const side = metrics?.recording ? `Side ${metrics.recording.side_code}` : session.affected_side;
              const source = { live: 'Live ESP32', replay: 'Replay', demo: 'Demo' }[session.data_source];
              return <li key={session.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 py-3 text-sm sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto] sm:py-4">
                <div className="min-w-0">
                  <p className="font-semibold capitalize text-slate-900">{metrics?.recording?.exercise_name ?? session.exercise_key.replace(/_/g, ' ')}</p>
                  <p className="text-slate-600">{new Date(session.start_time).toLocaleDateString([], { dateStyle: 'medium' })} · {side} · {source}</p>
                </div>
                {(reps != null || excursion != null || session.status !== 'completed') && <p className="row-start-2 text-slate-700 sm:row-auto">
                  {[reps == null ? null : `${reps} est. reps`, excursion == null ? null : measurement(excursion, '°')].filter(Boolean).join(' · ')}
                  {session.status !== 'completed' && <span className="ml-1 capitalize text-slate-600">{session.status.replace(/_/g, ' ')}</span>}
                </p>}
                <button onClick={() => handleViewDetails(session)}
                  className="col-start-2 row-start-1 inline-flex items-center justify-end gap-1.5 font-semibold text-teal-700 hover:underline sm:col-start-3">
                  <Eye className="h-4 w-4" />Details
                </button>
              </li>;
            })}
          </ul>}
      </section>

      {/* Session Detail Drawer / Modal */}
      {activeSession && (
        <dialog ref={detailDialog} aria-labelledby="session-detail-title"
          onCancel={event => { event.preventDefault(); setActiveSession(null); }}
          className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white shadow-xl backdrop:bg-slate-900/50">
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-4 py-3 sm:px-6">
              <div>
                <span className="text-[10px] font-bold text-teal-700 uppercase">
                  Session Detail #{activeSession.id}
                </span>
                <h3 id="session-detail-title" className="font-bold text-slate-900 text-lg capitalize">
                  {activeSession.movement_analytics?.recording?.exercise_name ?? activeSession.exercise_key.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm capitalize text-slate-600">
                  {activeSession.movement_analytics?.recording ? `Side ${activeSession.movement_analytics.recording.side_code}` : activeSession.affected_side}
                  {' · '}{activeSession.data_source === 'live' ? 'Live ESP32' : activeSession.data_source}
                </p>
              </div>
              <button type="button" aria-label="Close session details" autoFocus onClick={() => setActiveSession(null)} className="rounded p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700">
                <X className="w-5 h-5" />
              </button>
            </div>

          <div className="space-y-4 p-4 sm:p-6">
            <dl className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
              {[
                ['Excursion', activeSession.movement_analytics?.relative_excursion_deg, '°'],
                ['Estimated reps', activeSession.movement_analytics?.estimated_repetition_count, ''],
                ['Duration', activeSession.duration_seconds, ' s'],
              ].map(([label, value, unit]) => typeof value === 'number' && <div key={label}>
                <dt className="text-slate-600">{label}</dt>
                <dd className="text-lg font-semibold">{measurement(value, String(unit), unit === '' ? 0 : 1)}</dd>
              </div>)}
            </dl>

            <details className="rounded-lg border border-slate-200 px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium text-slate-800">Movement details and sensor traces</summary>
              <div className="mt-3 space-y-3">
            {activeSession.movement_analytics?.angle_source && <p className="text-sm text-slate-600">Angle range {activeSession.min_angle}°–{activeSession.max_angle}°</p>}
            <MovementAnalytics metrics={activeSession.movement_analytics} />
            {activeSession.movement_analytics?.repetition_timeline && (
              <SessionTimeline metrics={activeSession.movement_analytics}
                duration={activeSession.duration_seconds} elapsed={activeSession.duration_seconds} />
            )}
            {!!activeSession.movement_analytics?.wrist_trace?.length && (
              <div><h3 className="text-sm font-semibold">Saved wrist signals</h3>
                <WristChart data={activeSession.movement_analytics.wrist_trace} /></div>
            )}
            {/* Time-series Kinematic Trajectory */}
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <h4 className="text-xs font-bold text-slate-900 mb-2">Saved angle samples</h4>
              {sampleStatus === 'loading' ? (
                <p role="status" className="text-xs text-slate-500">Loading angle samples…</p>
              ) : sampleStatus === 'error' ? (
                <p role="status" className="text-xs text-amber-800">Couldn’t load angle samples. Reopen details to retry.</p>
              ) : sessionSamples.length > 0 ? (
                <div className="h-44 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sessionSamples}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="index" stroke="#94a3b8" fontSize={9} />
                      <YAxis stroke="#94a3b8" fontSize={9} unit="°" />
                      <Tooltip />
                      <Line type="monotone" dataKey="angle" stroke="#0d9488" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-32 flex items-center justify-center text-xs text-slate-400">
                  No saved angle samples.
                </div>
              )}
            </div>

              </div>
            </details>

            {/* Consistency & Notes */}
            <div className="space-y-2 text-xs">
              {activeSession.avg_rep_duration != null && <div className="flex justify-between p-2 rounded bg-slate-50">
                <span className="text-slate-500">Average Rep Duration:</span>
                <span className="font-semibold text-slate-900">{activeSession.avg_rep_duration}s</span>
              </div>}
              {activeSession.notes && (
                <div className="p-2.5 rounded bg-teal-50/50 border border-teal-100 text-slate-700">
                  <strong>Notes:</strong> {activeSession.notes}
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                onClick={() => setActiveSession(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </dialog>
      )}

      {/* Comparison Modal */}
      {compareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="max-h-[calc(100dvh-2rem)] w-full max-w-2xl space-y-4 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-xl sm:p-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Compare Rehabilitation Sessions</h3>
              <button onClick={() => setCompareModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Selectors */}
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-slate-500 font-semibold mb-1">Baseline Session (A)</label>
                <select
                  value={sessionAId}
                  onChange={(e) => setSessionAId(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-slate-50"
                >
                  {sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.id} — {s.exercise_key} ({measurement(s.movement_analytics?.relative_excursion_deg, '°')}) [{s.data_source}]
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-500 font-semibold mb-1">Follow-up Session (B)</label>
                <select
                  value={sessionBId}
                  onChange={(e) => setSessionBId(Number(e.target.value))}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-slate-50"
                >
                  {sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.id} — {s.exercise_key} ({measurement(s.movement_analytics?.relative_excursion_deg, '°')}) [{s.data_source}]
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-center">
              <button
                onClick={handleRunComparison}
                disabled={comparingLoading || sessionAId === sessionBId}
                className="bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-2 rounded-lg"
              >
                {comparingLoading ? 'Analyzing...' : 'Calculate Comparison'}
              </button>
            </div>

            {/* Comparison Results Card */}
            {comparisonResult && (
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3 text-xs">
                {/* Warnings banner */}
                {comparisonResult.warnings.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 text-amber-800 p-2.5 rounded-lg flex items-start space-x-2">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-bold">Comparability Warning:</div>
                      {comparisonResult.warnings.map((w, i) => (
                        <div key={i}>• {w}</div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white p-3 rounded-lg border border-slate-200">
                    <div className="text-[10px] text-slate-400 font-bold uppercase">Session #{comparisonResult.session_a.id}</div>
                    <div className="font-bold text-slate-900 mt-1 capitalize">{comparisonResult.session_a.exercise_key}</div>
                    <div className="text-xl font-bold text-slate-800 mt-2">{measurement(comparisonResult.session_a.movement_analytics?.relative_excursion_deg, '°')}</div>
                    <div className="text-slate-500 mt-1">{comparisonResult.session_a.movement_analytics?.estimated_repetition_count ?? '—'} estimated reps</div>
                  </div>

                  <div className="bg-white p-3 rounded-lg border border-slate-200">
                    <div className="text-[10px] text-slate-400 font-bold uppercase">Session #{comparisonResult.session_b.id}</div>
                    <div className="font-bold text-slate-900 mt-1 capitalize">{comparisonResult.session_b.exercise_key}</div>
                    <div className="text-xl font-bold text-teal-700 mt-2">{measurement(comparisonResult.session_b.movement_analytics?.relative_excursion_deg, '°')}</div>
                    <div className="text-slate-500 mt-1">{comparisonResult.session_b.movement_analytics?.estimated_repetition_count ?? '—'} estimated reps</div>
                  </div>
                </div>

                {Object.entries(comparisonResult.movement_changes ?? {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between px-2">
                    <span>{movementLabels[key] ?? key}</span><strong>{value > 0 ? '+' : ''}{value}</strong>
                  </div>
                ))}
                <div className="p-3 bg-teal-50 border border-teal-100 rounded-lg flex items-center justify-between">
                  <span className="font-medium text-slate-700">Relative excursion change</span>
                  <span className={`text-base font-bold ${(comparisonResult.rom_difference ?? 0) > 0 ? 'text-teal-700' : 'text-slate-900'}`}>
                    {measurement(comparisonResult.rom_difference, '°')}
                    {comparisonResult.rom_change_percentage !== null && ` (${comparisonResult.rom_change_percentage}%)`}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
