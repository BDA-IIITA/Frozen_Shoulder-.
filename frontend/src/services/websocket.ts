import { LiveSensorSample, DeviceStatus } from '../types';
import { backendOrigin } from './api';

type MessageHandler = (sample: LiveSensorSample) => void;
type StatusHandler = (status: DeviceStatus) => void;

class SensorWebSocketClient {
  private socket: WebSocket | null = null;
  private sampleHandlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();
  private isConnecting = false;
  private reconnectTimer: any = null;
  private pingInterval: any = null;

  connect() {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isConnecting = true;
    const wsUrl = `${backendOrigin.replace(/^http/, 'ws')}/ws/live`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnecting = false;
        // Start ping heartbeat
        this.pingInterval = setInterval(() => {
          if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type: 'PING', timestamp: Date.now() / 1000 }));
          }
        }, 15000);
      };

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'SENSOR_SAMPLE' && message.data) {
            this.sampleHandlers.forEach((handler) => handler(message.data));
          } else if (message.type === 'STATUS_UPDATE' && message.data) {
            this.statusHandlers.forEach((handler) => handler(message.data));
          }
        } catch {
          // ignore malformed frame
        }
      };

      this.socket.onclose = () => {
        this.isConnecting = false;
        clearInterval(this.pingInterval);
        // Attempt reconnect after 3 seconds
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = setTimeout(() => {
          this.connect();
        }, 3000);
      };

      this.socket.onerror = () => {
        this.isConnecting = false;
      };
    } catch {
      this.isConnecting = false;
    }
  }

  disconnect() {
    clearTimeout(this.reconnectTimer);
    clearInterval(this.pingInterval);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  onSample(handler: MessageHandler) {
    this.sampleHandlers.add(handler);
    return () => this.sampleHandlers.delete(handler);
  }

  onStatus(handler: StatusHandler) {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }
}

export const wsClient = new SensorWebSocketClient();
