import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

import { getInterviewDetails, triggerInterviewAnalysis } from '../lib/api/interviewApi';
import { useInterviewStore } from '../store/interviewStore';

function normalizeFinalReport(details, sessionReport) {
  if (sessionReport) {
    return {
      debrief: sessionReport.debrief || '',
      recommendation: sessionReport.recommendation || '',
      strengths: sessionReport.strengths || [],
      focus_areas: sessionReport.focus_areas || [],
      average_score: sessionReport.average_score || 0,
    };
  }

  const technical = details?.analysis?.technical_evaluation || {};
  const interviewReport = technical.interview_report || {};
  const soft = details?.analysis?.soft_skills_evaluation || {};
  const roadmap = details?.analysis?.learning_roadmap || {};

  return {
    debrief: interviewReport.debrief || details?.analysis?.final_verdict || '',
    recommendation: details?.analysis?.final_verdict || '',
    strengths: soft.strengths || [],
    focus_areas: roadmap.focus_areas || [],
    average_score: interviewReport.average_score || details?.analysis?.overall_score || 0,
  };
}

export function AnalysisReportPage() {
  const { interviewId } = useParams();
  const session = useInterviewStore((state) => state.session);
  const analysisTriggeredRef = useRef(false);

  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!interviewId) return;

    let active = true;
    let pollId = null;
    const queuedInterviewId = window.sessionStorage.getItem('intervai_analysis_queued');

    const load = async () => {
      setLoading(true);
      setError('');

      try {
        const response = await getInterviewDetails(interviewId);
        if (!active) return;
        setDetails(response);

        if (
          response.status === 'COMPLETED' &&
          !response.analysis &&
          !analysisTriggeredRef.current &&
          queuedInterviewId !== String(interviewId)
        ) {
          analysisTriggeredRef.current = true;
          await triggerInterviewAnalysis(interviewId);
        }
      } catch (err) {
        if (active) {
          setError(err?.response?.data?.detail || 'Failed to load report.');
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();

    pollId = window.setInterval(async () => {
      if (!active) return;

      try {
        const response = await getInterviewDetails(interviewId);
        if (!active) return;

        setDetails(response);

        if (response.status === 'ANALYSIS_COMPLETED' || response.status === 'FAILED_ANALYSIS') {
          window.sessionStorage.removeItem('intervai_analysis_queued');
          window.clearInterval(pollId);
          pollId = null;
        }
      } catch {
        // Keep polling; the backend analysis job may still be writing results.
      }
    }, 2500);

    return () => {
      active = false;
      if (pollId) {
        window.clearInterval(pollId);
      }
    };
  }, [interviewId]);

  const report = useMemo(
    () => normalizeFinalReport(details, session?.final_report),
    [details, session?.final_report],
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">Completed</p>
          <h2 className="mt-2 font-headline text-4xl font-bold">Interview Analysis</h2>
          <p className="mt-2 text-sm text-on-surface-variant">Session {String(interviewId).slice(0, 8)}</p>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {loading ? (
        <div className="glass-card rounded-lg p-4 text-sm text-on-surface-variant">Loading report...</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr]">
          <section className="glass-card flex flex-col items-center justify-center rounded-lg p-6">
            <h3 className="self-start font-headline text-2xl">Final Assessment</h3>
            <div className="mt-8 grid h-44 w-44 place-items-center rounded-full border-4 border-primary">
              <div className="text-center">
                <p className="font-headline text-5xl font-bold">{Math.round(report.average_score || 0)}</p>
                <p className="text-sm text-on-surface-variant">/100</p>
              </div>
            </div>
            <p className="mt-6 text-sm text-on-surface-variant">{report.recommendation || 'Awaiting recommendation.'}</p>
          </section>

          <section className="glass-card rounded-lg p-6">
            <h3 className="font-headline text-2xl">Strengths</h3>
            <ul className="mt-4 space-y-3 text-sm text-on-surface-variant">
              {(report.strengths || []).length > 0 ? (
                report.strengths.map((item, index) => (
                  <li key={`${item}-${index}`} className="rounded-md border border-outline-variant/70 p-3">
                    {item}
                  </li>
                ))
              ) : (
                <li className="rounded-md border border-outline-variant/70 p-3">No strengths extracted yet.</li>
              )}
            </ul>
          </section>

          <section className="glass-card rounded-lg p-6">
            <h3 className="font-headline text-2xl">Improvement Areas</h3>
            <ul className="mt-4 space-y-3 text-sm text-on-surface-variant">
              {(report.focus_areas || []).length > 0 ? (
                report.focus_areas.map((item, index) => (
                  <li key={`${item}-${index}`} className="rounded-md border border-outline-variant/70 p-3">
                    {item}
                  </li>
                ))
              ) : (
                <li className="rounded-md border border-outline-variant/70 p-3">No focus areas extracted yet.</li>
              )}
            </ul>
          </section>
        </div>
      )}

      <section className="glass-card rounded-lg p-6">
        <h3 className="font-headline text-2xl">Debrief</h3>
        <p className="mt-3 text-sm leading-7 text-on-surface-variant">
          {report.debrief || 'No debrief available for this session.'}
        </p>
      </section>
    </div>
  );
}
