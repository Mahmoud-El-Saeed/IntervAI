import { create } from 'zustand';

export const useInterviewStore = create((set) => ({
  selectedResumeId: null,
  currentInterviewId: null,
  session: null,

  setSelectedResumeId: (resumeId) => set({ selectedResumeId: resumeId }),

  setCurrentInterviewId: (interviewId) =>
    set({
      currentInterviewId: interviewId,
    }),

  setSession: (sessionPayload) =>
    set({
      session: sessionPayload,
    }),

  clearSession: () =>
    set({
      currentInterviewId: null,
      session: null,
    }),
}));
