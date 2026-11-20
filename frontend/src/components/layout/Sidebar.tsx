import React from 'react';
import {
  LayoutDashboard,
  Activity,
  BookOpen,
  History,
  TrendingUp,
  FileText,
  Cpu,
  ChevronRight,
  ShieldCheck
} from 'lucide-react';
import { NavItemKey } from '../../types';

interface SidebarProps {
  currentTab: NavItemKey;
  onSelectTab: (tab: NavItemKey) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  isOpenMobile,
  onCloseMobile,
}) => {
  const navItems = [
    { key: 'overview', label: 'Overview', icon: LayoutDashboard },
    { key: 'monitoring', label: 'Live Monitoring', icon: Activity, badge: 'Live' },
    { key: 'exercises', label: 'Exercise Library', icon: BookOpen },
    { key: 'sessions', label: 'Rehabilitation Sessions', icon: History },
    { key: 'analytics', label: 'Progress Analytics', icon: TrendingUp },
    { key: 'reports', label: 'Reports', icon: FileText },
    { key: 'settings', label: 'Device Settings', icon: Cpu },
  ];

  const handleNavClick = (key: NavItemKey) => {
    onSelectTab(key);
    onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:static top-0 left-0 z-50 h-screen w-64 bg-white border-r border-slate-200 flex flex-col transition-transform duration-300 ease-in-out ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand / Logo */}
        <div className="h-16 px-6 flex items-center border-b border-slate-100 space-x-3">
          <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center text-white shadow-sm shadow-teal-500/20">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="font-bold text-slate-900 tracking-tight text-base flex items-center">
              ShoulderSense
            </div>
            <div className="text-[10px] text-teal-700 font-medium tracking-wide uppercase">
              Rehab & Kinematics
            </div>
          </div>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.key;
            return (
              <button
                key={item.key}
                onClick={() => handleNavClick(item.key as NavItemKey)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-50 text-teal-900 font-semibold border-l-4 border-teal-600'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? 'text-teal-700' : 'text-slate-400 group-hover:text-slate-600'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] bg-teal-100 text-teal-800 font-bold px-1.5 py-0.5 rounded uppercase">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* System & Disclaimer Notice */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/70 m-3 rounded-lg">
          <div className="flex items-start space-x-2 text-slate-500 text-xs">
            <ShieldCheck className="w-4 h-4 text-teal-600 mt-0.5 flex-shrink-0" />
            <div className="text-[11px] leading-relaxed text-slate-600">
              <span className="font-semibold text-slate-700">Academic Project:</span> Real-time IMU movement monitoring. Not a medical diagnostic device.
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
