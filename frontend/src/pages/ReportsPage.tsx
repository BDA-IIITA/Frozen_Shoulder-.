import React, { useEffect, useState } from 'react';
import {
  FileText,
  Printer,
  Download,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Calendar,
  User,
  Activity,
  Cpu,
  Layers,
  Sparkles
} from 'lucide-react';
import { PhysiotherapyReport, SessionRecord } from '../types';
import { api } from '../services/api';

export const ReportsPage: React.FC = () => {
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [report, setReport] = useState<PhysiotherapyReport | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSessions().then((list) => {
      setSessions(list);
      if (list.length > 0) {
        setSelectedSessionId(list[0].id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedSessionId) {
      setLoading(true);
      api.getSessionReport(selectedSessionId)
        .then(setReport)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [selectedSessionId]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-5xl mx-auto">
      {/* Title & Print Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Physiotherapy Clinical Report</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Standardized rehabilitation summary for clinician and physiotherapist consultation
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <select
            value={selectedSessionId || ''}
            onChange={(e) => setSelectedSessionId(Number(e.target.value))}
            className="text-xs bg-white border border-slate-300 rounded-lg px-3 py-2 font-semibold text-slate-800"
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                Session #{s.id} ({s.exercise_key} — {s.rom}°)
              </option>
            ))}
          </select>

          <button
            onClick={handlePrint}
            className="inline-flex items-center space-x-1.5 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-xs transition-colors"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print Report</span>
          </button>
        </div>
      </div>

      {loading || !report ? (
        <div className="p-12 text-center text-slate-400 text-xs">
          Loading clinical report...
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-8 shadow-sm space-y-6 print:border-none print:shadow-none print:p-0">
          {/* Report Header */}
          <div className="border-b border-slate-200 pb-5 flex justify-between items-start">
            <div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-600"></span>
                <span className="text-xs font-bold text-teal-700 tracking-wider uppercase">ShoulderSense Clinical Telemetry</span>
              </div>
              <h2 className="text-xl font-bold text-slate-900 mt-1">Movement Analysis & ROM Progress Report</h2>
              <div className="text-xs text-slate-500 mt-0.5">
                Report Reference: <span className="font-mono font-semibold">{report.report_id}</span> • Generated {report.generated_at}
              </div>
            </div>

            <div className="text-right">
              <span className={`inline-block px-2.5 py-1 rounded text-xs font-bold uppercase ${
                report.session.data_source === 'demo' ? 'bg-amber-100 text-amber-800' : 'bg-green-100 text-green-800'
              }`}>
                {report.session.data_source} telemetry
              </span>
            </div>
          </div>

          {/* Patient & Session Identification */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-50 border border-slate-100 text-xs">
            <div>
              <span className="text-slate-400 font-medium">Participant Name</span>
              <div className="font-bold text-slate-900 mt-0.5">{report.patient.display_name}</div>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Target Shoulder</span>
              <div className="font-bold text-slate-900 mt-0.5 capitalize">{report.patient.affected_side} Shoulder</div>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Session Timestamp</span>
              <div className="font-bold text-slate-900 mt-0.5">{report.session.date}</div>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Protocol / Exercise</span>
              <div className="font-bold text-teal-800 mt-0.5">{report.session.exercise_name}</div>
            </div>
          </div>

          {/* Kinematic Measurement Results Grid */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
              Biomechanical Kinematics
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3.5 rounded-lg border border-slate-200">
                <span className="text-slate-400 font-medium">Measured ROM</span>
                <div className="text-2xl font-bold text-teal-700 mt-1">{report.session.rom}°</div>
                <div className="text-[10px] text-slate-500 mt-1">
                  Elevation range: {report.session.min_angle}° to {report.session.max_angle}°
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-slate-200">
                <span className="text-slate-400 font-medium">Completed Repetitions</span>
                <div className="text-2xl font-bold text-slate-900 mt-1">{report.session.repetitions}</div>
                <div className="text-[10px] text-slate-500 mt-1">Duration: {report.session.duration_seconds}s</div>
              </div>

              <div className="p-3.5 rounded-lg border border-slate-200">
                <span className="text-slate-400 font-medium">ROM Change vs. Prior</span>
                <div className="text-2xl font-bold text-slate-900 mt-1">
                  {report.session.rom_change_vs_prior !== null
                    ? `${report.session.rom_change_vs_prior > 0 ? '+' : ''}${report.session.rom_change_vs_prior}°`
                    : '—'}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">Same exercise comparison</div>
              </div>

              <div className="p-3.5 rounded-lg border border-slate-200">
                <span className="text-slate-400 font-medium">Kinematic Smoothness</span>
                <div className="text-2xl font-bold text-purple-700 mt-1">
                  {report.session.smoothness_score ?? '—'}/100
                </div>
                <div className="text-[10px] text-slate-500 mt-1">
                  Avg rep: {report.session.avg_rep_duration ?? '—'}s
                </div>
              </div>
            </div>
          </div>

          {/* Clinical Narrative Summary */}
          <div className="bg-teal-50/70 border border-teal-100 rounded-xl p-4 text-xs leading-relaxed text-slate-800 space-y-1.5">
            <h3 className="font-bold text-teal-900">Biomechanical Narrative</h3>
            <p>{report.clinical_summary}</p>
          </div>

          {/* Machine Learning & Demonstration Assessment */}
          <div className="border border-slate-200 rounded-xl p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2">
              <span className="font-bold text-slate-900">Movement Quality Model Evaluation</span>
              <span className="text-[10px] font-mono text-slate-400">STATUS: {report.ml_status.status_message}</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <span className="text-slate-400 font-medium">ML Classifier Output:</span>
                <div className="font-semibold text-slate-700 mt-1">
                  {report.ml_status.predicted_class || 'ML movement assessment is not configured yet.'}
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  * Pipeline awaits cohort validation before enabling automated inference.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400 font-medium">Demonstration Heuristic:</span>
                  <span className="text-[10px] text-amber-700 font-bold uppercase bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                    Rule-Based Demo
                  </span>
                </div>
                <div className="font-semibold text-slate-800 mt-1">
                  {report.rule_based_demonstration.demonstration_category} ({report.rule_based_demonstration.heuristic_score}/100)
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  {report.rule_based_demonstration.disclaimer}
                </p>
              </div>
            </div>
          </div>

          {/* Notes */}
          {report.session.notes && (
            <div className="p-3 rounded-lg bg-slate-50 text-xs text-slate-700">
              <strong className="text-slate-900">Session Notes:</strong> {report.session.notes}
            </div>
          )}

          {/* Signoff / Disclaimer */}
          <div className="border-t border-slate-200 pt-4 flex flex-col sm:flex-row sm:items-center justify-between text-[11px] text-slate-400 gap-3">
            <div className="max-w-xl leading-tight">
              <strong>Disclaimer:</strong> {report.disclaimer}
            </div>
            <div className="text-right">
              <div className="font-medium text-slate-600">ShoulderSense Kinematic Core</div>
              <div>ESP32 DevKit V1 + BNO086 Dual IMU</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
