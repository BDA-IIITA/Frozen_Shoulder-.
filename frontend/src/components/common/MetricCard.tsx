import React from 'react';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  change?: number | null;
  changeLabel?: string;
  icon: LucideIcon;
  badge?: string;
  variant?: 'teal' | 'blue' | 'amber' | 'slate';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  subtitle,
  change,
  changeLabel,
  icon: Icon,
  badge,
  variant = 'teal',
}) => {
  const iconColors = {
    teal: 'bg-teal-50 text-teal-600 border-teal-100',
    blue: 'bg-blue-50 text-blue-600 border-blue-100',
    amber: 'bg-amber-50 text-amber-600 border-amber-100',
    slate: 'bg-slate-50 text-slate-600 border-slate-100',
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-slate-600">
          {title}
        </span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center border ${iconColors[variant]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="flex items-baseline space-x-1.5">
        <span className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
          {value}
        </span>
        {unit && <span className="text-sm font-medium text-slate-500">{unit}</span>}
        {badge && (
          <span className="ml-2 text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium">
            {badge}
          </span>
        )}
      </div>

      {(change != null || changeLabel || subtitle) && <div className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-600">
        {change !== undefined && change !== null && (
          <span
            className={`font-semibold ${
              change > 0 ? 'text-teal-600' : change < 0 ? 'text-amber-600' : 'text-slate-500'
            }`}
          >
            {change > 0 ? `+${change}` : change}
            {unit}
          </span>
        )}
        {changeLabel && <span>{changeLabel}</span>}
        {subtitle && !changeLabel && <span>{subtitle}</span>}
      </div>}
    </div>
  );
};
