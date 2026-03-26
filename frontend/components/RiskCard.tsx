'use client';

import { useState } from 'react';
import { RiskAssessment } from '@/lib/types';

const emojiByRisk: Record<string, string> = {
  safe: '🟢',
  medium: '🟡',
  high: '🟠',
  critical: '🔴',
};

const colorByRisk: Record<string, string> = {
  safe: '#00D4AA',
  medium: '#F59E0B',
  high: '#f97316',
  critical: '#EF4444',
};

export default function RiskCard({ risk }: { risk: RiskAssessment }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article
      className={risk.risk_level === 'critical' ? 'risk-pulse' : ''}
      style={{
        background: 'rgba(10, 15, 30, 0.93)',
        border: `1px solid ${colorByRisk[risk.risk_level]}`,
        borderLeft: `4px solid ${colorByRisk[risk.risk_level]}`,
        borderRadius: 14,
        padding: 14,
        marginBottom: 10,
        width: 'min(92vw, 360px)',
        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <div>
          <div style={{ fontSize: 13, color: '#9DB0D1' }}>{risk.ward_name}</div>
          <div style={{ fontSize: 24, fontWeight: 800, lineHeight: 1.1 }}>
            {emojiByRisk[risk.risk_level]} {risk.risk_level.toUpperCase()}
          </div>
        </div>
        <time style={{ fontSize: 12, color: '#9DB0D1' }}>
          {new Date(risk.issued_at).toLocaleTimeString()}
        </time>
      </div>

      <div style={{ marginTop: 8, fontSize: 13, color: '#d9e3f8' }}>{risk.hazard_type.toUpperCase()}</div>

      <div style={{ display: 'flex', gap: 4, marginTop: 8, alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 3 }}>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: i <= (risk.data_quality_score || 1) ? colorByRisk[risk.risk_level] : 'transparent',
                border: `1px solid ${i <= (risk.data_quality_score || 1) ? colorByRisk[risk.risk_level] : '#334155'}`,
                boxShadow: i <= (risk.data_quality_score || 1) ? `0 0 8px ${colorByRisk[risk.risk_level]}44` : 'none',
              }}
            />
          ))}
        </div>
        <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 500, letterSpacing: '0.02em' }}>
          {risk.data_quality_score || 1}/4 SCIENTIFIC SOURCES VERIFIED
        </span>
      </div>

      <button
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        style={{
          marginTop: 10,
          width: '100%',
          border: '1px solid #1f2a44',
          borderRadius: 10,
          padding: '10px 12px',
          color: '#fff',
          background: 'rgba(18, 24, 42, 0.85)',
          textAlign: 'left',
          cursor: 'pointer',
        }}
      >
        What to do {expanded ? '▲' : '▼'}
      </button>
      {expanded ? <p style={{ marginTop: 8, fontSize: 13, lineHeight: 1.4 }}>{risk.guidance_en}</p> : null}
    </article>
  );
}
