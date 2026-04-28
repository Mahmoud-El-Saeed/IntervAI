import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="auth-page">
      <div className="auth-card text-center">
        <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">IntervAI</p>
        <h1 className="mt-4 font-headline text-4xl font-bold">Page not found</h1>
        <p className="mt-2 text-sm text-on-surface-variant">The route you requested does not exist.</p>
        <Link className="mt-6 inline-block text-primary hover:underline" to="/dashboard">
          Return to dashboard
        </Link>
      </div>
    </div>
  );
}
