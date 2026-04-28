import api from './client';

export async function getResumes() {
  const response = await api.get('/resume');
  return response.data;
}

export async function uploadResume(file) {
  const formData = new FormData();
  formData.set('upload_file', file);

  const response = await api.post('/resume/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}
