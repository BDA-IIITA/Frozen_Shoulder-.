import { useState } from 'react';
import type { HardwareStreamStatus } from '../../types';
import { measurement } from './MovementAnalytics';

export function OrientationDiagnostics({ hardware, exercise, active }: {
  hardware: HardwareStreamStatus | null;
  exercise: string;
  active: boolean;
}) {
  const [reference, setReference] = useState('');
  const [records, setRecords] = useState<Array<{ reference: number; predicted: number }>>([]);
  const diagnostic = hardware?.diagnostic;
  const preview = hardware?.orientation_preview;
  const predicted = exercise === 'flexion' ? preview?.flexion : exercise === 'abduction' ? preview?.abduction : undefined;
  const angle = Number(reference);
  const canCapture = !active && !!hardware?.axes_calibrated && !!hardware.receiving && predicted != null &&
    (preview?.movement_plane === 'neutral' || preview?.movement_plane === exercise) &&
    reference.trim() !== '' && Number.isFinite(angle) && angle >= 0 && angle <= 180;
  const quaternion = (values: number[]) => values.map(value => value.toFixed(4)).join(', ');

  return <div className="space-y-4 border-t border-slate-200 pt-4">
    <h3 className="font-semibold text-slate-900">Orientation diagnostics</h3>
    <p>Calibration: {hardware?.axes_calibrated ? 'Torso axes aligned' : hardware?.neutral_calibrated ? 'Neutral only · assumed torso axes' : 'Neutral unset · assumed torso axes'}</p>
    {diagnostic ? <dl className="grid gap-2 rounded-lg bg-slate-50 p-3 font-mono text-xs sm:grid-cols-2">
      <div><dt>Chest quaternion (x, y, z, w)</dt><dd>{quaternion(diagnostic.chest)}</dd></div>
      <div><dt>Limb quaternion ({diagnostic.limb_key}, x, y, z, w)</dt><dd>{quaternion(diagnostic.limb)}</dd></div>
      <div><dt>Neutral-relative quaternion</dt><dd>{quaternion(diagnostic.relative)}</dd></div>
      <div><dt>Latest processed angle / plane</dt><dd>{measurement(diagnostic.angle_deg, '°')} · {diagnostic.movement_plane}</dd></div>
      <div><dt>Total tilt from neutral</dt><dd>
        {measurement(preview?.total_elevation ?? diagnostic.total_elevation_deg, '°')}
        {hardware?.axes_calibrated ? ' · calibrated torso axes' : ' · assumed torso axes'}
      </dd></div>
      <div><dt>Packet device time / receipt age</dt><dd>{diagnostic.packet_timestamp_s.toFixed(3)} s · {diagnostic.sample_age_s.toFixed(2)} s ago</dd></div>
      <div><dt>Chest / limb sample times</dt><dd>{diagnostic.sensor_timestamps_s.map(time => time == null ? 'Unavailable' : `${time.toFixed(3)} s`).join(' / ')}</dd></div>
      <div><dt>Synchronization</dt><dd>{diagnostic.sync === 'unknown' ? 'Unknown · individual sample times missing' : `${diagnostic.sync.replace(/_/g, ' ')} · ${Math.round((diagnostic.skew_s ?? 0) * 1000)} ms skew`}</dd></div>
      <div><dt>Orientation quality</dt><dd>{diagnostic.quality}{diagnostic.off_plane ? ' · outside selected plane' : ''}</dd></div>
    </dl> : <p>Waiting for a paired chest and limb orientation packet.</p>}
    <p>Forearm rotation, elbow movement, sensor slippage, and different magnetic headings can affect the estimate.</p>
    {['flexion', 'abduction'].includes(exercise) && <div className="space-y-2">
      <h4 className="font-semibold text-slate-900">Verify against a measured angle</h4>
      <p>Before recording, align the sensors, hold a reference pose, and enter the angle measured independently. The app records the difference without changing calibration.</p>
      <div className="flex flex-wrap items-end gap-2">
        <label>Reference angle (°)<input className="ml-2 w-24 rounded-lg border p-1.5" type="number" min={0} max={180} value={reference} onChange={e => setReference(e.target.value)} /></label>
        <button className="rounded-lg border px-3 py-1.5 font-semibold disabled:opacity-50" disabled={!canCapture}
          onClick={() => { if (predicted != null) setRecords(rows => [...rows, { reference: angle, predicted }]); }}>Compare pose</button>
      </div>
      <p className="text-xs">Current estimate {measurement(predicted, '°')} · {preview?.movement_plane ?? 'No preview'}</p>
      {!!records.length && <table className="w-full text-left text-xs">
        <thead><tr><th>Reference</th><th>Estimate</th><th>Absolute error</th></tr></thead>
        <tbody>{records.map((row, i) => <tr key={i}>
          <td>{row.reference.toFixed(1)}°</td><td>{row.predicted.toFixed(1)}°</td><td>{Math.abs(row.predicted - row.reference).toFixed(1)}°</td>
        </tr>)}</tbody>
        <tfoot><tr><th colSpan={2}>Mean absolute error ({records.length} poses)</th><td>{(records.reduce((total, row) => total + Math.abs(row.predicted - row.reference), 0) / records.length).toFixed(1)}°</td></tr></tfoot>
      </table>}
    </div>}
  </div>;
}
