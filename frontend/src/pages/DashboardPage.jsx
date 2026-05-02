import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Calendar, Clock3, Plus, AlertCircle, X } from 'lucide-react';

import {
  getInterviewHistory,
} from '../lib/api/interviewApi';
import { initiateInterviewSession } from '../lib/api/orchestrator';
import { formatDateTime } from '../lib/utils';
import { StatusBadge } from '../components/ui/StatusBadge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { SelectResumeModal } from '../components/resume/SelectResumeModal';
import { useInterviewStore } from '../store/interviewStore';
import { useLanguageStore } from '../store/languageStore';

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setCurrentInterviewId = useInterviewStore((state) => state.setCurrentInterviewId);
  const setSelectedResumeId = useInterviewStore((state) => state.setSelectedResumeId);

  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedResumeId, setLocalSelectedResumeId] = useState('');
  const [creating, setCreating] = useState(false);
  const [creatingStage, setCreatingStage] = useState(null);
  const [errorModalOpen, setErrorModalOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [jobTitle, setJobTitle] = useState('Senior Backend Engineer');
  const [jobDescription, setJobDescription] = useState(
    'Design scalable backend APIs, optimize PostgreSQL queries, and drive architecture decisions.',
  );
  const globalLanguage = useLanguageStore((state) => state.currentLanguage);
  const [preferredLanguage, setPreferredLanguage] = useState(globalLanguage);

  useEffect(() => {
    let active = true;

    const loadHistory = async () => {
      try {
        const data = await getInterviewHistory();
        if (!active) return;
        setHistory(data);
        setError('');
      } catch (err) {
        if (!active) return;
        setError(err?.response?.data?.detail || 'Failed to fetch interviews.');
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadHistory();

    return () => {
      active = false;
    };
  }, []);

  const historyStats = useMemo(() => {
    const total = history.length;
    const completed = history.filter((item) => item.status === 'COMPLETED').length;
    const inProgress = history.filter((item) => item.status === 'INTERVIEW_IN_PROGRESS').length;

    return { total, completed, inProgress };
  }, [history]);

  const handleResumeConfirm = (resumeId) => {
    setSelectedResumeId(resumeId);
    setLocalSelectedResumeId(resumeId);
    setModalOpen(false);
  };

  const onCreateInterview = async () => {
    if (!selectedResumeId) {
      setModalOpen(true);
      return;
    }

    setCreating(true);
    setCreatingStage(null);
    setError('');

    try {
      const result = await initiateInterviewSession(
        selectedResumeId,
        jobTitle,
        jobDescription,
        preferredLanguage,
        (progress) => {
          if (progress.stage === 'creating') {
            setCreatingStage('creating');
          } else if (progress.stage === 'analyzing') {
            setCreatingStage('analyzing');
          } else if (progress.stage === 'polling') {
            setCreatingStage('polling');
          } else if (progress.stage === 'error') {
            setErrorMessage(progress.message);
            setErrorModalOpen(true);
          }
        }
      );

      setCurrentInterviewId(String(result.interview_id));
      setCreatingStage(null);
      navigate(`/interview/${result.interview_id}`);
    } catch (err) {
      setErrorMessage(err?.response?.data?.detail || err?.message || 'Unable to create interview session');
      setErrorModalOpen(true);
    } finally {
      setCreating(false);
      setCreatingStage(null);
    }
  };

  const handleRetryCreate = async () => {
    setErrorModalOpen(false);
    setErrorMessage('');
    await onCreateInterview();
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">{t('dashboard.interviewIntelligence')}</p>
          <h2 className="mt-2 font-headline text-4xl font-bold">{t('dashboard.interviewHistory')}</h2>
          <p className="mt-2 text-sm text-on-surface-variant">
            {t('dashboard.reviewPerformance')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => setModalOpen(true)}>
            {t('dashboard.selectResume')}
          </Button>
          <Button onClick={onCreateInterview} disabled={creating}>
            <Plus size={16} className="mr-2 rtl:ml-2" />
            {creatingStage === 'creating' && t('dashboard.creatingInterview')}
            {creatingStage === 'analyzing' && t('dashboard.analyzingResume')}
            {creatingStage === 'polling' && t('dashboard.startingInterview')}
            {!creatingStage && (creating ? t('dashboard.initiating') : t('dashboard.initiateNewSession'))}
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="glass-card rounded-lg p-4">
          <p className="font-code text-xs uppercase tracking-[0.1em] text-on-surface-variant">{t('dashboard.totalSessions')}</p>
          <p className="mt-2 font-headline text-3xl font-bold">{historyStats.total}</p>
        </article>
        <article className="glass-card rounded-lg p-4">
          <p className="font-code text-xs uppercase tracking-[0.1em] text-on-surface-variant">{t('dashboard.completed')}</p>
          <p className="mt-2 font-headline text-3xl font-bold text-emerald-300">{historyStats.completed}</p>
        </article>
        <article className="glass-card rounded-lg p-4">
          <p className="font-code text-xs uppercase tracking-[0.1em] text-on-surface-variant">{t('dashboard.inProgress')}</p>
          <p className="mt-2 font-headline text-3xl font-bold text-cyan-300">{historyStats.inProgress}</p>
        </article>
      </section>

      <section className="glass-card rounded-lg p-5">
        <h3 className="font-headline text-xl">{t('dashboard.sessionConfiguration')}</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm text-on-surface-variant">{t('dashboard.jobTitle')}</label>
            <Input value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-sm text-on-surface-variant">{t('dashboard.preferredLanguage')}</label>
            <select
              value={preferredLanguage}
              onChange={(event) => setPreferredLanguage(event.target.value)}
              className="w-full rounded-md border border-outline-variant bg-surface-container-low px-3 py-2 text-sm text-on-surface focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="en">{t('dashboard.english')}</option>
              <option value="ar">{t('dashboard.arabic')}</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm text-on-surface-variant">{t('dashboard.selectedResume')}</label>
            <Input
              readOnly
              value={selectedResumeId ? `${selectedResumeId.slice(0, 8)}...` : t('dashboard.noResumeSelected')}
            />
          </div>
        </div>

        <div className="mt-4">
          <label className="mb-1 block text-sm text-on-surface-variant">{t('dashboard.jobDescription')}</label>
          <textarea
            className="min-h-24 w-full rounded-md border border-outline-variant bg-surface-container-low px-3 py-2 text-sm text-on-surface focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary/30"
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
          />
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      <section className="space-y-3">
        {loading ? (
          <div className="glass-card rounded-lg p-4 text-sm text-on-surface-variant">{t('dashboard.loadingHistory')}</div>
        ) : history.length === 0 ? (
          <div className="glass-card rounded-lg p-4 text-sm text-on-surface-variant">
            {t('dashboard.noInterviews')}
          </div>
        ) : (
          history.map((item) => (
            <article
              key={item.id}
              className="glass-card flex flex-wrap items-center justify-between gap-4 rounded-lg p-4"
            >
              <div>
                <h3 className="font-headline text-xl">{item.job_title}</h3>
                <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-on-surface-variant">
                  <span className="inline-flex items-center gap-1">
                    <Calendar size={14} /> {formatDateTime(item.created_at)}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Clock3 size={14} /> Session #{String(item.id).slice(0, 8)}
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <StatusBadge status={item.status} />
                {item.status === 'COMPLETED' ? (
                  <Button variant="secondary" onClick={() => navigate(`/analysis/${item.id}`)}>
                    View Report
                  </Button>
                ) : (
                  <Button onClick={() => navigate(`/interview/${item.id}`)}>Continue</Button>
                )}
              </div>
            </article>
          ))
        )}
      </section>

      {errorModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="glass-card max-w-md rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertCircle size={24} className="text-error" />
                <h3 className="font-headline text-lg font-bold">{t('dashboard.sessionSetupFailed')}</h3>
              </div>
              <button onClick={() => {
                setErrorModalOpen(false);
                setErrorMessage('');
              }} className="text-on-surface-variant hover:text-on-surface">
                <X size={20} />
              </button>
            </div>
            <p className="mt-4 text-sm text-on-surface-variant">{errorMessage}</p>
            <div className="mt-6 flex gap-3">
              <Button variant="secondary" onClick={() => {
                setErrorModalOpen(false);
                setErrorMessage('');
              }}>
                {t('dashboard.cancel')}
              </Button>
              <Button onClick={handleRetryCreate}>
                {t('dashboard.retry')}
              </Button>
            </div>
          </div>
        </div>
      )}

      <SelectResumeModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleResumeConfirm}
      />
    </div>
  );
}
