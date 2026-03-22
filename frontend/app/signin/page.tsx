'use client';

import { FormEvent, Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { signIn, useSession } from 'next-auth/react';
import { sendRegistrationOtp } from '@/lib/api';

type SignInMode = 'email' | 'phone';

function normalizeKenyaPhone(input: string): string {
  const digits = input.replace(/\D/g, '');
  if (digits.startsWith('254')) return `+${digits.slice(0, 12)}`;
  if (digits.startsWith('0')) return `+254${digits.slice(1, 10)}`;
  return `+254${digits.slice(0, 9)}`;
}

function SignInPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status } = useSession();
  const [mode, setMode] = useState<SignInMode>('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('+254');
  const [otp, setOtp] = useState('');
  const [sendingOtp, setSendingOtp] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
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
      const result =
        mode === 'phone'
          ? await signIn('credentials', {
              phone: normalizeKenyaPhone(phone),
              otp,
              redirect: false,
              callbackUrl,
            })
          : await signIn('credentials', {
              email,
              password,
              redirect: false,
              callbackUrl,
            });

      if (result?.error || !result?.ok) {
        setError(mode === 'phone' ? 'Invalid phone OTP. Please try again.' : 'Invalid credentials. Please try again.');
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

  async function onSendOtp() {
    setSendingOtp(true);
    setError(null);
    try {
      await sendRegistrationOtp(normalizeKenyaPhone(phone), 'sms');
      setOtpSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send OTP');
    } finally {
      setSendingOtp(false);
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
        <p style={{ color: '#9DB0D1', marginTop: 0 }}>
          Sign in with email/password or with your registered phone OTP.
        </p>

        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <button
            type='button'
            onClick={() => setMode('email')}
            style={{
              ...switchButtonStyle,
              background: mode === 'email' ? '#00D4AA' : '#0b1221',
              color: mode === 'email' ? '#041019' : '#9DB0D1',
            }}
          >
            Email
          </button>
          <button
            type='button'
            onClick={() => setMode('phone')}
            style={{
              ...switchButtonStyle,
              background: mode === 'phone' ? '#00D4AA' : '#0b1221',
              color: mode === 'phone' ? '#041019' : '#9DB0D1',
            }}
          >
            Phone OTP
          </button>
        </div>

        {mode === 'email' ? (
          <>
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
          </>
        ) : (
          <>
            <label htmlFor='phone'>Phone number</label>
            <input
              id='phone'
              type='text'
              value={phone}
              onChange={(event) => setPhone(normalizeKenyaPhone(event.target.value))}
              required
              style={inputStyle}
            />

            <button
              type='button'
              disabled={sendingOtp}
              onClick={onSendOtp}
              style={{
                width: '100%',
                borderRadius: 10,
                border: '1px solid #1f2a44',
                background: '#16314e',
                color: '#fff',
                padding: '10px 12px',
                marginBottom: 12,
                cursor: 'pointer',
              }}
            >
              {sendingOtp ? 'Sending OTP...' : otpSent ? 'Resend OTP' : 'Send OTP'}
            </button>

            <label htmlFor='otp'>OTP code</label>
            <input
              id='otp'
              type='text'
              value={otp}
              onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 4))}
              required
              style={inputStyle}
            />
          </>
        )}

        {error ? <p style={{ color: '#EF4444' }}>{error}</p> : null}

        <button
          type='submit'
          disabled={busy || (mode === 'phone' && otp.length !== 4)}
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
          {busy ? 'Signing in...' : mode === 'phone' ? 'Sign In with OTP' : 'Sign In'}
        </button>

        <p style={{ color: '#9DB0D1', marginBottom: 0, marginTop: 14 }}>
          Need alert subscription only?{' '}
          <a href='/register' style={{ color: '#00D4AA', fontWeight: 700 }}>
            Register with phone OTP
          </a>
        </p>
      </form>
    </main>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInPageContent />
    </Suspense>
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

const switchButtonStyle: React.CSSProperties = {
  flex: 1,
  borderRadius: 10,
  border: '1px solid #1f2a44',
  padding: '10px 12px',
  fontWeight: 700,
  cursor: 'pointer',
};
