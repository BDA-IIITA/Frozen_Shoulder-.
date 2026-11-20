import React from 'react';
import { Menu, User, Cpu, Wifi, WifiOff } from 'lucide-react';
import { DeviceStatus } from '../../types';

interface HeaderProps {
  deviceStatus?: DeviceStatus | null;
  onOpenMobileSidebar: () => void;
  onNavigateToSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  deviceStatus,
  onOpenMobileSidebar,
  onNavigateToSettings,
}) => {
  const isDemo = deviceStatus?.data_source_mode === 'demo';
  const isActive = deviceStatus?.is_active ?? false;

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Mobile hamburger & current title */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onOpenMobileSidebar}
          className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden sm:block">
          <span className="text-xs text-slate-400 font-medium">Rehabilitation Protocol</span>
          <div className="text-sm font-semibold text-slate-800">
            Adhesive Capsulitis (Frozen Shoulder) Kinematics
          </div>
        </div>
      </div>

      {/* Right: Patient Profile & Hardware Connection Status */}
      <div className="flex items-center space-x-3 sm:space-x-4">
        {/* Patient Profile Tag */}
        <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-full text-xs text-slate-700">
          <div className="w-5 h-5 rounded-full bg-slate-200 flex items-center justify-center text-slate-600">
            <User className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="font-semibold text-slate-900">Participant P-101</span>
            <span className="hidden md:inline text-slate-500 ml-1.5">(Right Shoulder)</span>
          </div>
        </div>

        {/* Device Status Badge */}
        <button
          onClick={onNavigateToSettings}
          className="flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium transition-all hover:shadow-xs hover:border-slate-300"
          style={{
            backgroundColor: isDemo ? '#f0fdfa' : isActive ? '#f0fdf4' : '#fef2f2',
            borderColor: isDemo ? '#99f6e4' : isActive ? '#bbf7d0' : '#fecaca',
            color: isDemo ? '#0f766e' : isActive ? '#15803d' : '#b91c1c',
          }}
          title="Click to manage device connection in Settings"
        >
          <Cpu className="w-3.5 h-3.5" />
          <span className="font-bold">
            {isDemo ? 'DEMO MODE' : 'LIVE ESP32'}
          </span>
          <span className="flex h-2 w-2 relative">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isActive ? (isDemo ? 'bg-teal-400' : 'bg-emerald-400') : 'bg-rose-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isActive ? (isDemo ? 'bg-teal-500' : 'bg-emerald-500') : 'bg-rose-500'
              }`}
            />
          </span>
          <span className="hidden sm:inline text-[11px] font-semibold">
            {isDemo
              ? (isActive ? 'Simulating' : 'Standby')
              : (isActive ? 'Connected' : 'Disconnected')}
          </span>
        </button>
      </div>
    </header>
  );
};
