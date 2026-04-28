import api from './client';

export async function getInterviewHistory() {
  const response = await api.get('/interview');
  return response.data;
}

export async function createInterviewSession(payload) {
  const response = await api.post('/interview', payload);
  return response.data;
}

export async function getInterviewDetails(interviewId) {
  const response = await api.get(`/interview/${interviewId}`);
  return response.data;
}

export async function triggerInterviewAnalysis(interviewId) {
  const response = await api.post(`/interview/${interviewId}/analysis`);
  return response.data;
}
