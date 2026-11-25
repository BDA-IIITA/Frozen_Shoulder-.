import React, { useEffect, useRef, useState } from 'react';
import { AffectedSide, DataSourceMode } from '../../types';

interface ArmVisualizationProps {
  angleLabel?: string;
  movementPreview?: boolean;
  waitingMessage?: string;
  angle: number | null;           // Current primary elevation angle in degrees (0 to 180)
  maxAngle: number | null;        // Session max angle
  exerciseKey: string;     // flexion, abduction, external_rotation, internal_rotation
  affectedSide: AffectedSide;
  dataSource: DataSourceMode;
}

export const ArmVisualization: React.FC<ArmVisualizationProps> = ({
  angleLabel = "Current Angle",
  movementPreview = false,
  waitingMessage = 'Waiting for a fresh chest and wrist orientation pair.',
  angle,
  maxAngle,
  exerciseKey,
  affectedSide,
  dataSource,
}) => {
  const [visualAngle, setVisualAngle] = useState(angle ?? 0);
  const previous = useRef(angle ?? 0);
  useEffect(() => {
    const target = angle ?? 0;
    if (angle == null || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      previous.current = target;
      setVisualAngle(target);
      return;
    }
    const initial = previous.current;
    let frame = 0;
    let started: number | null = null;
    const animate = (time: number) => {
      started ??= time;
      const progress = Math.min(1, (time - started) / 180);
      previous.current = initial + (target - initial) * (1 - (1 - progress) ** 2);
      setVisualAngle(previous.current);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [angle]);
  const clampedAngle = Math.max(0, Math.min(180, visualAngle));
  const isRight = affectedSide === 'right';

  // Glenohumeral joint pivot coordinates
  const pivotX = isRight ? 210 : 90;
  const pivotY = 130;
  const upperArmLength = 85;
  const forearmLength = 80;

  // Rotation calculation:
  // For right arm abduction/flexion: 0 deg points down (90 deg in screen coords).
  // Raising the arm rotates counter-clockwise (or clockwise for left).
  const angleRad = (clampedAngle * Math.PI) / 180;
  
  let elbowX: number;
  let elbowY: number;
  let handX: number;
  let handY: number;

  if (exerciseKey === 'external_rotation' || exerciseKey === 'internal_rotation') {
    // Upper arm stays vertical at side, forearm rotates outward/inward
    elbowX = pivotX;
    elbowY = pivotY + upperArmLength;
    const rotSign = isRight ? 1 : -1;
    const rotRad = (clampedAngle * Math.PI) / 180 * rotSign * (exerciseKey === 'internal_rotation' ? -1 : 1);
    handX = elbowX + Math.sin(rotRad) * forearmLength;
    handY = elbowY - Math.cos(rotRad) * (forearmLength * 0.35); // perspective projection
  } else {
    // Elevation (flexion/abduction)
    const sign = isRight ? 1 : -1;
    // At 0 deg: elbow is straight down at (pivotX, pivotY + upperArmLength)
    // At 90 deg: arm is horizontal pointing outward (or forward)
    elbowX = pivotX + Math.sin(angleRad) * upperArmLength * sign;
    elbowY = pivotY + Math.cos(angleRad) * upperArmLength;

    handX = elbowX + Math.sin(angleRad) * forearmLength * sign;
    handY = elbowY + Math.cos(angleRad) * forearmLength;
  }

  const imuArmX = dataSource === 'live' ? handX : (pivotX + elbowX) / 2;
  const imuArmY = dataSource === 'live' ? handY : (pivotY + elbowY) / 2;

  return (
    <div className="flex flex-col items-center justify-between h-full bg-slate-900 rounded-xl p-4 text-white relative shadow-sm border border-slate-800">
      {/* Header Info */}
      <div className="w-full flex items-center justify-between text-xs text-slate-400 pb-2 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <span className="inline-block w-2 h-2 rounded-full bg-teal-400 "></span>
          <span className="font-medium text-slate-200">Arm movement</span>
        </div>
        <span className="bg-slate-800 px-2 py-0.5 rounded text-[11px] font-mono text-teal-300">
          {angle == null ? 'Waiting' : dataSource !== 'live' ? 'Synthetic' : movementPreview ? 'Wrist preview' : 'Live'}
        </span>
      </div>

      {/* SVG Upper Body Rig */}
      <div className="w-full flex justify-center py-2">
        <svg viewBox="-84 0 468 320" className="h-48 w-full max-w-lg overflow-visible sm:h-60">
          <defs>
            <linearGradient id="torsoGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id="armGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0d9488" />
              <stop offset="100%" stopColor="#14b8a6" />
            </linearGradient>
          </defs>

          {/* Reference grid arc */}
          <circle
            cx={pivotX}
            cy={pivotY}
            r={upperArmLength + forearmLength}
            fill="none"
            stroke="#334155"
            strokeDasharray="3 4"
            strokeWidth="1.5"
          />

          {/* Torso & Head Silhouette */}
          {/* Head */}
          <circle cx="150" cy="55" r="24" fill="#475569" stroke="#64748b" strokeWidth="2" />
          {/* Neck */}
          <rect x="142" y="78" width="16" height="18" fill="#475569" />
          {/* Torso */}
          <path
            d="M 110,95 L 190,95 L 175,230 L 125,230 Z"
            fill="url(#torsoGrad)"
            stroke="#475569"
            strokeWidth="2"
          />
          {/* Chest IMU Sensor #1 */}
          <rect
            x="142"
            y="125"
            width="16"
            height="18"
            rx="3"
            fill="#0ea5e9"
            stroke="#38bdf8"
            strokeWidth="1.5"
          />
          <text x="150" y="137" fill="#ffffff" fontSize="8" fontWeight="bold" textAnchor="middle">
            IMU 1
          </text>
          <text x="150" y="153" fill="#94a3b8" fontSize="8" textAnchor="middle">
            Torso Ref
          </text>

          {/* Inactive Opposite Arm (subtle) */}
          {isRight ? (
            <line x1="110" y1="115" x2="85" y2="210" stroke="#334155" strokeWidth="8" strokeLinecap="round" />
          ) : (
            <line x1="190" y1="115" x2="215" y2="210" stroke="#334155" strokeWidth="8" strokeLinecap="round" />
          )}

          {/* Active Glenohumeral Pivot Joint */}
          <circle cx={pivotX} cy={pivotY} r="9" fill="#0d9488" stroke="#5eead4" strokeWidth="2" />

          {/* Active Upper Arm Segment */}
          <line
            x1={pivotX}
            y1={pivotY}
            x2={elbowX}
            y2={elbowY}
            stroke="url(#armGrad)"
            strokeWidth="10"
            strokeLinecap="round"
          />

          {/* Active Forearm Segment */}
          <line
            x1={elbowX}
            y1={elbowY}
            x2={handX}
            y2={handY}
            stroke="#14b8a6"
            strokeWidth="8"
            strokeLinecap="round"
          />

          {/* Elbow Joint */}
          <circle cx={elbowX} cy={elbowY} r="6" fill="#0f766e" stroke="#5eead4" strokeWidth="1.5" />

          {/* Limb IMU Sensor #2 */}
          <circle cx={imuArmX} cy={imuArmY} r="7" fill="#f59e0b" stroke="#fcd34d" strokeWidth="1.5" />
          <text x={imuArmX + 12} y={imuArmY + 3} fill="#fcd34d" fontSize="9" fontWeight="bold">
            IMU 2
          </text>

          {/* Hand Endpoint Marker */}
          <circle cx={handX} cy={handY} r="5" fill="#5eead4" />

          {/* Angle Annotation Arc */}
          <path
            d={`M ${pivotX} ${pivotY + 45} A 45 45 0 0 ${isRight ? 1 : 0} ${pivotX + Math.sin(angleRad) * 45 * (isRight ? 1 : -1)} ${pivotY + Math.cos(angleRad) * 45}`}
            fill="none"
            stroke="#2dd4bf"
            strokeWidth="2"
          />
        </svg>
      </div>

      {/* Numerical Angle Readout Footer */}
      <div className="w-full bg-slate-800/80 rounded-lg p-2.5 flex items-center justify-around border border-slate-700">
        <div className="text-center">
          <div className="text-xs font-medium text-slate-300">{angleLabel}</div>
          <div className="text-xl font-bold text-teal-400">{angle == null ? '—' : `${angle.toFixed(1)}°`}</div>
        </div>
        {maxAngle != null && <div className="text-center">
          <div className="text-xs text-slate-300">Peak</div>
          <div className="text-xl font-semibold text-amber-400">{maxAngle.toFixed(1)}°</div>
        </div>}
      </div>
      {(angle == null || movementPreview) && <p className="mt-2 text-center text-xs text-slate-300">
        {angle == null ? waitingMessage : 'Wrist preview includes twist.'}
      </p>}
    </div>
  );
};
