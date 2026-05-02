import { create } from 'zustand';
import i18n from '../i18n';

const STORAGE_KEY = 'intervai_language';

function getInitialLanguage() {
  if (typeof window === 'undefined') return 'en';
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'ar' || stored === 'en') return stored;
  return 'en';
}

export const useLanguageStore = create((set) => ({
  currentLanguage: getInitialLanguage(),

  setLanguage: (lang) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, lang);
      i18n.changeLanguage(lang);
    }
    set({ currentLanguage: lang });
  },

  hydrateLanguage: () => {
    const stored = getInitialLanguage();
    i18n.changeLanguage(stored);
    set({ currentLanguage: stored });
  },
}));