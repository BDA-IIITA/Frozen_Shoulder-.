import React, { useEffect, useState } from 'react';
import {
  Compass,
  Trophy,
  Repeat,
  Calendar,
  Sparkles,
  TrendingUp,
  Cpu,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar
} from 'recharts';
import { MetricCard } from '../components/common/MetricCard';
import { DashboardSummary, ROMProgressItem, WeeklyActivityItem, NavItemKey } from '../types';
import { api } from '../services/api';

interface OverviewPageProps {
  onNavigate: (tab: NavItemKey) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [romHistory, setRomHistory] = useState<ROMProgressItem[]>([]);
  const [weeklyActivity, setWeeklyActivity] = useState<WeeklyActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [sumData, romData, weekData] = await Promise.all([
        api.getDashboardSummary(1),
        api.getROMAnalytics(1),
        api.getWeeklyActivity(1),
      ]);
      setSummary(sumData);
      setRomHistory(romData);
      setWeeklyActivity(weekData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center space-y-3">
          <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-slate-500 font-medium">Loading clinical dashboard...</span>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl flex items-center space-x-3">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <div className="font-semibold text-sm">Failed to connect to backend server</div>
            <div className="text-xs text-red-600 mt-0.5">{error || 'Make sure the FastAPI backend is running.'}</div>
          </div>
          <button
            onClick={loadData}
            className="ml-auto bg-red-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-red-700 font-medium"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const diag = summary.device_status;

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Quick Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Rehabilitation Overview</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Objective IMU kinematics tracking for adhesive capsulitis recovery
          </p>
        </div>
        <button
          onClick={() => onNavigate('monitoring')}
          className="inline-flex items-center justify-center space-x-2 bg-teal-600 hover:bg-teal-700 text-white px-4 py-2.5 rounded-lg font-medium text-sm shadow-xs transition-colors"
        >
          <span>Start Monitoring Session</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Primary Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Latest Shoulder ROM"
          value={summary.latest_rom}
          unit="°"
          change={summary.rom_change_vs_prior}
          changeLabel="vs. prior session"
          icon={Compass}
          variant="teal"
        />
        <MetricCard
          title="Best ROM Achieved"
          value={summary.best_rom}
          unit="°"
          subtitle="All sessions peak"
          icon={Trophy}
          variant="amber"
        />
        <MetricCard
          title="Total Repetitions"
          value={summary.total_repetitions}
          subtitle={`Across ${summary.total_sessions} completed sessions`}
          icon={Repeat}
          variant="blue"
        />
        <MetricCard
          title="Movement Consistency"
          value={summary.avg_movement_quality ? `${summary.avg_movement_quality}/100` : '—'}
          subtitle="Derived smoothness index"
          icon={Sparkles}
          variant="slate"
        />
      </div>

      {/* Recovery Summary Callout Banner (Data-Grounded) */}
      <div className="bg-gradient-to-r from-teal-50 to-blue-50 border border-teal-100 rounded-xl p-5 shadow-xs">
        <div className="flex items-start space-x-3">
          <div className="w-8 h-8 rounded-lg bg-teal-600/10 text-teal-700 flex items-center justify-center flex-shrink-0 mt-0.5">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Recovery Trend Summary</h3>
            <p className="text-xs sm:text-sm text-slate-700 mt-1 leading-relaxed">
              {summary.recovery_summary_text}
            </p>
            <div className="mt-2 flex items-center space-x-2 text-[11px] text-slate-500">
              <ShieldCheck className="w-3.5 h-3.5 text-teal-600" />
              <span>Strictly factual statements derived from stored sensor measurements. Not a medical diagnosis.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ROM Progress Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Range of Motion (ROM) Progress</h3>
              <p className="text-xs text-slate-500">Max elevation angle recorded per session</p>
            </div>
            <button
              onClick={() => onNavigate('analytics')}
              className="text-xs text-teal-700 hover:text-teal-800 font-medium"
            >
              View Detailed Analytics →
            </button>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={romHistory} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} unit="°" domain={[0, 'auto']} tickLine={false} />
                <Tooltip
                  formatter={(value: any) => [`${value}°`, 'ROM']}
                  labelFormatter={(label) => `Session Date: ${label}`}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
                <Line
                  type="monotone"
                  dataKey="rom"
                  stroke="#0d9488"
                  strokeWidth={2.5}
                  dot={{ fill: '#0d9488', r: 4 }}
                  activeDot={{ r: 6, fill: '#0f766e' }}
                  name="ROM"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Weekly Activity Chart */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-900">7-Day Activity</h3>
              <span className="text-[11px] text-slate-400 font-mono">Sessions / Day</span>
            </div>
            <p className="text-xs text-slate-500 mb-4">Rehabilitation session frequency</p>
            <div className="h-52 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyActivity} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="day" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} tickLine={false} />
                  <Tooltip
                    formatter={(val: any) => [val, 'Sessions']}
                    contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                  />
                  <Bar dataKey="sessions_count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Total weekly reps</span>
            <span className="font-semibold text-slate-800">
              {weeklyActivity.reduce((acc, curr) => acc + curr.total_repetitions, 0)} reps
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Section: Recent Sessions Table & Device Diagnostics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Sessions Table */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Recent Rehabilitation Sessions</h3>
              <p className="text-xs text-slate-500">History of verified exercise recordings</p>
            </div>
            <button
              onClick={() => onNavigate('sessions')}
              className="text-xs text-teal-700 hover:text-teal-800 font-medium"
            >
              All Sessions →
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-2.5">Date</th>
                  <th className="pb-2.5">Exercise</th>
                  <th className="pb-2.5 text-center">Reps</th>
                  <th className="pb-2.5 text-right">ROM</th>
                  <th className="pb-2.5 text-right">Duration</th>
                  <th className="pb-2.5 text-right">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {summary.recent_sessions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-400">
                      No sessions recorded yet. Start your first monitoring session!
                    </td>
                  </tr>
                ) : (
                  summary.recent_sessions.map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-2.5 font-medium text-slate-800">{s.date}</td>
                      <td className="py-2.5 font-medium text-slate-900">{s.exercise_name}</td>
                      <td className="py-2.5 text-center font-semibold text-teal-700">{s.repetitions}</td>
                      <td className="py-2.5 text-right font-bold text-slate-900">{s.rom}°</td>
                      <td className="py-2.5 text-right text-slate-500">{s.duration_seconds}s</td>
                      <td className="py-2.5 text-right">
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
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Device & Hardware Telemetry Status */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-900">Device Telemetry</h3>
              <Cpu className="w-4 h-4 text-teal-600" />
            </div>
            <p className="text-xs text-slate-500 mb-4">Wearable hardware & sensor status</p>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500">Source Mode</span>
                <span className="font-bold text-slate-900 uppercase">{diag.data_source_mode}</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500">Connection</span>
                <span className={`font-semibold ${diag.is_active ? 'text-teal-600' : 'text-slate-500'}`}>
                  {diag.is_active ? 'Connected / Active' : 'Idle / Standby'}
                </span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500">Packets Ingested</span>
                <span className="font-mono font-bold text-slate-900">{diag.packets_received}</span>
              </div>
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-500">Sensors Detected</span>
                <span className="font-medium text-slate-700">
                  {diag.sensors_detected.length > 0 ? diag.sensors_detected.join(', ') : 'None'}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 mt-4">
            <button
              onClick={() => onNavigate('settings')}
              className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 py-2 rounded-lg text-xs font-medium transition-colors"
            >
              Device Calibration & Settings →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
