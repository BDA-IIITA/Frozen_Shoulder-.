import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Pause,
  RotateCcw,
  CheckCircle,
  AlertTriangle,
  Cpu,
  Activity,
  Flame,
  Clock,
  Compass,
  Repeat,
  ShieldAlert,
  Save,
  Trash2,
  X
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
import { ArmVisualization } from '../components/monitoring/ArmVisualization';
import {
  LiveSensorSample,
  DataSourceMode,
  AffectedSide,
  Exercise,
  SessionRecord
} from '../types';
import { api } from '../services/api';
import { wsClient } from '../services/websocket';

export const LiveMonitoringPage: React.FC = () => {
  // Session State
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<string>('flexion');
  const [affectedSide, setAffectedSide] = useState<AffectedSide>('right');
  const [dataSource, setDataSource] = useState<DataSourceMode>('demo');
  
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
  const [sessionDuration, setSessionDuration] = useState(0);

  // Live Telemetry Data
  const [latestSample, setLatestSample] = useState<LiveSensorSample | null>(null);
  const [chartData, setChartData] = useState<Array<{ time: string; angle: number; velocity: number }>>([]);
  const [sessionMaxAngle, setSessionMaxAngle] = useState(0);
  const [sessionMinAngle, setSessionMinAngle] = useState(0);
  const [sessionRom, setSessionRom] = useState(0);
  const [repCount, setRepCount] = useState(0);
  const [repState, setRepState] = useState<string>('REST');

  // Finish Session Modal
  const [showFinishModal, setShowFinishModal] = useState(false);
  const [sessionNotes, setSessionNotes] = useState('');
  const [finishedSummary, setFinishedSummary] = useState<any | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Calibration alert
  const [calibrationMsg, setCalibrationMsg] = useState<string | null>(null);

  // Hardware connection tracking
  const [lastPacketTime, setLastPacketTime] = useState<number | null>(null);
  const [isHardwareOnline, setIsHardwareOnline] = useState(false);

  const durationTimerRef = useRef<any>(null);

  // Load exercises on mount
  useEffect(() => {
    api.getExercises().then((list) => {
      setExercises(list);
      if (list.length > 0) setSelectedExercise(list[0].exercise_key);
    }).catch(console.error);

    // Connect WebSocket
    wsClient.connect();

    const unsubscribe = wsClient.onSample((sample) => {
      setLatestSample(sample);
      setLastPacketTime(Date.now());
      setIsHardwareOnline(true);
      setSessionMaxAngle(sample.session_max_angle);
      setSessionMinAngle(sample.session_min_angle);
      setSessionRom(sample.session_rom);
      setRepCount(sample.repetitions);
      setRepState(sample.state);

      // Append to rolling chart buffer (keep last 60 points)
      const nowStr = new Date(sample.timestamp * 1000).toLocaleTimeString([], {
        minute: '2-digit',
        second: '2-digit',
      });

      setChartData((prev) => {
        const next = [...prev, {
          time: nowStr,
          angle: sample.primary_angle,
          velocity: sample.angular_velocity,
        }];
        return next.length > 50 ? next.slice(next.length - 50) : next;
      });
    });

    return () => {
      unsubscribe();
      if (durationTimerRef.current) clearInterval(durationTimerRef.current);
    };
  }, []);

  // Monitor hardware freshness in live mode (offline if no packets within 3s)
  useEffect(() => {
    const timer = setInterval(() => {
      if (lastPacketTime && (Date.now() - lastPacketTime < 3000)) {
        setIsHardwareOnline(true);
      } else {
        setIsHardwareOnline(false);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [lastPacketTime]);

  // Timer counter when active & not paused
  useEffect(() => {
    if (isSessionActive && !isPaused) {
      durationTimerRef.current = setInterval(() => {
        setSessionDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (durationTimerRef.current) clearInterval(durationTimerRef.current);
    }
    return () => {
      if (durationTimerRef.current) clearInterval(durationTimerRef.current);
    };
  }, [isSessionActive, isPaused]);

  // Start Session handler
  const handleStartSession = async () => {
    try {
      setChartData([]);
      setSessionDuration(0);
      setSessionMaxAngle(0);
      setSessionMinAngle(0);
      setSessionRom(0);
      setRepCount(0);

      const resp = await api.startSession({
        patient_id: 1,
        exercise_key: selectedExercise,
        affected_side: affectedSide,
        data_source: dataSource,
      });

      setCurrentSessionId(resp.session_id);
      setIsSessionActive(true);
      setIsPaused(false);
    } catch (err: any) {
      alert(`Could not start session: ${err.message}`);
    }
  };

  // Pause / Resume
  const handleTogglePause = () => {
    setIsPaused(!isPaused);
  };

  // Finish session (open confirmation dialog)
  const handleInitiateFinish = () => {
    setShowFinishModal(true);
  };

  // Save session to database
  const handleConfirmFinish = async () => {
    if (!currentSessionId) return;
    try {
      setIsSaving(true);
      const res = await api.finishSession(currentSessionId, sessionNotes, true);
      setFinishedSummary(res);
      setIsSessionActive(false);
      setIsPaused(false);
      setShowFinishModal(false);
    } catch (err: any) {
      alert(`Error saving session: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  // Discard session with confirmation
  const handleDiscardSession = async () => {
    if (!currentSessionId) return;
    if (window.confirm('Discard this monitoring session without saving?')) {
      try {
        await api.discardSession(currentSessionId);
        setIsSessionActive(false);
        setIsPaused(false);
        setCurrentSessionId(null);
        setChartData([]);
      } catch (err: any) {
        alert(`Error discarding session: ${err.message}`);
      }
    }
  };

  // Calibrate neutral reference
  const handleCalibrate = async () => {
    try {
      const res = await api.calibrateNeutral('esp32-shoulder-01');
      setCalibrationMsg(res.message);
      setTimeout(() => setCalibrationMsg(null), 4000);
    } catch (err: any) {
      alert(`Calibration failed: ${err.message}`);
    }
  };

  // Switch mode
  const handleModeChange = async (mode: DataSourceMode) => {
    if (isSessionActive) {
      alert('Finish or discard the active session before switching data sources.');
      return;
    }
    setDataSource(mode);
    try {
      await api.connectDevice('esp32-shoulder-01', mode);
    } catch (err) {
      console.error(err);
    }
  };

  const formatTimer = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const currentExerciseObj = exercises.find((e) => e.exercise_key === selectedExercise);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Banner / Device Connection Panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              dataSource === 'demo' ? 'bg-teal-50 text-teal-700' : 'bg-blue-50 text-blue-700'
            }`}
          >
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="font-bold text-slate-900 text-base">Real-Time Movement Monitoring</h2>
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                  dataSource === 'demo'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-green-100 text-green-800'
                }`}
              >
                {dataSource === 'demo' ? 'SIMULATED DEMO' : 'LIVE ESP32 HARDWARE'}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Dual BNO086 relative quaternion orientation pipeline
            </p>
          </div>
        </div>

        {/* Source Mode Selector & Calibration */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="bg-slate-100 p-1 rounded-lg flex items-center space-x-1 text-xs font-medium">
            <button
              onClick={() => handleModeChange('demo')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                dataSource === 'demo'
                  ? 'bg-white text-slate-900 font-bold shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Demo Generator
            </button>
            <button
              onClick={() => handleModeChange('live')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                dataSource === 'live'
                  ? 'bg-white text-slate-900 font-bold shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              ESP32 Live Mode
            </button>
          </div>

          <button
            onClick={handleCalibrate}
            className="border border-slate-300 hover:bg-slate-50 text-slate-700 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            title="Zero the relative sensor reference when standing naturally"
          >
            Calibrate Neutral
          </button>
        </div>
      </div>

      {/* Calibration feedback toast */}
      {calibrationMsg && (
        <div className="bg-teal-50 border border-teal-200 text-teal-800 px-4 py-2.5 rounded-lg text-xs flex items-center justify-between animate-fadeIn">
          <span>✓ {calibrationMsg}</span>
          <button onClick={() => setCalibrationMsg(null)} className="text-teal-600 hover:text-teal-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Live ESP32 Hardware Status Banner */}
      {dataSource === 'live' && (
        <div
          className={`rounded-xl border p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-colors ${
            isHardwareOnline
              ? 'bg-emerald-50/90 border-emerald-200 text-emerald-950'
              : 'bg-amber-50/90 border-amber-200 text-amber-950'
          }`}
        >
          <div className="flex items-center space-x-3">
            <span className="relative flex h-3.5 w-3.5">
              {isHardwareOnline && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              )}
              <span
                className={`relative inline-flex rounded-full h-3.5 w-3.5 ${
                  isHardwareOnline ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
              />
            </span>
            <div>
              <div className="text-xs font-bold flex items-center gap-1.5">
                {isHardwareOnline ? (
                  <>
                    <span>ESP32 Hardware: CONNECTED & STREAMING</span>
                    <span className="text-[10px] bg-emerald-200 text-emerald-900 font-mono px-1.5 py-0.5 rounded font-bold">
                      20 Hz Telemetry
                    </span>
                  </>
                ) : (
                  <>
                    <span>ESP32 Hardware: WAITING FOR WI-FI PACKETS</span>
                    <span className="text-[10px] bg-amber-200 text-amber-900 font-mono px-1.5 py-0.5 rounded font-bold">
                      Standby
                    </span>
                  </>
                )}
              </div>
              <p className="text-[11px] opacity-80 mt-0.5">
                {isHardwareOnline
                  ? `Active data packets arriving via Wi-Fi (Device: ${latestSample?.device_id || 'esp32-shoulder-01'})`
                  : `Ensure ESP32 is powered on and connected to the same Wi-Fi. Ingest endpoint: /api/sensor/ingest`}
              </p>
            </div>
          </div>

          <div className="text-right flex sm:flex-col items-center sm:items-end justify-between sm:justify-center">
            <span className="text-[10px] font-bold uppercase tracking-wider opacity-60">Status</span>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                isHardwareOnline ? 'bg-emerald-200/70 text-emerald-900' : 'bg-amber-200/70 text-amber-900'
              }`}
            >
              {isHardwareOnline ? 'STREAMING ACTIVE' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      )}

      {/* Control Strip & Active Session Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        {/* Left: Exercise and Side Pickers */}
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Select Exercise
            </label>
            <select
              value={selectedExercise}
              onChange={(e) => setSelectedExercise(e.target.value)}
              disabled={isSessionActive}
              className="text-xs bg-slate-50 border border-slate-300 rounded-lg px-3 py-1.5 font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-teal-500 disabled:opacity-60"
            >
              {exercises.map((ex) => (
                <option key={ex.exercise_key} value={ex.exercise_key}>
                  {ex.display_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Affected Shoulder
            </label>
            <div className="flex rounded-lg border border-slate-300 overflow-hidden text-xs">
              <button
                type="button"
                disabled={isSessionActive}
                onClick={() => setAffectedSide('left')}
                className={`px-3 py-1.5 font-medium ${
                  affectedSide === 'left' ? 'bg-teal-600 text-white font-bold' : 'bg-white text-slate-700'
                }`}
              >
                Left
              </button>
              <button
                type="button"
                disabled={isSessionActive}
                onClick={() => setAffectedSide('right')}
                className={`px-3 py-1.5 font-medium border-l border-slate-300 ${
                  affectedSide === 'right' ? 'bg-teal-600 text-white font-bold' : 'bg-white text-slate-700'
                }`}
              >
                Right
              </button>
            </div>
          </div>
        </div>

        {/* Right: Controls & Timer */}
        <div className="flex items-center space-x-3">
          {/* Duration Clock */}
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg text-xs font-mono font-bold text-slate-800">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>{formatTimer(sessionDuration)}</span>
          </div>

          {/* Action Buttons */}
          {!isSessionActive ? (
            <button
              onClick={handleStartSession}
              className="inline-flex items-center space-x-1.5 bg-teal-600 hover:bg-teal-700 text-white px-4 py-2 rounded-lg font-semibold text-xs shadow-xs transition-colors"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Start Session</span>
            </button>
          ) : (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleTogglePause}
                className="inline-flex items-center space-x-1 bg-slate-100 hover:bg-slate-200 text-slate-800 px-3 py-2 rounded-lg font-medium text-xs transition-colors"
              >
                {isPaused ? <Play className="w-3.5 h-3.5 fill-current" /> : <Pause className="w-3.5 h-3.5 fill-current" />}
                <span>{isPaused ? 'Resume' : 'Pause'}</span>
              </button>

              <button
                onClick={handleInitiateFinish}
                className="inline-flex items-center space-x-1 bg-teal-600 hover:bg-teal-700 text-white px-3.5 py-2 rounded-lg font-semibold text-xs shadow-xs transition-colors"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                <span>Finish & Save</span>
              </button>

              <button
                onClick={handleDiscardSession}
                className="inline-flex items-center space-x-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 px-2.5 py-2 rounded-lg font-medium text-xs transition-colors"
                title="Discard session"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Workspace Grid: Kinematics Visualizer & Live Measurements */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Upper Body Kinematic Model (5 cols) */}
        <div className="lg:col-span-5 h-[440px]">
          <ArmVisualization
            angle={latestSample?.primary_angle ?? 0}
            maxAngle={sessionMaxAngle}
            exerciseKey={selectedExercise}
            affectedSide={affectedSide}
            dataSource={dataSource}
          />
        </div>

        {/* Right: Live Telemetry Cards & Rolling Real-Time Chart (7 cols) */}
        <div className="lg:col-span-7 flex flex-col justify-between space-y-4">
          {/* Real-time Kinematic Metric Chips */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Elevation Angle */}
            <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Current Angle</div>
              <div className="text-2xl font-bold text-teal-700 mt-1">
                {latestSample ? `${latestSample.primary_angle.toFixed(1)}°` : '0.0°'}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                Vel: {latestSample?.angular_velocity ?? 0} °/s
              </div>
            </div>

            {/* Range of Motion */}
            <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Session ROM</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {sessionRom.toFixed(1)}°
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                Max: {sessionMaxAngle.toFixed(1)}°
              </div>
            </div>

            {/* Repetitions */}
            <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Completed Reps</div>
              <div className="text-2xl font-bold text-blue-700 mt-1">{repCount}</div>
              <div className="text-[10px] text-slate-500 mt-1">FSM verified</div>
            </div>

            {/* FSM Phase Indicator */}
            <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
              <div className="text-[10px] text-slate-400 font-semibold uppercase">Rep State</div>
              <div className="text-sm font-bold text-slate-800 mt-2 flex items-center space-x-1.5">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    repState === 'ASCENT'
                      ? 'bg-amber-500 animate-pulse'
                      : repState === 'DESCENT'
                      ? 'bg-blue-500 animate-pulse'
                      : 'bg-slate-300'
                  }`}
                />
                <span>{repState}</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1.5">Direction Hysteresis</div>
            </div>
          </div>

          {/* Real-time Angle & Angular Velocity Chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex-1 flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h4 className="text-xs font-bold text-slate-900">Shoulder Angle & Velocity vs. Time</h4>
                <p className="text-[11px] text-slate-500">Rolling window (last 50 packets)</p>
              </div>
              <div className="flex items-center space-x-3 text-[11px]">
                <div className="flex items-center space-x-1 text-teal-700 font-semibold">
                  <span className="w-3 h-0.5 bg-teal-600 rounded"></span>
                  <span>Angle (°)</span>
                </div>
                <div className="flex items-center space-x-1 text-amber-600 font-semibold">
                  <span className="w-3 h-0.5 bg-amber-500 rounded"></span>
                  <span>Velocity (°/s)</span>
                </div>
              </div>
            </div>

            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="#f1f5f9" />
                  <XAxis dataKey="time" stroke="#cbd5e1" fontSize={9} tickLine={false} />
                  <YAxis stroke="#cbd5e1" fontSize={9} tickLine={false} domain={[0, 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '11px' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="angle"
                    stroke="#0d9488"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="velocity"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="3 3"
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Exercise Guidance Tip */}
            {currentExerciseObj && (
              <div className="mt-2 p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-[11px] text-slate-600 flex items-start space-x-2">
                <span className="font-semibold text-slate-700 flex-shrink-0">Instructions:</span>
                <span>{currentExerciseObj.instructions}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Finished Session Post-Summary Banner (if just completed) */}
      {finishedSummary && (
        <div className="bg-white border-2 border-teal-500 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-teal-800">
              <CheckCircle className="w-5 h-5 text-teal-600" />
              <h3 className="font-bold text-base">Session #{finishedSummary.session.id} Recorded Successfully!</h3>
            </div>
            <button
              onClick={() => setFinishedSummary(null)}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Dismiss
            </button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-slate-50 p-2.5 rounded-lg">
              <span className="text-slate-500">Exercise</span>
              <div className="font-semibold text-slate-900 mt-0.5">{finishedSummary.exercise_name}</div>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg">
              <span className="text-slate-500">Repetitions</span>
              <div className="font-semibold text-teal-700 mt-0.5">{finishedSummary.session.repetitions} completed</div>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg">
              <span className="text-slate-500">Measured ROM</span>
              <div className="font-bold text-slate-900 mt-0.5">{finishedSummary.session.rom}°</div>
            </div>
            <div className="bg-slate-50 p-2.5 rounded-lg">
              <span className="text-slate-500">Consistency Index</span>
              <div className="font-semibold text-slate-800 mt-0.5">
                {finishedSummary.session.smoothness_score ?? '—'}/100
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Finish Session Modal Dialog */}
      {showFinishModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4 border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Finish & Save Session</h3>
              <button onClick={() => setShowFinishModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-slate-50 p-3 rounded-lg space-y-1.5 border border-slate-100">
                <div className="flex justify-between">
                  <span className="text-slate-500">Exercise</span>
                  <span className="font-semibold text-slate-900 capitalize">{selectedExercise}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Data Source</span>
                  <span className="font-bold text-teal-700 uppercase">{dataSource}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Reps Completed</span>
                  <span className="font-bold text-slate-900">{repCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Measured ROM</span>
                  <span className="font-bold text-slate-900">{sessionRom.toFixed(1)}°</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Duration</span>
                  <span className="font-mono text-slate-800">{formatTimer(sessionDuration)}</span>
                </div>
              </div>

              <div>
                <label className="block text-slate-600 font-medium mb-1">
                  Session Notes (Optional)
                </label>
                <textarea
                  value={sessionNotes}
                  onChange={(e) => setSessionNotes(e.target.value)}
                  placeholder="e.g. Mild resistance felt at 70 degrees, rested 10s between reps."
                  rows={3}
                  className="w-full text-xs p-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-teal-500"
                />
              </div>

              <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-800">
                Session data will be permanently saved with the <strong>{dataSource.toUpperCase()}</strong> tag in the local SQLite database.
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowFinishModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmFinish}
                disabled={isSaving}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-lg shadow-xs transition-colors flex items-center space-x-1.5"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{isSaving ? 'Saving...' : 'Confirm & Save'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
