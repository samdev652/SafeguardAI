'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  LocationSearchResult,
  searchLocations,
  sendRegistrationOtp,
  subscribeToAlerts,
  verifyRegistrationOtp,
} from '@/lib/api';
import { RiskLevel } from '@/lib/types';

const RegisterWardMap = dynamic(() => import('@/components/RegisterWardMap'), { ssr: false });

type Step = 1 | 2 | 3;
type Channel = 'sms' | 'whatsapp' | 'push';

const stepLabels = {
  1: 'Location',
  2: 'Alert channels',
  3: 'Phone verification',
} as const;

const channelLabels: Record<Channel, string> = {
  sms: 'SMS',
  whatsapp: 'WhatsApp',
  push: 'Push notifications',
};

function phoneWithKenyaPrefix(input: string): string {
  const digits = input.replace(/\D/g, '');
  if (digits.startsWith('254')) return `+${digits.slice(0, 12)}`;
  if (digits.startsWith('0')) return `+254${digits.slice(1, 10)}`;
  return `+254${digits.slice(0, 9)}`;
}

function riskClass(level: RiskLevel): string {
  if (level === 'critical') return 'register-risk-critical';
  if (level === 'high') return 'register-risk-high';
  if (level === 'medium') return 'register-risk-medium';
  return 'register-risk-safe';
}

