import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { useAuthStore } from '../store/authStore';

export function RegisterPage() {
  const navigate = useNavigate();
  const register = useAuthStore((state) => state.register);
  const loading = useAuthStore((state) => state.loading);
  const storeError = useAuthStore((state) => state.error);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const onSubmit = async (event) => {
    event.preventDefault();

    try {
      await register({
        full_name: fullName,
        email,
        password,
      });
      navigate('/login', { replace: true });
    } catch {
      // Error state is handled in store.
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="font-code text-xs uppercase tracking-[0.1em] text-primary">IntervAI</p>
        <h1 className="mt-3 font-headline text-4xl font-bold">Create account</h1>
        <p className="mt-2 text-sm text-on-surface-variant">
          Enter your details to begin the technical assessment journey.
        </p>

        {storeError && (
          <div className="mt-5 rounded-md border border-error-container bg-error-container/15 px-3 py-2 text-sm text-error">
            {storeError}
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="mb-1 block text-sm text-on-surface-variant" htmlFor="name">
              Full Name
            </label>
            <Input
              id="name"
              type="text"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Ada Lovelace"
              required
            />
          </div>

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
              minLength={6}
              required
            />
          </div>

          <Button className="w-full" type="submit" disabled={loading}>
            {loading ? 'Creating account...' : 'Create account'}
          </Button>
        </form>

        <p className="mt-6 text-sm text-on-surface-variant">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
