import Link from 'next/link';
import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import type { RiskAssessment } from '@/lib/types';
import ThreatShareButton from '@/components/ThreatShareButton';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function fetchThreatById(id: number): Promise<RiskAssessment | null> {
  const response = await fetch(`${API_BASE_URL}/api/risk/current/`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    return null;
  }

  const threats = (await response.json()) as RiskAssessment[];
  return threats.find((threat) => threat.id === id) || null;
}

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const threatId = Number(params.id);
  if (!Number.isFinite(threatId)) {
    return {
      title: 'Threat not found | Safeguard AI',
      description: 'Requested threat could not be found.',
    };
  }

  const threat = await fetchThreatById(threatId);
  if (!threat) {
    return {
      title: 'Threat not found | Safeguard AI',
      description: 'Requested threat could not be found.',
    };
  }

  const location = `${threat.ward_name}${threat.county_name ? `, ${threat.county_name}` : ''}`;
  const title = `${threat.hazard_type} risk in ${location} (${threat.risk_level.toUpperCase()}) | Safeguard AI`;
  const description = `AI-predicted ${threat.hazard_type} threat in ${location} with ${Math.round(
    threat.risk_score
  )}% probability. Current risk level: ${threat.risk_level.toUpperCase()}.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: 'article',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  };
}

export default async function ThreatDetailPage({ params }: { params: { id: string } }) {
  const threatId = Number(params.id);
  if (!Number.isFinite(threatId)) {
    notFound();
  }

  const threat = await fetchThreatById(threatId);
  if (!threat) {
    notFound();
  }

  return (
    <main className='public-root' style={{ padding: '88px 16px 40px' }}>
      <section className='threat-detail-shell'>
        <p className='threat-detail-kicker'>Public Threat Link</p>
        <h1>
          {threat.hazard_type} in {threat.ward_name}
        </h1>
        <p className='threat-detail-meta'>
          {threat.county_name ? `${threat.county_name} County · ` : ''}
          Risk: <strong>{threat.risk_level.toUpperCase()}</strong> · Probability {Math.round(threat.risk_score)}%
        </p>

        <article className='threat-detail-card'>
          <h2>AI Summary</h2>
          <p>{threat.summary}</p>
          <h3>English guidance</h3>
          <p>{threat.guidance_en}</p>
          <h3>Swahili guidance</h3>
          <p>{threat.guidance_sw}</p>
        </article>

        <div className='threat-detail-actions'>
          <Link href='/threats' className='download-link'>
            Back to all threats
          </Link>
          <Link href='/register' className='download-link'>
            Get alerts on phone
          </Link>
          <ThreatShareButton threatId={threat.id} />
        </div>
      </section>
    </main>
  );
}