export default function RegisterPage() {
  const [step, setStep] = useState<Step>(1);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<LocationSearchResult[]>([]);
  const [selectedWard, setSelectedWard] = useState<LocationSearchResult | null>(null);

  const [channels, setChannels] = useState<Channel[]>(['sms']);
  const [phone, setPhone] = useState('+254');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpMessage, setOtpMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ ward: string; risk: RiskLevel } | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }

    const timeout = window.setTimeout(() => {
      searchLocations(query)
        .then(setResults)
        .catch(() => setResults([]));
    }, 220);

    return () => window.clearTimeout(timeout);
  }, [query]);

  const progress = useMemo(() => (step / 3) * 100, [step]);

  const selectedChannels = useMemo(
    () => ['sms', ...channels.filter((channel) => channel !== 'sms')] as Channel[],
    [channels]
  );

  const canContinueStep1 = Boolean(selectedWard);
  const canContinueStep2 = selectedChannels.length > 0;

  function toggleChannel(channel: Channel) {
    if (channel === 'sms') return;
    setChannels((prev) => (prev.includes(channel) ? prev.filter((value) => value !== channel) : [...prev, channel]));
  }

  async function sendOtp() {
    setBusy(true);
    setError(null);
    setOtpMessage(null);
    try {
      const normalized = phoneWithKenyaPrefix(phone);
      const response = await sendRegistrationOtp(normalized);
      setPhone(response.phone);
      setOtpSent(true);
      setOtpMessage('OTP sent. Enter the 4-digit code to complete registration.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send OTP');
    } finally {
      setBusy(false);
    }
  }

  async function verifyAndSubscribe() {
    if (!selectedWard) return;
    setBusy(true);
    setError(null);
    setOtpMessage(null);

    try {
      const normalized = phoneWithKenyaPrefix(phone);
      await verifyRegistrationOtp(normalized, otp);
      const response = await subscribeToAlerts({
        ward_id: selectedWard.id,
        phone: normalized,
        channels: selectedChannels,
      });
      setSuccess({ ward: response.ward_name, risk: response.risk_level });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not complete registration');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className='register-root'>
      <section className='register-shell'>
        {!success ? (
          <>
            <header className='register-head'>
              <Link href='/' className='register-back-home'>
                ← Back to live homepage
              </Link>
              <h1>Get protected in under 60 seconds</h1>
              <p>Choose your ward, select channels, verify your phone.</p>
            </header>

            <div className='register-progress'>
              <div className='register-progress-meta'>
                <span>{`Step ${step} / 3`}</span>
                <strong>{stepLabels[step]}</strong>
              </div>
              <div className='register-progress-track'>
                <motion.div className='register-progress-fill' animate={{ width: `${progress}%` }} />
              </div>
            </div>

            <AnimatePresence mode='wait'>
              <motion.div
                key={step}
                initial={{ x: 36, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -22, opacity: 0 }}
                transition={{ duration: 0.24 }}
              >
                {step === 1 ? (
                  <section className='register-step'>
                    <h2>Select your ward</h2>
                    <p>Start typing your ward name to find your location.</p>

                    <label htmlFor='ward-search' className='register-label'>
                      Ward search
                    </label>
                    <input
                      id='ward-search'
                      value={query}
                      onChange={(event) => {
                        setQuery(event.target.value);
                        setSelectedWard(null);
                      }}
                      placeholder='e.g. Westlands, Starehe, Parklands'
                      className='register-input'
                      autoComplete='off'
                    />

                    {results.length ? (
                      <div className='register-results'>
                        {results.map((ward) => (
                          <button
                            key={ward.id}
                            type='button'
                            onClick={() => {
                              setSelectedWard(ward);
                              setQuery(`${ward.ward_name}, ${ward.county_name}`);
                              setResults([]);
                            }}
                            className='register-result-item'
                          >
                            <strong>{ward.ward_name}</strong>
                            <span>{ward.county_name}</span>
                          </button>
                        ))}
                      </div>
                    ) : null}

                    {selectedWard ? (
                      <div className='register-map-wrap'>
                        <div className='register-map-meta'>
                          <strong>{selectedWard.ward_name}</strong>
                          <span>{selectedWard.county_name} County</span>
                        </div>
                        <div className='register-map-frame'>
                          <RegisterWardMap latitude={selectedWard.latitude} longitude={selectedWard.longitude} />
                        </div>
                      </div>
                    ) : null}

                    <div className='register-actions'>
                      <button
                        type='button'
                        className='register-primary'
                        onClick={() => setStep(2)}
                        disabled={!canContinueStep1}
                      >
                        Continue to channels
                      </button>
                    </div>
                  </section>
                ) : null}

                {step === 2 ? (
                  <section className='register-step'>
                    <h2>Choose alert channels</h2>
                    <p>SMS is mandatory to guarantee life-critical delivery.</p>

                    <div className='register-channel-grid'>
                      {(['sms', 'whatsapp', 'push'] as Channel[]).map((channel) => {
                        const selected = selectedChannels.includes(channel);
                        return (
                          <button
                            key={channel}
                            type='button'
                            onClick={() => toggleChannel(channel)}
                            className={`register-channel-card ${selected ? 'register-channel-active' : ''}`}
                            disabled={channel === 'sms'}
                          >
                            <div>
                              <strong>{channelLabels[channel]}</strong>
                              <span>{channel === 'sms' ? 'Always on' : selected ? 'Enabled' : 'Tap to enable'}</span>
                            </div>
                            <span className='register-toggle'>{selected ? 'ON' : 'OFF'}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className='register-preview'>
                      <h3>Message preview</h3>
                      {selectedChannels.map((channel) => (
                        <article key={channel} className='register-preview-card'>
                          <strong>{channelLabels[channel]}</strong>
                          <p>
                            ALERT: {selectedWard?.ward_name || 'Your ward'} flood risk upgraded to HIGH. Move to higher
                            ground immediately. Reply SOS for rescue.
                          </p>
                        </article>
                      ))}
                    </div>

                    <div className='register-actions register-actions-split'>
                      <button type='button' className='register-ghost' onClick={() => setStep(1)}>
                        Back
                      </button>
                      <button
                        type='button'
                        className='register-primary'
                        onClick={() => setStep(3)}
                        disabled={!canContinueStep2}
                      >
                        Continue to phone
                      </button>
                    </div>
                  </section>
                ) : null}

                {step === 3 ? (
                  <section className='register-step'>
                    <h2>Verify your phone</h2>
                    <p>We use your phone number as identity. No password required.</p>

                    <label htmlFor='phone' className='register-label'>
                      Phone number
                    </label>
                    <input
                      id='phone'
                      className='register-input'
                      value={phone}
                      onChange={(event) => setPhone(phoneWithKenyaPrefix(event.target.value))}
                      placeholder='+2547XXXXXXXX'
                    />

                    <div className='register-otp-row'>
                      <button type='button' className='register-secondary' onClick={sendOtp} disabled={busy}>
                        {busy ? 'Sending...' : otpSent ? 'Resend OTP' : 'Send OTP'}
                      </button>
                      <input
                        className='register-input register-otp-input'
                        inputMode='numeric'
                        pattern='[0-9]*'
                        maxLength={4}
                        value={otp}
                        onChange={(event) => setOtp(event.target.value.replace(/\D/g, '').slice(0, 4))}
                        placeholder='4-digit OTP'
                      />
                    </div>

                    {otpMessage ? <p className='register-help-success'>{otpMessage}</p> : null}
                    {error ? <p className='register-help-error'>{error}</p> : null}

                    <div className='register-actions register-actions-split'>
                      <button type='button' className='register-ghost' onClick={() => setStep(2)}>
                        Back
                      </button>
                      <button
                        type='button'
                        className='register-primary'
                        onClick={verifyAndSubscribe}
                        disabled={busy || otp.length !== 4}
                      >
                        {busy ? 'Verifying...' : 'Activate alerts'}
                      </button>
                    </div>
                  </section>
                ) : null}
              </motion.div>
            </AnimatePresence>
          </>
        ) : (
          <section className='register-success'>
            <motion.div
              className='register-success-check'
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <span>✓</span>
            </motion.div>
            <h2>You are now protected.</h2>
            <p>
              Alerts are active for <strong>{success.ward}</strong>. Current risk level is{' '}
              <span className={`register-risk-pill ${riskClass(success.risk)}`}>{success.risk.toUpperCase()}</span>
            </p>
            <div className='register-success-actions'>
              <Link href='/dashboard' className='register-primary'>
                View live dashboard
              </Link>
              <Link href='/download' className='register-secondary'>
                Download mobile app
              </Link>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
