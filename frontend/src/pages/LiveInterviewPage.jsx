import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';
import { PlugZap, Send, Wifi, WifiOff } from 'lucide-react';

import { Button } from '../components/ui/Button';
import { InterviewSocketClient } from '../lib/ws/interviewSocket';
import { getAccessToken } from '../lib/storage';
import { useInterviewStore } from '../store/interviewStore';

export function LiveInterviewPage() {
  const { t } = useTranslation();
  const { interviewId } = useParams();
  const navigate = useNavigate();
  const chatContainerRef = useRef(null);
  const socketRef = useRef(null);

  const setSession = useInterviewStore((state) => state.setSession);
  const session = useInterviewStore((state) => state.session);
  const setCurrentInterviewId = useInterviewStore((state) => state.setCurrentInterviewId);

  const [answer, setAnswer] = useState('');
  const [connectionState, setConnectionState] = useState('connecting');
  const [error, setError] = useState('');
  const [activeHint, setActiveHint] = useState('');
  const hintTimeoutRef = useRef(null);

  useEffect(() => {
    if (!interviewId) return;
    setCurrentInterviewId(interviewId);

    const token = getAccessToken();
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }

    const socket = new InterviewSocketClient({
      interviewId,
      token,
      onConnectionState: (state) => setConnectionState(state),
      onEvent: (event) => {
        if (event.type === 'error') {
          setError(event.detail || 'WebSocket error');
          return;
        }

        if (event.type === 'pong') {
          return;
        }

        if (event.data) {
          setSession(event.data);
        }

        if (event.type === 'hint_provided') {
          const hintText = event.data?.hint || event.data?.last_hint || '';
          if (hintText) {
            setActiveHint(hintText);
            if (hintTimeoutRef.current) {
              window.clearTimeout(hintTimeoutRef.current);
            }
            hintTimeoutRef.current = window.setTimeout(() => {
              setActiveHint('');
            }, 12000);
          }
          return;
        }

        if (event.type === 'session_completed') {
          navigate(`/analysis/${interviewId}`, { replace: true });
        }
      },
    });

    socket.connect();
    socketRef.current = socket;

    return () => {
      socket.close();
    };
  }, [interviewId, navigate, setCurrentInterviewId, setSession]);

  useEffect(() => {
    if (!chatContainerRef.current) return;
    chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
  }, [session?.chat_history]);

  useEffect(() => {
    return () => {
      if (hintTimeoutRef.current) {
        window.clearTimeout(hintTimeoutRef.current);
      }
    };
  }, []);

  const onSend = () => {
    const text = answer.trim();
    if (!text) return;

    const result = socketRef.current?.sendAnswer(text);

    // result now has: { success, queued, readyState, state }
    if (!result?.success) {
      if (result?.queued) {
        // Message was queued; socket is temporarily connecting or closing
        setError(`Message queued (socket ${result.state}). Will send when ready.`);
        setAnswer(''); // Clear input so user knows it's pending
        // Auto-clear error after 2 seconds
        window.setTimeout(() => setError(''), 2000);
      } else {
        // Socket is fully closed; provide diagnostic info
        const diagnostic = result ? `Socket is ${result.state} (readyState: ${result.readyState})` : 'Socket connection lost';
        setError(`Connection is not ready. ${diagnostic}. Reconnecting...`);
      }
      return;
    }

    setAnswer('');
    setError('');
  };

  const connectionLabel = useMemo(() => {
    if (connectionState === 'connected') return t('interview.connected');
    if (connectionState === 'reconnecting') return t('interview.reconnecting');
    if (connectionState === 'failed') return t('interview.disconnected');
    if (connectionState === 'error') return t('interview.connectionError');
    return t('interview.connecting');
  }, [connectionState, t]);

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <section className="glass-card rounded-lg p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">{t('interview.liveInterview')}</p>
            <h2 className="mt-2 font-headline text-3xl font-bold">{t('interview.session')} {String(interviewId).slice(0, 8)}</h2>
          </div>
          <div className="inline-flex items-center gap-2 rounded-xl border border-outline-variant px-3 py-1 text-xs uppercase tracking-[0.08em] text-on-surface-variant">
            {connectionState === 'connected' ? <Wifi size={14} /> : <WifiOff size={14} />}
            {connectionLabel}
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
            {error}
          </div>
        )}

        {activeHint && (
          <div className="mb-3 rounded-md border border-primary/40 bg-primary-container/20 px-3 py-2 text-sm text-on-surface">
            <div className="text-xs uppercase tracking-[0.08em] text-primary">{t('interview.hint')}</div>
            <div className="mt-1">{activeHint}</div>
          </div>
        )}

        <div
          ref={chatContainerRef}
          className="h-[55vh] space-y-3 overflow-y-auto rounded-md border border-outline-variant/60 bg-surface-container-low p-4"
        >
          {(session?.chat_history || []).map((item, index) => (
            <div
              key={`${item.role}-${index}`}
              className={item.role === 'human' ? 'ml-auto rtl:mr-auto max-w-[80%]' : 'mr-auto rtl:ml-auto max-w-[80%]'}
            >
              {item.role === 'ai_hint' ? (
                <div className="rounded-md border border-primary/40 bg-primary-container/20 px-3 py-2 text-sm text-on-surface">
                  <div className="text-xs uppercase tracking-[0.08em] text-primary">{t('interview.hint')}</div>
                  <div className="mt-1">{item.content}</div>
                </div>
              ) : item.role === 'ai_feedback' ? (
                <div className="rounded-md border border-outline-variant/70 bg-surface-container-high px-3 py-2 text-sm text-on-surface">
                  <div className="text-xs uppercase tracking-[0.08em] text-on-surface-variant">{t('interview.evaluation')}</div>
                  <div className="mt-1">{item.content}</div>
                </div>
              ) : (
                <div
                  className={
                    item.role === 'human'
                      ? 'rounded-md bg-primary-container px-3 py-2 text-sm text-on-primary-container'
                      : 'rounded-md border border-outline-variant/70 bg-surface-container px-3 py-2 text-sm text-on-surface'
                  }
                >
                  {item.content}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="mt-4 flex items-end gap-3">
          <textarea
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            placeholder={t('interview.typeYourAnswer')}
            className="min-h-20 flex-1 rounded-md border border-outline-variant bg-surface-container-low px-3 py-2 text-sm text-on-surface focus:border-primary-container focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <Button onClick={onSend} className="h-10">
            <Send size={16} className="mr-2 rtl:ml-2 rtl:rotate-180" />
            {t('interview.send')}
          </Button>
        </div>
      </section>

      <aside className="space-y-4">
        <section className="glass-card rounded-lg p-4">
          <h3 className="font-headline text-lg">{t('interview.currentQuestion')}</h3>
          <p className="mt-2 text-sm text-on-surface-variant">
            {session?.current_question || t('interview.waitingForQuestion')}
          </p>
        </section>

        <section className="glass-card rounded-lg p-4">
          <h3 className="font-headline text-lg">{t('interview.sessionState')}</h3>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant">{t('interview.score')}</dt>
              <dd>{Math.round(session?.score?.total ?? 0)} /100</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant">{t('interview.questionsAsked')}</dt>
              <dd>{session?.score?.asked ?? 0}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant">{t('interview.difficulty')}</dt>
              <dd>{session?.difficulty_level || 'Medium'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-on-surface-variant">{t('interview.topic')}</dt>
              <dd>{session?.current_topic || 'General'}</dd>
            </div>
          </dl>
        </section>

        <section className="glass-card rounded-lg p-4">
          <Button
            variant="secondary"
            className="w-full"
            onClick={() => socketRef.current?.requestState()}
          >
            <PlugZap size={16} className="mr-2 rtl:ml-2" />
            {t('interview.resyncState')}
          </Button>
        </section>
      </aside>
    </div>
  );
}
