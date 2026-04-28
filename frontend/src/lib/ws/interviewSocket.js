import {
  WS_BASE_URL,
  WS_RECONNECT_ATTEMPTS,
  WS_RECONNECT_BASE_DELAY_MS,
} from '../config';
import { getAccessToken } from '../storage';

export class InterviewSocketClient {
  constructor({ interviewId, token, onEvent, onConnectionState }) {
    this.interviewId = interviewId;
    this.token = token;
    this.onEvent = onEvent;
    this.onConnectionState = onConnectionState;

    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = WS_RECONNECT_ATTEMPTS;
    this.reconnectBaseDelayMs = WS_RECONNECT_BASE_DELAY_MS;
    this.pingInterval = null;
    this.closedByUser = false;
    this.messageQueue = [];
    this.isProcessingQueue = false;
  }

  connect() {
    this.closedByUser = false;
    this.token = getAccessToken() || this.token;
    const url = `${WS_BASE_URL}/ws/interview/${this.interviewId}?token=${encodeURIComponent(this.token)}`;
    this.socket = new WebSocket(url);
    this.onConnectionState?.('connecting');

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.onConnectionState?.('connected');
      this.startPing();
      this.processMessageQueue();
    };

    this.socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        this.onEvent?.(payload);
      } catch {
        this.onEvent?.({ type: 'error', detail: 'Malformed websocket event.' });
      }
    };

    this.socket.onclose = () => {
      this.stopPing();
      if (this.closedByUser) {
        this.onConnectionState?.('disconnected');
        return;
      }

      this.onConnectionState?.('reconnecting');
      this.scheduleReconnect();
    };

    this.socket.onerror = () => {
      this.onConnectionState?.('error');
    };
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.onConnectionState?.('failed');
      return;
    }

    const delay = this.reconnectBaseDelayMs * 2 ** this.reconnectAttempts;
    this.reconnectAttempts += 1;

    window.setTimeout(() => {
      if (!this.closedByUser) {
        this.connect();
      }
    }, delay);
  }

  sendAnswer(answer) {
    return this.send({ type: 'answer', answer });
  }

  requestState() {
    return this.send({ type: 'state' });
  }

  ping() {
    return this.send({ type: 'ping' });
  }

  getReadyState() {
    if (!this.socket) {
      return { readyState: -1, state: 'NO_SOCKET', label: 'Socket instance is null' };
    }
    const states = {
      0: { state: 'CONNECTING', label: 'Socket is connecting' },
      1: { state: 'OPEN', label: 'Socket is open and ready' },
      2: { state: 'CLOSING', label: 'Socket is closing' },
      3: { state: 'CLOSED', label: 'Socket is closed' },
    };
    const info = states[this.socket.readyState] || { state: 'UNKNOWN', label: 'Unknown state' };
    return { readyState: this.socket.readyState, ...info };
  }

  processMessageQueue() {
    if (this.isProcessingQueue || this.messageQueue.length === 0) {
      return;
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    this.isProcessingQueue = true;
    try {
      while (this.messageQueue.length > 0) {
        const payload = this.messageQueue.shift();
        this.socket.send(JSON.stringify(payload));
      }
    } finally {
      this.isProcessingQueue = false;
    }
  }

  send(payload) {
    // Pre-flight check: report exact socket state
    if (!this.socket) {
      console.warn('[InterviewSocket] Send failed: socket is null');
      this.messageQueue.push(payload);
      return { success: false, queued: true, readyState: -1, state: 'NO_SOCKET' };
    }

    const readyState = this.socket.readyState;
    if (readyState !== WebSocket.OPEN) {
      const stateNames = {
        0: 'CONNECTING',
        1: 'OPEN',
        2: 'CLOSING',
        3: 'CLOSED',
      };
      const stateName = stateNames[readyState] || 'UNKNOWN';
      console.warn(`[InterviewSocket] Send failed: socket is in ${stateName} state (${readyState})`);

      // Queue the message if the socket is temporarily connecting or closing
      if (readyState === 0 || readyState === 2) {
        this.messageQueue.push(payload);
        return { success: false, queued: true, readyState, state: stateName };
      }

      // Don't queue if the socket is fully closed; let the caller handle reconnection
      return { success: false, queued: false, readyState, state: stateName };
    }

    this.socket.send(JSON.stringify(payload));
    return { success: true, queued: false, readyState: 1, state: 'OPEN' };
  }

  startPing() {
    this.stopPing();
    this.pingInterval = window.setInterval(() => this.ping(), 15000);
  }

  stopPing() {
    if (!this.pingInterval) return;
    window.clearInterval(this.pingInterval);
    this.pingInterval = null;
  }

  close() {
    this.closedByUser = true;
    this.stopPing();
    this.messageQueue = [];
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
