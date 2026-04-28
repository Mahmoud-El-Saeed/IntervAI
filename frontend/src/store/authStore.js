import { create } from 'zustand';

import { loginUser, registerUser } from '../lib/api/authApi';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '../lib/storage';

function isAuthenticatedFromStorage() {
  return Boolean(getAccessToken() && getRefreshToken());
}

export const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: isAuthenticatedFromStorage(),
  loading: false,
  error: null,

  register: async (payload) => {
    set({ loading: true, error: null });
    try {
      const user = await registerUser(payload);
      set({ loading: false, user, error: null });
      return user;
    } catch (error) {
      set({ loading: false, error: error?.response?.data?.detail || 'Registration failed.' });
      throw error;
    }
  },

  login: async (credentials) => {
    set({ loading: true, error: null });
    try {
      const tokens = await loginUser(credentials);
      setTokens(tokens);
      set({ loading: false, isAuthenticated: true, error: null });
      return tokens;
    } catch (error) {
      set({ loading: false, error: error?.response?.data?.detail || 'Invalid credentials.' });
      throw error;
    }
  },

  hydrateAuth: () => {
    set({ isAuthenticated: isAuthenticatedFromStorage() });
  },

  logout: () => {
    clearTokens();
    set({ user: null, isAuthenticated: false, error: null });
  },
}));
