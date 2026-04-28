import api from './client';

export async function registerUser(payload) {
  const response = await api.post('/auth/register', payload);
  return response.data;
}

export async function loginUser({ email, password }) {
  const formData = new URLSearchParams();
  formData.set('username', email);
  formData.set('password', password);

  const response = await api.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  return response.data;
}

export async function refreshSession(refreshToken) {
  const response = await api.post('/auth/refresh', {
    refresh_token: refreshToken,
  });

  return response.data;
}
