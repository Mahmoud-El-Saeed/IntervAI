import api from './client';

const POLL_INTERVAL_MS = 1000;
const MAX_POLLS = 60;
export async function initiateInterviewSession(
  resumeId,
  jobTitle,
  jobDescription,
  preferredLanguage = 'en',
  onProgress = () => {}
) {
  try {
    onProgress({ stage: 'creating', message: 'Creating interview session...' });

    const createResponse = await api.post('/interview', {
      resume_id: resumeId,
      job_title: jobTitle,
      job_description: jobDescription,
      preferred_language: preferredLanguage,
    });

    const interviewId = createResponse.data.interview_id;

    onProgress({ stage: 'analyzing', message: 'Starting resume analysis...' });

    await api.post(`/interview/${interviewId}/analysis`);

    onProgress({ stage: 'polling', message: 'Waiting for analysis to complete...' });

    let pollCount = 0;
    let analysisReady = false;

    while (pollCount < MAX_POLLS && !analysisReady) {
      const statusResponse = await api.get(`/interview/${interviewId}/status`);
      const { ready, status } = statusResponse.data;

      if (ready) {
        analysisReady = true;
        onProgress({
          stage: 'success',
          message: 'Interview session ready!',
          interviewId,
          status,
        });
        return {
          interview_id: interviewId,
          success: true,
          status,
        };
      }

      if (status === 'FAILED_ANALYSIS') {
        throw new Error('Resume analysis failed. Please try again.');
      }

      pollCount++;
      if (pollCount < MAX_POLLS) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
    }

    if (!analysisReady) {
      throw new Error('Analysis timeout. Please try again.');
    }

    return {
      interview_id: interviewId,
      success: true,
    };
  } catch (error) {
    const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to initiate interview session';
    onProgress({
      stage: 'error',
      message: errorMessage,
      error,
    });
    throw error;
  }
}
