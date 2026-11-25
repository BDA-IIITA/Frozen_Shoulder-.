import React, { useEffect, useState } from 'react';
import {
  Cpu,
  Wifi,
  WifiOff,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sliders,
  Code2,
  ShieldCheck,
  Server,
  Zap,
  Check,
  Copy
} from 'lucide-react';
import { DeviceStatus, DataSourceMode } from '../types';
import { api } from '../services/api';

export const DeviceSettingsPage: React.FC = () => {
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus | null>(null);
  const [mode, setMode] = useState<Exclude<DataSourceMode, "replay">>('demo');
  const [ipAddress, setIpAddress] = useState('192.168.1.105');
  const [copied, setCopied] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibMessage, setCalibMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const summary = await api.getDashboardSummary(1);
      setDeviceStatus(summary.device_status);
      const reportedMode = summary.device_status.data_source_mode;
      if (reportedMode !== "replay") setMode(reportedMode);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSwitchMode = async (newMode: Exclude<DataSourceMode, "replay">) => {
    setMode(newMode);
    try {
      await api.connectDevice('esp32-shoulder-01', newMode, ipAddress);
      fetchStatus();
    } catch (err: any) {
      console.warn("Device mode set warning:", err);
      fetchStatus();
    }
  };

  const handleCalibrate = async () => {
    try {
      setIsCalibrating(true);
      const res = await api.calibrateNeutral('esp32-shoulder-01');
      setCalibMessage(res.message);
      setTimeout(() => setCalibMessage(null), 5000);
    } catch (err: any) {
      alert(`Calibration failed: ${err.message}`);
    } finally {
      setIsCalibrating(false);
    }
  };

  const jsonPayloadExample = `{
  "timestamp": ${Math.floor(Date.now() / 1000)}.0,
  "device_id": "esp32-shoulder-01",
  "source": "live",
  "sensors": {
    "chest": {
      "quaternion": { "x": 0.000, "y": 0.000, "z": 0.000, "w": 1.000 },
      "calibration_status": 3
    },
    "upper_arm": {
      "quaternion": { "x": 0.000, "y": 0.422, "z": 0.000, "w": 0.906 },
      "calibration_status": 3
    }
  }
}`;

  const handleCopyPayload = () => {
    navigator.clipboard.writeText(jsonPayloadExample);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Device Settings</h1>
      </div>

      {/* Mode Switch Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h3 className="font-semibold text-slate-900">Data source</h3>

        <div className="flex items-center space-x-2 bg-slate-100 p-1 rounded-lg">
          <button
            onClick={() => handleSwitchMode('demo')}
            className={`px-4 py-2 text-xs font-bold rounded-md transition-all ${
              mode === 'demo'
                ? 'bg-white text-teal-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Demo Mode (Simulated)
          </button>
          <button
            onClick={() => handleSwitchMode('live')}
            className={`px-4 py-2 text-xs font-bold rounded-md transition-all ${
              mode === 'live'
                ? 'bg-white text-blue-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Live ESP32 Wearable
          </button>
        </div>
      </div>

      {/* Diagnostics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Device ID</span>
          <div className="font-mono font-bold text-slate-900 text-base mt-1">
            {deviceStatus?.device_id || 'esp32-shoulder-01'}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">ESP32 DevKit V1</span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Connection Status</span>
          <div className="flex items-center space-x-1.5 mt-1">
            <span
              className={`w-2 h-2 rounded-full ${
                deviceStatus?.hardware_active ? 'bg-teal-500 animate-pulse' : 'bg-slate-400'
              }`}
            />
            <span className="font-bold text-slate-900 text-base">
              {deviceStatus?.hardware_active ? 'Recent ESP32 signal' : 'No recent ESP32 signal'}
            </span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">
            {deviceStatus?.data_freshness_sec != null
              ? `Data age: ${deviceStatus?.data_freshness_sec}s`
              : 'No live stream'}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Packets Received</span>
          <div className="font-mono font-bold text-teal-700 text-base mt-1">
            {deviceStatus?.packets_received ?? 0}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">
            Invalid / Malformed: {deviceStatus?.packets_invalid ?? 0}
          </span>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Detected IMUs</span>
          <div className="font-bold text-slate-900 text-sm mt-1">
            {deviceStatus?.sensors_detected.length ? deviceStatus.sensors_detected.join(' + ') : 'None'}
          </div>
          <span className="text-[11px] text-teal-700 font-medium mt-1 block">
            BNO086 (Torso + Upper Arm)
          </span>
        </div>
      </div>

      {/* Neutral Baseline Calibration Workflow */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-base font-bold text-slate-900">Neutral calibration</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
              Rest the arm at the side, then capture the starting position.
            </p>
          </div>
          <button
            onClick={handleCalibrate}
            disabled={isCalibrating}
            className="inline-flex items-center space-x-1.5 bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow-xs transition-colors flex-shrink-0"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isCalibrating ? 'animate-spin' : ''}`} />
            <span>{isCalibrating ? 'Calibrating...' : 'Capture Neutral Baseline'}</span>
          </button>
        </div>

        {calibMessage && (
          <div className="bg-teal-50 border border-teal-200 text-teal-900 p-3 rounded-lg text-xs flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-teal-600 flex-shrink-0" />
            <span>{calibMessage}</span>
          </div>
        )}

        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-[11px] text-slate-500">
          * Note: Sensor calibration normalizes sensor mounting offsets relative to the torso frame. It does not replace physical anatomical alignment.
        </div>
      </div>

      {/* Hardware Integration Guide & Payload Schema */}
      <details className="rounded-xl border border-slate-200 bg-white p-4 sm:p-6">
        <summary className="cursor-pointer font-semibold">ESP32 setup details</summary>
        <div className="mt-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
            <div className="font-bold text-slate-800">Local Network Ingestion Endpoints:</div>
            <div className="space-y-1 font-mono text-[11px]">
              <div>• HTTP POST: <span className="text-teal-700 font-semibold">http://&lt;LAPTOP_IP&gt;:8000/api/sensor/ingest</span></div>
              <div>• WebSocket: <span className="text-blue-700 font-semibold">ws://&lt;LAPTOP_IP&gt;:8000/ws/live</span></div>
            </div>
            <div className="pt-2 text-slate-500 text-[11px] leading-relaxed">
              Both the ESP32 and the computer hosting this web application must be connected to the same Wi-Fi network (or ESP32 Access Point mode).
            </div>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
            <div className="font-bold text-slate-800">Hardware Sensor Bus Wiring:</div>
            <div className="text-slate-600 space-y-1 text-[11px]">
              <div>• Sensor 1 (Torso / Chest): BNO086 I2C Address <strong>0x4A</strong></div>
              <div>• Sensor 2 (Upper Arm): BNO086 I2C Address <strong>0x4B</strong> (DI pin pulled HIGH)</div>
              <div>• Optional Sensor 3 (Forearm): Supported in schema for future expansion</div>
            </div>
          </div>
        </div>

        {/* JSON Schema Box */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700">Expected Sensor Packet JSON Schema</span>
            <button
              onClick={handleCopyPayload}
              className="inline-flex items-center space-x-1 text-slate-500 hover:text-slate-800 text-xs font-medium"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy JSON'}</span>
            </button>
          </div>

          <pre className="bg-slate-900 text-teal-400 p-4 rounded-xl text-xs font-mono overflow-x-auto border border-slate-800">
            {jsonPayloadExample}
          </pre>
        </div>
        </div>
      </details>
    </div>
  );
};
