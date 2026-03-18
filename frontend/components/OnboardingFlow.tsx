'use client';

import { useState } from 'react';
import Image from 'next/image';

interface OnboardingFlowProps {
  onComplete: (payload: { ward: string; channels: string[]; phone: string }) => void;
}

export default function OnboardingFlow({ onComplete }: OnboardingFlowProps) {
  const [step, setStep] = useState(1);
  const [ward, setWard] = useState('');
  const [channels, setChannels] = useState<string[]>(['sms']);
  const [phone, setPhone] = useState('');

  const toggleChannel = (value: string) => {
    setChannels((prev) => (prev.includes(value) ? prev.filter((c) => c !== value) : [...prev, value]));
  };

  return (
    <section
      style={{
        minHeight: '100dvh',
        display: 'grid',
        placeItems: 'center',
        padding: 20,
      }}
    >
      <div
        style={{
          width: 'min(95vw, 440px)',
          background: 'rgba(15, 23, 42, 0.92)',
          border: '1px solid #1f2a44',
          borderRadius: 18,
          padding: 20,
        }}
      >
        <div style={{ fontSize: 12, color: '#9DB0D1' }}>Step {step} of 3</div>
        <h1 style={{ marginTop: 8, marginBottom: 14, fontSize: 28 }}>Welcome to Safeguard AI</h1>

        {step === 1 ? (
          <div>
            <Image src='/illustrations/location.svg' alt='Location step illustration' width={120} height={120} />
            <p style={{ color: '#9DB0D1' }}>Enter your ward so we can localize warnings.</p>
            <input
              value={ward}
              onChange={(event) => setWard(event.target.value)}
              placeholder='e.g. Westlands'
              style={inputStyle}
            />
          </div>
        ) : null}

        {step === 2 ? (
          <div>
            <Image src='/illustrations/channels.svg' alt='Channels step illustration' width={120} height={120} />
            <p style={{ color: '#9DB0D1' }}>Choose your alert channels.</p>
            <div style={{ display: 'grid', gap: 10 }}>
              {['sms', 'whatsapp', 'push'].map((channel) => (
                <label key={channel} style={labelStyle}>
                  <input
                    type='checkbox'
                    checked={channels.includes(channel)}
                    onChange={() => toggleChannel(channel)}
                  />
                  <span style={{ textTransform: 'capitalize' }}>{channel}</span>
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div>
            <Image src='/illustrations/phone.svg' alt='Phone registration illustration' width={120} height={120} />
            <p style={{ color: '#9DB0D1' }}>Register your phone number for urgent alerts.</p>
            <input
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder='+2547XXXXXXXX'
              style={inputStyle}
            />
          </div>
        ) : null}

        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between' }}>
          <button
            onClick={() => setStep((value) => Math.max(1, value - 1))}
            disabled={step === 1}
            style={secondaryButton}
          >
            Back
          </button>
          {step < 3 ? (
            <button onClick={() => setStep((value) => value + 1)} style={primaryButton}>
              Continue
            </button>
          ) : (
            <button onClick={() => onComplete({ ward, channels, phone })} style={primaryButton}>
              Finish
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  marginTop: 8,
  width: '100%',
  borderRadius: 12,
  border: '1px solid #1f2a44',
  background: '#0b1221',
  color: '#fff',
  padding: '12px 14px',
  fontSize: 16,
};

const labelStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  borderRadius: 10,
  border: '1px solid #1f2a44',
  padding: '10px 12px',
};

const primaryButton: React.CSSProperties = {
  border: 0,
  borderRadius: 12,
  padding: '10px 16px',
  fontWeight: 700,
  color: '#041019',
  background: '#00D4AA',
  cursor: 'pointer',
};

const secondaryButton: React.CSSProperties = {
  border: '1px solid #1f2a44',
  borderRadius: 12,
  padding: '10px 16px',
  fontWeight: 600,
  color: '#fff',
  background: '#0b1221',
  cursor: 'pointer',
};
