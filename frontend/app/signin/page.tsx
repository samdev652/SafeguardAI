'use client';

import { FormEvent, Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { signIn, useSession } from 'next-auth/react';
import { sendRegistrationOtp } from '@/lib/api';

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
      const result = await signIn('credentials', {
        phone: normalizeKenyaPhone(phone),
        otp,
        redirect: false,
        callbackUrl,
      });

      if (result?.error || !result?.ok) {
        setError('Invalid phone OTP. Please try again.');
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
          Securely access your dashboard with your registered phone number.
        </p>

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

        {error ? <p style={{ color: '#EF4444' }}>{error}</p> : null}

        <button
          type='submit'
          disabled={busy || otp.length !== 4}
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
          {busy ? 'Signing in...' : 'Sign In with OTP'}
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
