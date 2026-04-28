const ACCESS_TOKEN_KEY = 'intervai_access_token';
const REFRESH_TOKEN_KEY = 'intervai_refresh_token';

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(tokens) {
  if (!tokens) return;
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token || '');
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token || '');
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export const storageKeys = {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
};
