import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { useAuthStore } from '../store/authStore';

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  const storeError = useAuthStore((state) => state.error);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const onSubmit = async (event) => {
    event.preventDefault();

    try {
      await login({ email, password });
      const redirectPath = location.state?.from?.pathname || '/dashboard';
      navigate(redirectPath, { replace: true });
    } catch {
      // Error state is handled in store.
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">IntervAI</p>
        <h1 className="mt-3 font-headline text-4xl font-bold">Welcome back</h1>
        <p className="mt-2 text-sm text-on-surface-variant">Enter your credentials to access your dashboard.</p>

        {storeError && (
          <div className="mt-5 rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
            {storeError}
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="mb-1 block text-sm text-on-surface-variant" htmlFor="email">
              Work Email
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@company.com"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-on-surface-variant" htmlFor="password">
              Password
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <Button className="w-full" type="submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-on-surface-variant">
          New to IntervAI?{' '}
          <Link to="/register" className="font-semibold text-primary hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
