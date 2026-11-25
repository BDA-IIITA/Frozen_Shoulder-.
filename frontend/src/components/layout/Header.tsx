import { Menu, Radio } from 'lucide-react';
import type { DeviceStatus } from '../../types';

interface HeaderProps {
  deviceStatus?: DeviceStatus | null;
  onOpenMobileSidebar: () => void;
  onNavigateToSettings: () => void;
}

export function Header({ deviceStatus, onOpenMobileSidebar, onNavigateToSettings }: HeaderProps) {
  const source = deviceStatus?.data_source_mode;
  const label = source === 'replay' ? 'Dataset Replay' : source === 'demo' ? 'Synthetic Demo' : source === 'live' ? 'Live ESP32' : 'Device settings';
  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onOpenMobileSidebar} aria-label="Open navigation" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden">
          <Menu className="h-5 w-5" />
        </button>
        <span className="text-sm font-semibold text-slate-800 lg:hidden">ShoulderSense</span>
      </div>
      <button onClick={onNavigateToSettings} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-slate-100 text-xs font-semibold text-slate-700">
        <Radio className="h-4 w-4 text-teal-700" />
        {label}{source === 'live' && (deviceStatus?.hardware_active ? ' · Receiving' : ' · Standby')}
      </button>
    </header>
  );
}
