import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  Activity,
  BarChart2,
  Calendar,
  Layers,
  Sparkles,
  ShieldCheck,
  Filter,
  CheckCircle2
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  BarChart,
  Bar
} from 'recharts';
import { ROMProgressItem, Exercise } from '../types';
import { api } from '../services/api';

export const ProgressAnalyticsPage: React.FC = () => {
  const [exerciseKey, setExerciseKey] = useState<string>('flexion');
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [romData, setRomData] = useState<ROMProgressItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getExercises().then(setExercises).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    api.getROMAnalytics(1, exerciseKey)
      .then(setRomData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [exerciseKey]);

  // Derived calculations
  const baselineRom = romData.length > 0 ? romData[0].rom : 0;
  const latestRom = romData.length > 0 ? romData[romData.length - 1].rom : 0;
  const netChange = Number((latestRom - baselineRom).toFixed(1));
  const pctChange = baselineRom > 0 ? Number(((netChange / baselineRom) * 100).toFixed(1)) : null;

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Title & Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Progress Analytics</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Longitudinal kinematic analysis and range-of-motion recovery metrics
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <select
            value={exerciseKey}
            onChange={(e) => setExerciseKey(e.target.value)}
            className="text-xs bg-white border border-slate-300 rounded-lg px-3 py-2 font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            {exercises.map((ex) => (
              <option key={ex.exercise_key} value={ex.exercise_key}>
                {ex.display_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Progress Metric Summary Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="text-xs text-slate-500 font-semibold uppercase">Baseline Session ROM</div>
          <div className="text-2xl font-bold text-slate-800 mt-1">{baselineRom}°</div>
          <div className="text-xs text-slate-400 mt-1">First recorded session</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="text-xs text-slate-500 font-semibold uppercase">Latest Recorded ROM</div>
          <div className="text-2xl font-bold text-teal-700 mt-1">{latestRom}°</div>
          <div className="text-xs text-slate-400 mt-1">Current milestone</div>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="text-xs text-slate-500 font-semibold uppercase">Measured Net Change</div>
          <div className={`text-2xl font-bold mt-1 ${netChange >= 0 ? 'text-teal-600' : 'text-amber-600'}`}>
            {netChange >= 0 ? `+${netChange}` : netChange}°
            {pctChange !== null && <span className="text-sm font-semibold ml-1.5">({pctChange}%)</span>}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Across {romData.length} recorded sessions</div>
        </div>
      </div>

      {/* Primary Chart: ROM vs Session Number */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">ROM Progression by Session</h3>
            <p className="text-xs text-slate-500">Maximum elevation angle per consecutive session</p>
          </div>
          <span className="text-xs font-mono text-teal-700 font-semibold bg-teal-50 px-2 py-1 rounded">
            {exerciseKey.replace('_', ' ').toUpperCase()}
          </span>
        </div>

        {romData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-xs text-slate-400">
            No session recordings found for this exercise.
          </div>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={romData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="session_number"
                  stroke="#94a3b8"
                  fontSize={11}
                  tickLine={false}
                  label={{ value: 'Session Number', position: 'insideBottom', offset: -5, fontSize: 10, fill: '#94a3b8' }}
                />
                <YAxis stroke="#94a3b8" fontSize={11} unit="°" domain={[0, 'auto']} tickLine={false} />
                <Tooltip
                  formatter={(val: any) => [`${val}°`, 'ROM']}
                  labelFormatter={(num) => `Session #${num}`}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
                <Line
                  type="monotone"
                  dataKey="rom"
                  stroke="#0d9488"
                  strokeWidth={3}
                  dot={{ fill: '#0d9488', r: 5 }}
                  activeDot={{ r: 7, fill: '#0f766e' }}
                  name="Range of Motion"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Secondary Graphs: Repetitions & Consistency Score */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Repetitions per Session */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Repetition Volume</h3>
          <p className="text-xs text-slate-500 mb-4">Completed repetitions verified by FSM</p>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={romData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="session_number" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} tickLine={false} />
                <Tooltip
                  formatter={(val: any) => [val, 'Repetitions']}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
                <Bar dataKey="repetitions" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Movement Quality / Smoothness */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Kinematic Smoothness Index</h3>
          <p className="text-xs text-slate-500 mb-4">Consistency of velocity and duration (0-100)</p>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={romData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="session_number" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} tickLine={false} />
                <Tooltip
                  formatter={(val: any) => [`${val}/100`, 'Smoothness Score']}
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
                <Line
                  type="monotone"
                  dataKey="smoothness_score"
                  stroke="#8b5cf6"
                  strokeWidth={2.5}
                  dot={{ fill: '#8b5cf6', r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Clinical Disclaimer */}
      <div className="p-4 rounded-xl bg-slate-100 border border-slate-200/80 text-xs text-slate-600 flex items-start space-x-2.5">
        <ShieldCheck className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" />
        <p>
          ROM changes represent <strong>biomechanical variations in measured kinematic angles</strong>. 
          They do not directly equate to percentages of physiological recovery or replace comprehensive clinical evaluation by an orthopedic specialist.
        </p>
      </div>
    </div>
  );
};
