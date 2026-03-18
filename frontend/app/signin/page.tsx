'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { signIn, useSession } from 'next-auth/react';

export default function SignInPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === 'authenticated') {
      router.replace('/dashboard');
    }
  }, [status, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const callbackUrl = searchParams.get('callbackUrl') || '/dashboard';

    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
        callbackUrl,
      });

      if (result?.error || !result?.ok) {
        setError('Invalid credentials. Please try again.');
        return;
      }

      router.push(callbackUrl);
      router.refresh();
    } catch {
      setError('Sign in failed. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', padding: 20 }}>
      <form
        onSubmit={onSubmit}
        style={{
          width: 'min(92vw, 420px)',
          background: 'rgba(15, 23, 42, 0.92)',
          border: '1px solid #1f2a44',
          borderRadius: 16,
          padding: 20,
        }}
      >
        <h1 style={{ marginTop: 0 }}>Sign in to Safeguard AI</h1>
        <p style={{ color: '#9DB0D1', marginTop: 0 }}>Use your registered account to enable SOS dispatch and private alerts.</p>

        <label htmlFor='email'>Email</label>
        <input
          id='email'
          type='email'
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          style={inputStyle}
        />

        <label htmlFor='password'>Password</label>
        <input
          id='password'
          type='password'
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          style={inputStyle}
        />

        {error ? <p style={{ color: '#EF4444' }}>{error}</p> : null}

        <button
          type='submit'
          disabled={busy}
          style={{
            width: '100%',
            marginTop: 12,
            border: 0,
            borderRadius: 12,
            padding: '12px 14px',
            fontWeight: 700,
            background: '#00D4AA',
            color: '#041019',
            cursor: 'pointer',
          }}
        >
          {busy ? 'Signing in...' : 'Sign In'}
        </button>

        <p style={{ color: '#9DB0D1', marginBottom: 0, marginTop: 14 }}>
          New to Safeguard AI?{' '}
          <a href='/register' style={{ color: '#00D4AA', fontWeight: 700 }}>
            Create account
          </a>
        </p>
      </form>
    </main>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  borderRadius: 10,
  border: '1px solid #1f2a44',
  background: '#0b1221',
  color: '#fff',
  padding: '10px 12px',
  marginTop: 6,
  marginBottom: 12,
};
