import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { OverviewPage } from './pages/OverviewPage';
import { LiveMonitoringPage } from './pages/LiveMonitoringPage';
import { ExerciseLibraryPage } from './pages/ExerciseLibraryPage';
import { SessionsPage } from './pages/SessionsPage';
import { ProgressAnalyticsPage } from './pages/ProgressAnalyticsPage';
import { ReportsPage } from './pages/ReportsPage';
import { DeviceSettingsPage } from './pages/DeviceSettingsPage';
import { NavItemKey, DeviceStatus } from './types';
import { api } from './services/api';
import { wsClient } from './services/websocket';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavItemKey>('overview');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus | null>(null);

  // Poll / listen to device telemetry status
  useEffect(() => {
    wsClient.connect();

    const unsubStatus = wsClient.onStatus((status) => {
      setDeviceStatus(status);
    });

    // Also poll every 5s for fallback
    const poll = async () => {
      try {
        const sum = await api.getDashboardSummary(1);
        setDeviceStatus(sum.device_status);
      } catch {
        // backend might be starting
      }
    };
    poll();
    const interval = setInterval(poll, 5000);

    return () => {
      unsubStatus();
      clearInterval(interval);
    };
  }, []);

  const renderContent = () => {
    switch (currentTab) {
      case 'overview':
        return <OverviewPage onNavigate={(tab) => setCurrentTab(tab)} />;
      case 'monitoring':
        return <LiveMonitoringPage />;
      case 'exercises':
        return <ExerciseLibraryPage onNavigateToMonitoring={() => setCurrentTab('monitoring')} />;
      case 'sessions':
        return <SessionsPage />;
      case 'analytics':
        return <ProgressAnalyticsPage />;
      case 'reports':
        return <ReportsPage />;
      case 'settings':
        return <DeviceSettingsPage />;
      default:
        return <OverviewPage onNavigate={(tab) => setCurrentTab(tab)} />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header
          deviceStatus={deviceStatus}
          onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          onNavigateToSettings={() => setCurrentTab('settings')}
        />

        <main className="flex-1 overflow-y-auto">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
