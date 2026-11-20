import React, { useEffect, useState } from 'react';
import {
  History,
  Filter,
  CheckCircle2,
  Calendar,
  Layers,
  Sparkles,
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

  // Detail Modal
  const [activeSession, setActiveSession] = useState<SessionRecord | null>(null);
  const [sessionSamples, setSessionSamples] = useState<any[]>([]);

  // Comparison State
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [sessionAId, setSessionAId] = useState<number | ''>('');
  const [sessionBId, setSessionBId] = useState<number | ''>('');
  const [comparisonResult, setComparisonResult] = useState<SessionComparison | null>(null);
  const [comparingLoading, setComparingLoading] = useState(false);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const data = await api.getSessions({
        exercise_key: filterExercise !== 'all' ? filterExercise : undefined,
        data_source: filterSource !== 'all' ? filterSource : undefined,
      });
      setSessions(data);
      if (data.length >= 2) {
        setSessionAId(data[1].id);
        setSessionBId(data[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, [filterExercise, filterSource]);

  // View Details
  const handleViewDetails = async (s: SessionRecord) => {
    setActiveSession(s);
    try {
      const samples = await api.getSessionSamples(s.id);
      const chartPoints = samples.map((sm, i) => ({
        index: i + 1,
        angle: sm.flexion_angle || sm.abduction_angle,
        velocity: sm.angular_velocity,
      }));
      setSessionSamples(chartPoints);
    } catch {
      setSessionSamples([]);
    }
  };

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
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Title & Comparison Trigger */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Rehabilitation Sessions</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Historical records, time-series kinematic samples, and session comparisons
          </p>
        </div>
        <button
          onClick={() => {
            setCompareModalOpen(true);
            if (sessionAId && sessionBId) handleRunComparison();
          }}
          disabled={sessions.length < 2}
          className="inline-flex items-center space-x-2 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white px-4 py-2.5 rounded-lg font-medium text-xs shadow-xs transition-colors"
        >
          <Columns className="w-4 h-4" />
          <span>Compare Two Sessions</span>
        </button>
      </div>

      {/* Filters Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2 text-xs text-slate-500">
            <Filter className="w-3.5 h-3.5" />
            <span className="font-semibold text-slate-700">Filters:</span>
          </div>

          <select
            value={filterExercise}
            onChange={(e) => setFilterExercise(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 font-medium text-slate-800"
          >
            <option value="all">All Exercises</option>
            <option value="flexion">Shoulder Flexion</option>
            <option value="abduction">Shoulder Abduction</option>
            <option value="external_rotation">External Rotation</option>
            <option value="internal_rotation">Internal Rotation</option>
          </select>

          <select
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 font-medium text-slate-800"
          >
            <option value="all">All Data Sources</option>
            <option value="demo">Demo Data Only</option>
            <option value="live">Live Hardware Only</option>
          </select>
        </div>

        <div className="text-xs text-slate-500">
          Showing <strong>{sessions.length}</strong> recorded sessions
        </div>
      </div>

      {/* Sessions Table */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="pb-3">Session ID</th>
              <th className="pb-3">Date & Time</th>
              <th className="pb-3">Exercise</th>
              <th className="pb-3 text-center">Side</th>
              <th className="pb-3 text-center">Reps</th>
              <th className="pb-3 text-right">ROM</th>
              <th className="pb-3 text-right">Min - Max</th>
              <th className="pb-3 text-right">Duration</th>
              <th className="pb-3 text-right">Smoothness</th>
              <th className="pb-3 text-center">Source</th>
              <th className="pb-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sessions.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-8 text-center text-slate-400">
                  No sessions match the selected filters.
                </td>
              </tr>
            ) : (
              sessions.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3 font-mono font-bold text-slate-700">#{s.id}</td>
                  <td className="py-3 font-medium text-slate-800">
                    {new Date(s.start_time).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                  </td>
                  <td className="py-3 font-bold text-slate-900 capitalize">
                    {s.exercise_key.replace('_', ' ')}
                  </td>
                  <td className="py-3 text-center capitalize text-slate-600">{s.affected_side}</td>
                  <td className="py-3 text-center font-bold text-teal-700">{s.repetitions}</td>
                  <td className="py-3 text-right font-bold text-slate-900">{s.rom}°</td>
                  <td className="py-3 text-right text-slate-500">
                    {s.min_angle}° - {s.max_angle}°
                  </td>
                  <td className="py-3 text-right text-slate-600">{s.duration_seconds}s</td>
                  <td className="py-3 text-right font-semibold text-slate-800">
                    {s.smoothness_score ?? '—'}/100
                  </td>
                  <td className="py-3 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        s.data_source === 'demo'
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : 'bg-green-50 text-green-700 border border-green-200'
                      }`}
                    >
                      {s.data_source}
                    </span>
                  </td>
                  <td className="py-3 text-right">
                    <button
                      onClick={() => handleViewDetails(s)}
                      className="inline-flex items-center space-x-1 text-teal-700 hover:text-teal-900 font-semibold"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Details</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Session Detail Drawer / Modal */}
      {activeSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-6 space-y-4 border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-bold text-teal-700 uppercase">
                  Session Detail #{activeSession.id}
                </span>
                <h3 className="font-bold text-slate-900 text-lg capitalize">
                  {activeSession.exercise_key.replace('_', ' ')} ({activeSession.affected_side} side)
                </h3>
              </div>
              <button onClick={() => setActiveSession(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                <span className="text-slate-400">Measured ROM</span>
                <div className="text-lg font-bold text-teal-700 mt-0.5">{activeSession.rom}°</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                <span className="text-slate-400">Repetitions</span>
                <div className="text-lg font-bold text-slate-900 mt-0.5">{activeSession.repetitions}</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                <span className="text-slate-400">Duration</span>
                <div className="text-lg font-bold text-slate-900 mt-0.5">{activeSession.duration_seconds}s</div>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                <span className="text-slate-400">Data Source</span>
                <div className="text-sm font-bold text-slate-800 uppercase mt-1">{activeSession.data_source}</div>
              </div>
            </div>

            {/* Time-series Kinematic Trajectory */}
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
              <h4 className="text-xs font-bold text-slate-900 mb-2">Saved Kinematic Angle Samples</h4>
              {sessionSamples.length > 0 ? (
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
                  No detailed time-series downsamples stored for this session.
                </div>
              )}
            </div>

            {/* Consistency & Notes */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between p-2 rounded bg-slate-50">
                <span className="text-slate-500">Average Rep Duration:</span>
                <span className="font-semibold text-slate-900">{activeSession.avg_rep_duration ?? '—'}s</span>
              </div>
              <div className="flex justify-between p-2 rounded bg-slate-50">
                <span className="text-slate-500">Smoothness Index:</span>
                <span className="font-semibold text-slate-900">{activeSession.smoothness_score ?? '—'}/100</span>
              </div>
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
        </div>
      )}

      {/* Comparison Modal */}
      {compareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-6 space-y-4 border border-slate-200">
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
                      #{s.id} — {s.exercise_key} ({s.rom}°) [{s.data_source}]
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
                      #{s.id} — {s.exercise_key} ({s.rom}°) [{s.data_source}]
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
                    <div className="text-xl font-bold text-slate-800 mt-2">{comparisonResult.session_a.rom}° ROM</div>
                    <div className="text-slate-500 mt-1">{comparisonResult.session_a.repetitions} reps</div>
                  </div>

                  <div className="bg-white p-3 rounded-lg border border-slate-200">
                    <div className="text-[10px] text-slate-400 font-bold uppercase">Session #{comparisonResult.session_b.id}</div>
                    <div className="font-bold text-slate-900 mt-1 capitalize">{comparisonResult.session_b.exercise_key}</div>
                    <div className="text-xl font-bold text-teal-700 mt-2">{comparisonResult.session_b.rom}° ROM</div>
                    <div className="text-slate-500 mt-1">{comparisonResult.session_b.repetitions} reps</div>
                  </div>
                </div>

                <div className="p-3 bg-teal-50 border border-teal-100 rounded-lg flex items-center justify-between">
                  <span className="font-medium text-slate-700">Measured ROM Change:</span>
                  <span className={`text-base font-bold ${comparisonResult.rom_difference > 0 ? 'text-teal-700' : 'text-slate-900'}`}>
                    {comparisonResult.rom_difference > 0 ? `+${comparisonResult.rom_difference}` : comparisonResult.rom_difference}° 
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
