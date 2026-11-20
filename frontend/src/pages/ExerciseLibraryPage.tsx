import React, { useEffect, useState } from 'react';
import {
  Compass,
  ArrowUpRight,
  Info,
  CheckCircle2,
  Activity,
  Sliders,
  ChevronRight,
  ShieldCheck,
  X
} from 'lucide-react';
import { Exercise, NavItemKey } from '../types';
import { api } from '../services/api';

interface ExerciseLibraryPageProps {
  onNavigateToMonitoring: () => void;
}

export const ExerciseLibraryPage: React.FC<ExerciseLibraryPageProps> = ({
  onNavigateToMonitoring,
}) => {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getExercises()
      .then(setExercises)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Exercise Library</h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Evidence-aligned shoulder mobility protocols for frozen shoulder rehabilitation
        </p>
      </div>

      {/* Clinical Disclaimer Banner */}
      <div className="bg-slate-100 border border-slate-200/80 rounded-xl p-4 text-xs text-slate-600 flex items-start space-x-2.5">
        <ShieldCheck className="w-4 h-4 text-teal-600 flex-shrink-0 mt-0.5" />
        <p>
          Target angles shown are <strong>configurable clinician-defined reference goals</strong>, not universal medical standards. 
          Patients should never force movement beyond their pain-free boundary.
        </p>
      </div>

      {/* Exercise Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {exercises.map((ex) => (
          <div
            key={ex.exercise_key}
            className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-teal-700 bg-teal-50 px-2.5 py-1 rounded-md border border-teal-100">
                  {ex.category}
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Target: {ex.default_target_angle}°
                </span>
              </div>

              <h3 className="text-base font-bold text-slate-900 mb-1">{ex.display_name}</h3>
              <p className="text-xs text-slate-600 leading-relaxed mb-4">{ex.description}</p>

              <div className="bg-slate-50 rounded-lg p-3 space-y-1.5 text-xs border border-slate-100 mb-4">
                <div className="flex justify-between">
                  <span className="text-slate-500">Target Movement:</span>
                  <span className="font-medium text-slate-800 text-right">{ex.target_movement}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Primary IMU Metric:</span>
                  <span className="font-semibold text-teal-700 text-right">{ex.primary_metric}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Hysteresis Thresholds:</span>
                  <span className="font-mono text-slate-700 text-right">
                    Ascent: &gt;{ex.threshold_up}° | Rest: &lt;{ex.threshold_down}°
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setSelectedExercise(ex)}
                className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold py-2 rounded-lg transition-colors text-center"
              >
                View Instructions
              </button>
              <button
                onClick={onNavigateToMonitoring}
                className="flex-1 bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold py-2 rounded-lg transition-colors flex items-center justify-center space-x-1"
              >
                <Activity className="w-3.5 h-3.5" />
                <span>Start Monitoring</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Exercise Detail Modal */}
      {selectedExercise && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4 border border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-bold text-teal-700 uppercase tracking-wider">
                  {selectedExercise.category}
                </span>
                <h3 className="font-bold text-slate-900 text-lg">{selectedExercise.display_name}</h3>
              </div>
              <button
                onClick={() => setSelectedExercise(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs leading-relaxed text-slate-700">
              <div>
                <h4 className="font-bold text-slate-900 mb-1">Anatomical Focus & Objective</h4>
                <p>{selectedExercise.description}</p>
              </div>

              <div className="p-3.5 bg-teal-50 border border-teal-100 rounded-lg">
                <h4 className="font-bold text-teal-900 mb-1">Step-by-Step Patient Instructions</h4>
                <p className="text-teal-950 whitespace-pre-line">{selectedExercise.instructions}</p>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                <div className="font-semibold text-slate-800">Biomechanical Measurement Protocol:</div>
                <div>• Primary Angle: {selectedExercise.primary_metric}</div>
                <div>• Minimum Rep Duration: {selectedExercise.min_rep_duration_sec}s</div>
                <div>• Clinician Target Angle: {selectedExercise.default_target_angle}°</div>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setSelectedExercise(null)}
                className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800"
              >
                Close
              </button>
              <button
                onClick={() => {
                  setSelectedExercise(null);
                  onNavigateToMonitoring();
                }}
                className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs rounded-lg transition-colors flex items-center space-x-1"
              >
                <Activity className="w-3.5 h-3.5" />
                <span>Launch in Live Monitoring</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
