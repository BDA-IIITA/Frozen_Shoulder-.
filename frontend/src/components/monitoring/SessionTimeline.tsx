import type { MovementAnalytics } from '../../types';

export const formatTime = (seconds: number) => {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
};

export function SessionTimeline({ metrics, duration, elapsed }: { metrics?: MovementAnalytics | null; duration: number; elapsed: number }) {
  const cycles = metrics?.repetition_timeline ?? [];
  const scale = Math.max(duration, elapsed, 1);
  const percent = (value: number) => Math.max(0, Math.min(100, value / scale * 100));
  const span = (start: number, end: number) => ({
    left: `${percent(start)}%`, width: `${Math.max(.6, percent(end) - percent(start))}%`,
  });

  return (
    <section aria-labelledby="timeline-title" className="rounded-lg bg-slate-50 p-3">
      <h2 id="timeline-title" className="font-semibold text-slate-900">Rep timeline</h2>
      <div className="mt-3 grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 gap-y-3 text-xs sm:grid-cols-[9rem_minmax(0,1fr)]">
        <span className="font-medium text-slate-600">Estimated cycles</span>
        <div className="relative h-6 overflow-hidden rounded-md bg-slate-200/70" aria-label={`${cycles.length} cycle positions`}>
          {cycles.map((cycle, index) => (
            <div key={index} style={span(cycle.start_s, cycle.end_s)} className="absolute inset-y-1 rounded border border-indigo-400 bg-indigo-200"
              title={`Estimated cycle ${index + 1}: ${cycle.start_s.toFixed(2)}–${cycle.end_s.toFixed(2)} s`}>
              {cycle.marker_s != null && cycle.end_s > cycle.start_s && (
                <i className="absolute inset-y-0 w-px bg-indigo-700"
                  style={{ left: `${100 * (cycle.marker_s - cycle.start_s) / (cycle.end_s - cycle.start_s)}%` }} />
              )}
            </div>
          ))}
          {!cycles.length && <span className="px-2 leading-6 text-slate-500">No estimates yet</span>}
        </div>
        <div />
        <div className="flex justify-between font-mono text-slate-500"><span>0:00</span><span>{formatTime(scale / 2)}</span><span>{formatTime(scale)}</span></div>
      </div>
    </section>
  );
}
