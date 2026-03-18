'use client';

import { useState } from 'react';

interface ThreatShareButtonProps {
  threatId: number;
}

export default function ThreatShareButton({ threatId }: ThreatShareButtonProps) {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  async function onCopy() {
    const path = `/threats/${threatId}`;
    const fullUrl = `${window.location.origin}${path}`;

    try {
      if (typeof navigator.share === 'function') {
        await navigator.share({
          title: 'Safeguard AI threat alert',
          text: 'Live public threat alert from Safeguard AI',
          url: fullUrl,
        });
        setStatus('copied');
      } else {
        await navigator.clipboard.writeText(fullUrl);
        setStatus('copied');
      }
    } catch {
      // If native share is canceled or unavailable, fallback to clipboard copy.
      try {
        await navigator.clipboard.writeText(fullUrl);
        setStatus('copied');
      } catch {
        setStatus('failed');
      }
    }

    window.setTimeout(() => setStatus('idle'), 1800);
  }

  return (
    <button type='button' className='download-link' onClick={onCopy}>
      Share this threat {status === 'copied' ? '(Copied)' : status === 'failed' ? '(Copy failed)' : ''}
    </button>
  );
}
