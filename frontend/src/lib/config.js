export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000';

export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL?.trim() || 'ws://localhost:8000';

export const WS_RECONNECT_ATTEMPTS = Number(
  import.meta.env.VITE_WS_RECONNECT_ATTEMPTS || 5,
);

export const WS_RECONNECT_BASE_DELAY_MS = Number(
  import.meta.env.VITE_WS_RECONNECT_BASE_DELAY_MS || 1000,
);
