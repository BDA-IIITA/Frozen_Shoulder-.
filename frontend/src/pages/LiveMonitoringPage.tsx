import { OrientationDiagnostics } from '../components/monitoring/OrientationDiagnostics';
import { ArmVisualization } from '../components/monitoring/ArmVisualization';
import { useEffect, useRef, useState } from 'react';
import { CircleCheck, Clock3, Database, Play, Radio, RotateCcw, Pause, Save, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import type { DataSourceMode, Exercise, HardwareStreamStatus, MonitoringSnapshot, Participant, PlaybackSpeed, ReplayAction, ReplayRecording } from '../types';
import { measurement, MovementAnalytics, WristChart } from '../components/monitoring/MovementAnalytics';
import { formatTime, SessionTimeline } from '../components/monitoring/SessionTimeline';

const sources = [
  { id: 'replay', label: 'Dataset Replay', icon: Database },
  { id: 'live', label: 'Live ESP32', icon: Radio },
  { id: 'demo', label: 'Synthetic Demo', icon: Sparkles },
] as const;
const speeds = [1, 2, 4] as const;
const field = 'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900';
const button = 'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-50';
const primary = 'inline-flex items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50';

export function LiveMonitoringPage({ onOpenProgress }: { onOpenProgress?: (source: DataSourceMode) => void }) {
  const [source, setSource] = useState<DataSourceMode>('replay');
  const [catalog, setCatalog] = useState<ReplayRecording[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [patients, setPatients] = useState<Participant[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErrors, setLoadErrors] = useState<string[]>([]);
  const [participant, setParticipant] = useState('');
  const [recordingId, setRecordingId] = useState('');
  const [patientId, setPatientId] = useState<number>();
  const [repPeak, setRepPeak] = useState('15');
  const [exerciseKey, setExerciseKey] = useState('flexion');
  const [side, setSide] = useState<'left' | 'right'>('right');
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const [active, setActive] = useState<MonitoringSnapshot | null>(null);
  const [saved, setSaved] = useState<Awaited<ReturnType<typeof api.finishSession>> | null>(null);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notes, setNotes] = useState('');
  const [pain, setPain] = useState('');
  const [stiffness, setStiffness] = useState('');
  const [targetReps, setTargetReps] = useState('');
  const [targetAngle, setTargetAngle] = useState('');
  const revision = useRef(0);
  const catalogRevision = useRef(0);

  useEffect(() => {
    setTargetReps('');
    setTargetAngle('');
  }, [patientId, side, exerciseKey]);

  function loadCatalog() {
    const version = ++catalogRevision.current;
    setLoading(true);
    Promise.allSettled([api.getReplayRecordings(), api.getExercises(), api.getParticipants()] as const)
      .then(([recordings, availableExercises, people]) => {
        if (version !== catalogRevision.current) return;
        const errors = [];
        if (recordings.status === 'fulfilled') {
          setCatalog(recordings.value);
          const first = recordings.value.find(record => record.exercise_key === 'flexion') ?? recordings.value[0];
          setParticipant(first?.participant ?? '');
          setRecordingId(first?.id ?? '');
        } else errors.push('Replay catalog could not be loaded.');
        if (availableExercises.status === 'fulfilled') setExercises(availableExercises.value);
        else errors.push('Exercise list could not be loaded.');
        if (people.status === 'fulfilled') {
          setPatients(people.value);
          setPatientId(people.value[0]?.id);
          setSide(people.value[0]?.affected_side ?? 'right');
        } else errors.push('Participant list could not be loaded.');
        setLoadErrors(errors);
      }).finally(() => { if (version === catalogRevision.current) setLoading(false); });
  }

  useEffect(() => {
    loadCatalog();
    return () => { catalogRevision.current++; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      const version = revision.current;
      try {
        const snapshot = await api.getActiveMonitoring();
        if (!cancelled && version === revision.current) {
          setActive(snapshot);
          setConnectionError(false);
        }
      } catch { if (!cancelled) setConnectionError(true); }
      if (!cancelled) timer = setTimeout(poll, 350);
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  async function run(action: () => Promise<void>) {
    revision.current++;
    setBusy(true);
    setError('');
    try { await action(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'The operation could not be completed.'); }
    finally { revision.current++; setBusy(false); }
  }

  const mode = active?.source ?? saved?.session.data_source ?? source;
  const isReplay = mode === 'replay';
  const record = active?.analytics.recording ?? saved?.session.movement_analytics?.recording ?? catalog.find(item => item.id === recordingId);
  const metrics = active?.analytics ?? saved?.session.movement_analytics;
  const repReview = metrics?.repetition_review;
  const completed = active?.status === 'complete';
  const elapsed = active?.elapsed_s ?? saved?.session.duration_seconds ?? 0;
  const duration = isReplay ? record?.duration_s ?? elapsed : elapsed;
  const exercise = exercises.find(item => item.exercise_key === (active?.exercise_key ?? exerciseKey));
  const displayName = isReplay ? record?.exercise_name : exercise?.display_name;
  const patient = patients.find(item => item.id === (active?.patient_id ?? patientId));
  const displayParticipant = isReplay ? record?.participant.replace('spars9x_', 'SPARS9x ') : patient?.name;
  const status = active ? { playing: 'Playing', paused: 'Paused', complete: 'Complete', recording: 'Monitoring', stopped: 'Stopped' }[active.status] : saved ? 'Saved' : 'Ready';
  const currentSpeed = active?.playback_speed ?? speed;
  const canStart = !!patientId && !!(isReplay ? record : exercise) && !loading;

  function chooseParticipant(value: string) {
    setSaved(null);
    setParticipant(value);
    const items = catalog.filter(item => item.participant === value);
    setRecordingId((items.find(item => item.exercise_key === 'flexion') ?? items[0])?.id ?? '');
  }

  function start() {
    run(async () => {
      setSaved(null);
      const peak = Number(repPeak);
      if (mode === 'live' && (!Number.isFinite(peak) || peak < 5 || peak > 120)) {
        throw new Error('Choose a repetition threshold from 5° to 120°.');
      }
      const repsGoal = mode === 'live' && targetReps !== '' ? Number(targetReps) : undefined;
      const angleGoal = mode === 'live' && targetAngle !== '' ? Number(targetAngle) : undefined;
      if (repsGoal != null && (!Number.isInteger(repsGoal) || repsGoal < 1 || repsGoal > 500)) {
        throw new Error('Enter a prescribed rep target from 1 to 500.');
      }
      if (angleGoal != null && (!Number.isFinite(angleGoal) || angleGoal <= 0 || angleGoal > 180)) {
        throw new Error('Enter a prescribed movement target above 0° and up to 180°.');
      }
      const result = await api.startSession({
        patient_id: isReplay ? patients[0]?.id : patientId, data_source: mode, exercise_key: exerciseKey, affected_side: side,
        recording_id: isReplay ? record?.id : undefined, playback_speed: speed,
        rep_peak_deg: mode === 'live' ? peak : undefined,
        prescribed_repetitions: repsGoal, prescribed_angle_deg: angleGoal,
      });
      const snapshot = await api.getActiveMonitoring();
      if (snapshot?.session_id === result.session_id) setActive(snapshot);
    });
  }

  function control(action: ReplayAction, value?: PlaybackSpeed) {
    if (!active) return;
    run(async () => {
      const result = await api.controlReplay(active.session_id, action, value);
      setActive({ ...result, patient_id: active.patient_id });
    });
  }

  function save() {
    if (!active) return;
    run(async () => {
      const rating = mode === 'live' && pain !== '' ? Number(pain) : undefined;
      if (rating != null && (!Number.isInteger(rating) || rating < 0 || rating > 10)) {
        throw new Error('Enter a whole number from 0 to 10 for pain.');
      }
      const stiffnessRating = mode === 'live' && stiffness !== '' ? Number(stiffness) : undefined;
      if (stiffnessRating != null && (!Number.isInteger(stiffnessRating) || stiffnessRating < 0 || stiffnessRating > 10)) {
        throw new Error('Enter a whole number from 0 to 10 for stiffness.');
      }
      setSaved(await api.finishSession(active.session_id, notes.trim(), true, rating, stiffnessRating));
      setActive(null);
      setSaving(false);
      setNotes('');
      setPain('');
      setStiffness('');
    });
  }

  const monitoringSide = active?.affected_side === 'left' ? 'left' : active?.affected_side === 'right' ? 'right' : side;
  const [hardware, setHardware] = useState<HardwareStreamStatus | null>(null);
  const [hardwareError, setHardwareError] = useState(false);
  const [calibrating, setCalibrating] = useState(false);
  const [neutralMessage, setNeutralMessage] = useState('');
  useEffect(() => {
    if (mode !== 'live') return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api.getHardwareStream(monitoringSide);
        if (!cancelled) { setHardware(result); setHardwareError(false); }
      } catch {
        if (!cancelled) { setHardware(null); setHardwareError(true); }
      }
      if (!cancelled) timer = setTimeout(refresh, 800);
    }
    refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [mode, monitoringSide]);
  const currentOrientation = active?.orientation;
  const selectedExercise = active?.exercise_key ?? exerciseKey;
  const needsPlaneCalibration = mode === 'live' && ['flexion', 'abduction'].includes(selectedExercise);
  const showPlaneAngles = mode !== 'live' || hardware?.axes_calibrated === true;
  const preview = !active && mode === 'live' && hardware?.receiving ? hardware.orientation_preview : null;
  const external = preview ? preview.ext_rotation : null;
  const internal = preview ? preview.int_rotation : null;
  const rotationPreview = exerciseKey === 'external_rotation' ? external : internal;
  const primaryPreview = exerciseKey === 'flexion' ? preview?.flexion : exerciseKey === 'abduction' ? preview?.abduction : rotationPreview;
  const orientation = currentOrientation?.quality_flag === 'VALID' &&
    (mode !== 'live' || hardware?.receiving) ? currentOrientation : null;

  const displayedMovement = orientation?.movement_angle_deg ??
    (showPlaneAngles ? preview?.total_elevation : preview?.neutral_rotation);
  const movementType = orientation?.movement_metric ?? (showPlaneAngles ? 'total_tilt' : 'neutral_rotation');
  const movementLabel = movementType === 'neutral_rotation' ? 'Wrist orientation change' : 'Total tilt from neutral';

  const elevationExercise = ['flexion', 'abduction'].includes(exerciseKey);
  const preferredPose = exerciseKey === 'abduction' ? 'side' : 'forward';
  const otherPose = preferredPose === 'side' ? 'forward' : 'side';
  const poses = hardware?.captured_poses ?? [];
  const nextPose = poses.includes(preferredPose) ? otherPose : preferredPose;
  const calibrationAvailable = !!hardware?.receiving && hardware.has_orientation && !!hardware.device_id;
  function calibrate(action: () => Promise<void>) {
    setCalibrating(true);
    run(async () => {
      try { await action(); } finally { setCalibrating(false); }
    });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-5 sm:px-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Live Monitoring</h1>
      </header>

      <div className="grid grid-cols-3 gap-2" aria-label="Session data source">
        {sources.map(({ id, label, icon: Icon }) => (
          <button type="button" key={id} disabled={!!active || busy} aria-pressed={mode === id}
            onClick={() => { setSource(id); setSaved(null); setError(''); }}
            className={`flex flex-col items-center justify-center gap-1 rounded-xl border px-2 py-2.5 text-center transition sm:flex-row sm:justify-start sm:gap-3 sm:px-3 sm:text-left ${mode === id ? 'border-teal-600 bg-teal-50 text-teal-950 ring-1 ring-teal-600' : 'border-slate-200 bg-white text-slate-800 hover:border-teal-400'}`}>
            <Icon className="h-4 w-4 shrink-0 text-teal-700 sm:h-5 sm:w-5" /><span className="text-xs font-semibold sm:text-sm">{label}</span>
          </button>
        ))}
      </div>

      {loading && <p role="status" className="text-sm text-slate-500">Loading exercises and recordings…</p>}
      {!!loadErrors.length && <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        {loadErrors.join(' ')} <button className="ml-2 underline" onClick={loadCatalog}>Retry</button>
      </div>}
      {!loading && isReplay && !catalog.length && !active && <p className="rounded-xl border bg-white p-4 text-sm text-slate-600">No replay recordings are available.</p>}
      {connectionError && <p role="alert" className="text-sm text-amber-800">Monitoring connection interrupted. Reconnecting…</p>}
      {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

      <section aria-label="Session setup and controls" className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        {(!active || isReplay) && <div className="grid grid-cols-2 gap-3 border-b border-slate-100 p-4 sm:grid-cols-[1fr_1.8fr_auto] sm:items-end sm:p-5">
          {isReplay ? <>
            {!active && <>
            <label className="text-xs font-semibold text-slate-600">Participant
              <select aria-label="Replay participant" className={field} disabled={!!active || busy || loading} value={record?.participant ?? participant} onChange={event => chooseParticipant(event.target.value)}>
                {!catalog.length && <option value="">No participants</option>}
                {[...new Set(catalog.map(item => item.participant))].map(id => <option key={id} value={id}>{id.replace('spars9x_', '')}</option>)}
              </select>
            </label>
            <label className="order-3 col-span-2 min-w-0 text-xs font-semibold text-slate-600 sm:order-none sm:col-span-1">Exercise recording
              <select aria-label="Exercise recording" className={field} disabled={!!active || busy || loading} value={record?.id ?? ''} onChange={event => { setSaved(null); setRecordingId(event.target.value); }}>
                {!catalog.length && <option value="">No recordings</option>}
                {catalog.filter(item => item.participant === (record?.participant ?? participant)).map(item =>
                  <option key={item.id} value={item.id}>{item.exercise_name} · side code {item.side_code} · {item.duration_s.toFixed(1)} s</option>)}
              </select>
            </label>
            </>}
            <label className="text-xs font-semibold text-slate-600">Playback speed
              <select className={field} value={currentSpeed} disabled={busy || completed} onChange={event => {
                const value = Number(event.target.value) as PlaybackSpeed;
                setSpeed(value);
                if (active) control('speed', value);
              }}>
                {speeds.map(value => <option key={value} value={value}>{value}×</option>)}
              </select>
            </label>
          </> : <>
            <label className="text-xs font-semibold text-slate-600">Participant
              <select className={field} value={active?.patient_id ?? patientId ?? ''} disabled={!!active || busy}
                onChange={event => {
                  const id = Number(event.target.value);
                  setPatientId(id);
                  setSide(patients.find(item => item.id === id)?.affected_side ?? 'right');
                }}>
                {!patients.length && <option value="">No participants</option>}
                {patients.map(person => <option key={person.id} value={person.id}>{person.name}</option>)}
              </select>
            </label>
            <label className="order-3 col-span-2 min-w-0 text-xs font-semibold text-slate-600 sm:order-none sm:col-span-1">Exercise
              <select aria-label="Exercise" className={field} value={active?.exercise_key ?? exerciseKey} disabled={!!active || busy} onChange={event => setExerciseKey(event.target.value)}>
                {exercises.map(item => <option key={item.exercise_key} value={item.exercise_key}>{item.display_name}</option>)}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-600">Shoulder
              <select className={field} value={active?.affected_side ?? side} disabled={!!active || busy}
                onChange={event => setSide(event.target.value as 'left' | 'right')}>
                <option value="left">Left</option><option value="right">Right</option>
              </select>
            </label>
          </>}
        </div>}

        <div className="bg-slate-900 p-4 text-white sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight">{displayName ?? 'Select an exercise'}</h2>
              {displayParticipant && <p className="mt-1 text-sm text-slate-300">{displayParticipant} · {isReplay && record ? `Side ${record.side_code}` : `${monitoringSide} side`}</p>}
            </div>
            <div className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-sm font-medium" role="status">{calibrating ? 'Calibrating' : connectionError || hardwareError && mode === 'live' ? 'Error' : mode === 'live' && hardware && !hardware.receiving ? 'Disconnected' : mode === 'live' && active ? 'Streaming' : status}</div>
          </div>
          {isReplay && record && <div className="mt-5 space-y-2">
            <div className="flex justify-between gap-2 text-sm text-slate-200">
              <span className="flex items-center gap-2"><Clock3 className="h-4 w-4" />{elapsed.toFixed(1)} s elapsed</span>
              <span>{record.duration_s.toFixed(1)} s recording</span>
            </div>
            <progress aria-label="Replay progress" className="h-2 w-full overflow-hidden rounded-full accent-teal-400 [&::-webkit-progress-bar]:bg-slate-700 [&::-webkit-progress-value]:bg-teal-400"
              value={elapsed} max={record.duration_s} />
          </div>}
          {!isReplay && active && <p className="mt-4 font-mono text-sm text-slate-300">{formatTime(elapsed)} recorded</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2 p-4 sm:p-5">
          {!active && <button className={primary} disabled={busy || !canStart} onClick={start}><Play className="h-4 w-4" />{isReplay ? 'Start replay' : 'Start session'}</button>}
          {active && isReplay && <>
            {!completed && <button className={button} disabled={busy} onClick={() => control(active.status === 'paused' ? 'resume' : 'pause')}>
              {active.status === 'paused' ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}{active.status === 'paused' ? 'Resume' : 'Pause'}
            </button>}
            <button className={button} disabled={busy} onClick={() => control('restart', currentSpeed)}><RotateCcw className="h-4 w-4" />Restart</button>
          </>}
          {active && <>
            <button className={primary} disabled={busy || (isReplay && !elapsed)} onClick={() => setSaving(value => !value)}><Save className="h-4 w-4" />Finish &amp; Save</button>
            <button className="px-2 py-2 text-sm font-medium text-slate-600 hover:text-rose-700" disabled={busy} onClick={() => {
              if (window.confirm('Discard this unsaved session?')) run(async () => { await api.discardSession(active.session_id); setActive(null); setSaving(false); });
            }}>Discard</button>
          </>}
        </div>

        {mode === 'live' && !active && <details className="border-t border-slate-100 px-4 py-3 sm:px-5">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">Session options{(targetReps || targetAngle) && ' · targets set'}</summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <label className="text-sm text-slate-700">Prescribed reps
              <input className={field} type="number" min={1} max={500} value={targetReps} onChange={event => setTargetReps(event.target.value)} />
            </label>
            <label className="text-sm text-slate-700">Prescribed excursion (°)
              <input className={field} type="number" min={0.1} max={180} step="any" value={targetAngle} onChange={event => setTargetAngle(event.target.value)} />
            </label>
            <label className="text-sm text-slate-700">Rep detection threshold (°)
              <input type="number" min={5} max={120} step="1" className={field} disabled={busy}
                value={repPeak} onChange={event => setRepPeak(event.target.value)} />
            </label>
          </div>
        </details>}

        {saving && active && <div className="grid gap-3 border-t bg-slate-50 p-5 sm:grid-cols-2">
          <label className="text-sm text-slate-700">Session notes (optional)<textarea className={field} value={notes} onChange={event => setNotes(event.target.value)} /></label>
          {mode === 'live' && <label className="text-sm text-slate-700">Self-reported pain (optional, 0–10)
            <input className={field} type="number" min={0} max={10} value={pain} onChange={event => setPain(event.target.value)} />
          </label>}
          {mode === 'live' && <label className="text-sm text-slate-700">Self-reported stiffness (optional, 0–10)
            <input className={field} type="number" min={0} max={10} value={stiffness} onChange={event => setStiffness(event.target.value)} />
          </label>}
          <div className="flex items-center gap-2 sm:col-span-2">
            <button className={primary} onClick={save} disabled={busy}>Confirm &amp; Save</button>
            <button className={button} onClick={() => setSaving(false)}>Cancel</button>
          </div>
        </div>}
      </section>

      {!isReplay && (
        <section className="grid gap-4 lg:grid-cols-2" aria-label="Live orientation and sensor status">
          <div className="min-w-0">
            <ArmVisualization angle={needsPlaneCalibration ? displayedMovement ?? null : orientation?.primary_angle ?? primaryPreview ?? null}
              maxAngle={orientation?.session_max_angle ?? null}
              angleLabel={needsPlaneCalibration ? movementLabel : undefined}
              movementPreview={needsPlaneCalibration && movementType === 'neutral_rotation'}
              waitingMessage={mode === 'live' && calibrationAvailable && !hardware?.neutral_calibrated
                ? active ? 'Finish or discard this session, then select Set neutral.' : 'Select Set neutral to start the arm preview.'
                : undefined}
              exerciseKey={active?.exercise_key ?? exerciseKey}
              affectedSide={(active?.affected_side ?? side) === 'left' ? 'left' : 'right'}
              dataSource={mode} />
          </div>
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h2 className="text-lg font-semibold">Session measurements</h2>
              {mode === 'live' && <button className={button}
                disabled={busy || !!active || !hardware?.receiving || !hardware.has_orientation || !hardware.device_id}
                onClick={() => calibrate(async () => {
                  if (!hardware?.device_id) return;
                  setNeutralMessage('');
                  await api.calibrateNeutral(hardware.device_id);
                  setNeutralMessage('Neutral captured at 0°.');
                  setHardware(await api.getHardwareStream(monitoringSide));
                })}>Set neutral</button>}
            </div>
            {mode === 'live' && !active && elevationExercise && hardware?.neutral_calibrated && !hardware.axes_calibrated && (
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                <summary className="cursor-pointer font-semibold">Shared sensor setup · {poses.length}/2 directions</summary>
                <p className="mt-2">Forward and side raises establish the torso axes.</p>
                <button className={`${button} mt-2`} disabled={busy || !calibrationAvailable}
                  onClick={() => calibrate(async () => {
                    if (!hardware?.device_id) return;
                    await api.captureMotionAxis(hardware.device_id, nextPose, side);
                    setHardware(await api.getHardwareStream(monitoringSide));
                    setNeutralMessage(poses.length ? 'Torso axes aligned.' : 'Direction captured.');
                  })}>{nextPose === 'forward' ? 'Capture forward raise' : 'Capture side raise'}</button>
              </details>
            )}
            {mode === 'live' && !active && <p className="text-sm text-slate-600">
              {neutralMessage ? <span role="status">{neutralMessage}</span>
                : !calibrationAvailable ? 'Waiting for chest and wrist readings.'
                : hardware?.neutral_calibrated ? 'Neutral set.' : 'Lower the arm and set neutral.'}
            </p>}
            <dl className="divide-y divide-slate-100 text-sm">
              <div className="flex items-center justify-between gap-3 py-3">
                <dt className="text-slate-600">Estimated reps</dt>
                <dd className="text-2xl font-semibold tabular-nums">{metrics?.estimated_repetition_count ?? '—'}</dd>
              </div>
              {repReview?.median_peak_deg != null && <div className="flex justify-between gap-3 py-3">
                <dt className="text-slate-600">Typical peak <span className="text-xs">(last 3 reps)</span></dt>
                <dd className="font-semibold">{measurement(repReview.median_peak_deg, '°')}</dd>
              </div>}
            </dl>
            {active && needsPlaneCalibration && displayedMovement == null && <p className="text-sm text-amber-800">
              {hardware?.receiving && !hardware.neutral_calibrated
                ? 'Finish or discard the session to set neutral.'
                : 'Waiting for paired orientations.'}
            </p>}

          </div>
        </section>
      )}

      {(completed || saved) && <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
        <span className="flex items-center gap-2"><CircleCheck className="h-5 w-5" />
          {saved ? `Session #${saved.session.id} saved · ${saved.exercise_name} · ${saved.session.duration_seconds.toFixed(1)} s` : 'Replay complete. Review the recording summary, then save the session.'}
        </span>
        {saved && onOpenProgress && <button className="font-semibold underline" onClick={() => onOpenProgress(saved.session.data_source)}>View progress</button>}
      </div>}

      {isReplay && metrics?.estimated_repetition_count != null && (
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span className="text-sm text-slate-600">Estimated reps</span>
          <strong className="text-xl tabular-nums">{metrics.estimated_repetition_count}</strong>
        </div>
      )}

      {(active || saved) && <details className="rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Movement details</summary>
        <div className="mt-3 space-y-3">
          <MovementAnalytics metrics={metrics} />
          {orientation?.angular_velocity != null && displayedMovement != null && <p className="text-sm text-slate-600">Angle speed {measurement(orientation.angular_velocity, '°/s')}</p>}
          {orientation?.off_plane && showPlaneAngles && <p className="text-sm text-slate-600">Movement includes forward and sideways motion.</p>}
          <SessionTimeline metrics={metrics} duration={active ? duration : saved?.session.duration_seconds ?? duration} elapsed={elapsed} />
        </div>
      </details>}

      <details className="rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer select-none text-sm font-semibold text-slate-700">Technical details</summary>
        <div className="mt-4 space-y-3 text-sm text-slate-600">
            {mode === 'live' && <div className="space-y-2 border-t border-slate-200 pt-4 text-sm">
              <h3 className="font-semibold">ESP32 packet monitor</h3>
              <p className={hardware?.receiving ? 'font-semibold text-teal-700' : 'font-semibold text-amber-800'}>
                {hardwareError ? 'Backend status unavailable' : !hardware ? 'Checking for ESP32 packets…' : hardware.receiving
                  ? 'Receiving ESP32 packets' : hardware.valid_packets ? 'ESP32 stream has stopped' : 'No valid ESP32 packets received'}
              </p>
              {hardware && <>
                <p>Accepted packets <b>{hardware.valid_packets}</b> · Rejected <b>{hardware.rejected_packets}</b></p>
                <p>Last valid packet {hardware.last_packet_age_s == null ? '—' : `${hardware.last_packet_age_s.toFixed(1)} s ago`}</p>
                {hardware.sensors.length > 0 && <p>{hardware.device_id} · {hardware.sensors.join(' + ')}</p>}
                {hardware.receiving && !hardware.has_orientation && <p>Arm animation requires chest and limb orientation in the same packet.</p>}
                {hardware.receiving && !hardware.has_wrist_vectors && <p>Wrist speed and jerk require wrist accelerometer and gyroscope values.</p>}
              </>}
              {active && currentOrientation && !orientation && currentOrientation.quality_flag !== 'VALID' &&
                <p className="text-slate-500">Latest orientation status: {currentOrientation.quality_flag.toLowerCase().replace(/_/g, ' ')}.</p>}
            </div>}
          {!!(active?.wrist_trace.length || saved?.session.movement_analytics?.wrist_trace?.length) ?
            <WristChart data={active?.wrist_trace ?? saved?.session.movement_analytics?.wrist_trace ?? []} />
            : <p>Wrist signals appear here when accelerometer and gyroscope data are received.</p>}
          {mode === 'live' && <OrientationDiagnostics key={`${exerciseKey}:${side}:${neutralMessage}`}
            hardware={hardware} exercise={active?.exercise_key ?? exerciseKey} active={!!active} />}
          {metrics?.relative_excursion_deg != null && <p>Chest-relative sensor excursion {measurement(metrics.relative_excursion_deg, '°')}. Depends on sensor placement and calibration.</p>}
        </div>
      </details>
    </div>
  );
}
