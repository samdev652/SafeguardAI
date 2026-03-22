'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSession } from 'next-auth/react';
import { fetchCurrentRisks, fetchNearestRescueUnits } from '@/lib/api';
import { RescueUnit, RiskAssessment, RiskLevel } from '@/lib/types';

const RiskMap = dynamic(() => import('@/components/RiskMap'), { ssr: false });

type HazardFilter = 'all' | 'flood' | 'landslide' | 'drought' | 'earthquake';
type SortMode = 'severity' | 'recent' | 'county';

const severityRank: Record<RiskLevel, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  safe: 1,
};

const hazardMeta: Record<string, { dont: string; icon: string }> = {
  flood: { dont: 'Do not cross flooded roads or bridges.', icon: '🌊' },
  landslide: { dont: 'Do not stand near steep, water-soaked slopes.', icon: '⛰️' },
  drought: { dont: 'Do not wait to ration water until supplies are exhausted.', icon: '☀️' },
  earthquake: { dont: 'Do not use elevators during tremors.', icon: '🫨' },
};

function getHazardType(input: string): HazardFilter {
  const normalized = input.trim().toLowerCase();
  if (normalized.includes('flood')) return 'flood';
  if (normalized.includes('landslide')) return 'landslide';
  if (normalized.includes('drought')) return 'drought';
  if (normalized.includes('earthquake')) return 'earthquake';
  return 'all';
}

function riskBadgeClass(level: RiskLevel): string {
  if (level === 'critical') return 'badge-critical';
  if (level === 'high') return 'badge-high';
  if (level === 'medium') return 'badge-medium';
  return 'badge-safe';
}

function formatAgoFromDate(iso: string): string {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function probabilityWidth(score: number): string {
  const bounded = Math.max(0, Math.min(100, Math.round(score)));
  return `${bounded}%`;
}

export default function ThreatsPage() {
  const { status } = useSession();
  const [loading, setLoading] = useState(true);
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [hazardFilter, setHazardFilter] = useState<HazardFilter>('all');
  const [countyFilter, setCountyFilter] = useState('all');
  const [sortMode, setSortMode] = useState<SortMode>('severity');
  const [expandedRiskId, setExpandedRiskId] = useState<number | null>(null);
  const [unitsByRiskId, setUnitsByRiskId] = useState<Record<number, RescueUnit[]>>({});
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number>(Date.now());
  const [nowTick, setNowTick] = useState<number>(Date.now());
  const [shareMessageById, setShareMessageById] = useState<Record<number, string>>({});
  const [newUntilById, setNewUntilById] = useState<Record<number, number>>({});
  const seenIdsRef = useRef<Set<number>>(new Set());

  const refreshThreats = useCallback(async () => {
    const payload = await fetchCurrentRisks();
    const now = Date.now();
    const nextNewUntil: Record<number, number> = {};
    const seen = seenIdsRef.current;

    for (const risk of payload) {
      if (!seen.has(risk.id)) {
        nextNewUntil[risk.id] = now + 30000;
      }
      seen.add(risk.id);
    }

    setRisks(payload);
    if (Object.keys(nextNewUntil).length) {
      setNewUntilById((prev) => ({ ...prev, ...nextNewUntil }));
    }
    setLastUpdatedAt(now);
    setLoading(false);
  }, []);

  useEffect(() => {
    refreshThreats().catch(() => {
      setRisks([]);
      setLoading(false);
    });

    const pollInterval = window.setInterval(() => {
      refreshThreats().catch(() => undefined);
    }, 60000);

    const tickInterval = window.setInterval(() => {
      setNowTick(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(pollInterval);
      window.clearInterval(tickInterval);
    };
  }, [refreshThreats]);

  const counties = useMemo(() => {
    return Array.from(new Set(risks.map((risk) => risk.county_name).filter(Boolean) as string[])).sort();
  }, [risks]);

  const filteredAndSorted = useMemo(() => {
    const filtered = risks.filter((risk) => {
      const hazard = getHazardType(risk.hazard_type);
      const hazardMatch = hazardFilter === 'all' || hazard === hazardFilter;
      const countyMatch = countyFilter === 'all' || (risk.county_name || 'Unknown') === countyFilter;
      return hazardMatch && countyMatch;
    });

    return filtered.sort((a, b) => {
      if (sortMode === 'recent') {
        return new Date(b.issued_at).getTime() - new Date(a.issued_at).getTime();
      }
      if (sortMode === 'county') {
        const byCounty = (a.county_name || '').localeCompare(b.county_name || '');
        if (byCounty !== 0) return byCounty;
      }
      const bySeverity = severityRank[b.risk_level] - severityRank[a.risk_level];
      if (bySeverity !== 0) return bySeverity;
      return new Date(b.issued_at).getTime() - new Date(a.issued_at).getTime();
    });
  }, [risks, hazardFilter, countyFilter, sortMode]);

  const mapRisks = filteredAndSorted.length ? filteredAndSorted : risks;

  const lastUpdatedSeconds = Math.max(0, Math.floor((nowTick - lastUpdatedAt) / 1000));

  const refreshNearestUnits = useCallback(async (risk: RiskAssessment) => {
    try {
      const units = await fetchNearestRescueUnits(risk.latitude, risk.longitude);
      setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: units.slice(0, 3) }));
    } catch {
      setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: [] }));
    }
  }, []);

  async function ensureNearestUnits(risk: RiskAssessment) {
    if (unitsByRiskId[risk.id]) return;
    await refreshNearestUnits(risk);
  }

  useEffect(() => {
    if (!expandedRiskId) return;
    const risk = risks.find((item) => item.id === expandedRiskId);
    if (!risk) return;

    refreshNearestUnits(risk).catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshNearestUnits(risk).catch(() => undefined);
    }, 20000);

    return () => window.clearInterval(interval);
  }, [expandedRiskId, refreshNearestUnits, risks]);

  async function copyShareLink(riskId: number) {
    const path = `/threats/${riskId}`;
    const absoluteUrl = typeof window !== 'undefined' ? `${window.location.origin}${path}` : path;
    try {
      await navigator.clipboard.writeText(absoluteUrl);
      setShareMessageById((prev) => ({ ...prev, [riskId]: 'Copied' }));
    } catch {
      setShareMessageById((prev) => ({ ...prev, [riskId]: 'Copy failed' }));
    }
    window.setTimeout(() => {
      setShareMessageById((prev) => ({ ...prev, [riskId]: '' }));
    }, 1800);
  }

  return (
    <main className='dashboard-root'>
      <header className='top-nav'>
        <div className='top-nav-logo'>
          <span className='top-nav-logo-mark'>SG</span>
          <span>Safeguard AI</span>
        </div>
        <div className='top-nav-live'>
          <span className='live-dot' />
          <span>Public Live Feed</span>
          <span className='top-nav-live-count'>- {risks.length} threats tracked</span>
        </div>
        <div className='top-nav-actions'>
          <Link href='/' className='signout-button'>Back home</Link>
          <Link href={status === 'authenticated' ? '/dashboard#alerts' : '/register'} className='sos-nav-button'>
            {status === 'authenticated' ? 'My alerts' : 'Get alerts'}
          </Link>
        </div>
      </header>

      <section className='dashboard-split'>
        <div className='map-panel'>
          <RiskMap risks={mapRisks} />
          <div className='map-legend'>
            <h4>Risk Legend</h4>
            <ul>
              <li>
                <span className='legend-dot legend-safe' /> Low
              </li>
              <li>
                <span className='legend-dot legend-medium' /> Medium
              </li>
              <li>
                <span className='legend-dot legend-high' /> High
              </li>
              <li>
                <span className='legend-dot legend-critical' /> Critical
              </li>
            </ul>
          </div>
        </div>

        <aside className='feed-panel'>
          <div className='feed-head'>
            <h2>All Public Threats</h2>
            <p>{loading ? 'Syncing live intelligence...' : `Last updated ${lastUpdatedSeconds}s ago`}</p>
          </div>

          <div className='threats-filter-bar'>
            <div className='filter-row'>
              {(['all', 'flood', 'landslide', 'drought', 'earthquake'] as HazardFilter[]).map((filter) => (
                <button
                  key={filter}
                  type='button'
                  className={`filter-pill ${hazardFilter === filter ? 'filter-pill-active' : ''}`}
                  onClick={() => setHazardFilter(filter)}
                >
                  {filter === 'all'
                    ? 'All'
                    : filter === 'flood'
                      ? 'Floods'
                      : filter === 'landslide'
                        ? 'Landslides'
                        : filter === 'drought'
                          ? 'Droughts'
                          : 'Earthquakes'}
                </button>
              ))}
            </div>
            <div className='threats-select-row'>
              <input
                list='county-options'
                className='threats-select'
                placeholder='Filter by county'
                value={countyFilter === 'all' ? '' : countyFilter}
                onChange={(event) => {
                  const value = event.target.value.trim();
                  setCountyFilter(value || 'all');
                }}
              />
              <datalist id='county-options'>
                {counties.map((county) => (
                  <option key={county} value={county} />
                ))}
              </datalist>
              <select
                className='threats-select'
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as SortMode)}
              >
                <option value='severity'>Sort: Severity</option>
                <option value='recent'>Sort: Most recent</option>
                <option value='county'>Sort: County</option>
              </select>
              <button type='button' className='register-ghost' onClick={() => setCountyFilter('all')}>
                Clear county
              </button>
            </div>
          </div>

          <div className='feed-list'>
            {filteredAndSorted.map((risk) => {
              const hazard = getHazardType(risk.hazard_type);
              const isExpanded = expandedRiskId === risk.id;
              const isNew = (newUntilById[risk.id] || 0) > nowTick;
              const nearest = unitsByRiskId[risk.id] || [];

              return (
                <article key={risk.id} className={`feed-card ${isNew ? 'feed-card-new' : ''}`}>
                  <div className='feed-card-title'>
                    <div>
                      <h3>
                        <span>{hazardMeta[hazard]?.icon || '⚠️'}</span> {risk.hazard_type}
                        {isNew ? <span className='threats-new-badge'>New</span> : null}
                      </h3>
                      <p>
                        {risk.ward_name}
                        {risk.county_name ? `, ${risk.county_name}` : ''}
                      </p>
                    </div>
                    <span className={`risk-badge ${riskBadgeClass(risk.risk_level)}`}>{risk.risk_level.toUpperCase()}</span>
                  </div>

                  <div className='feed-card-metrics'>
                    <span>{Math.round(risk.risk_score)}% probability</span>
                    <span>{formatAgoFromDate(risk.issued_at)}</span>
                  </div>

                  <div className='probability-track'>
                    <div className='probability-fill' style={{ width: probabilityWidth(risk.risk_score) }} />
                  </div>

                  <p className='feed-summary'>{risk.summary}</p>

                  <div className='threats-card-actions'>
                    <button
                      type='button'
                      className='drawer-toggle'
                      onClick={() => {
                        if (!isExpanded) ensureNearestUnits(risk).catch(() => undefined);
                        setExpandedRiskId(isExpanded ? null : risk.id);
                      }}
                    >
                      {isExpanded ? 'Hide details' : 'Expand details'}
                    </button>
                    <button type='button' className='drawer-toggle' onClick={() => copyShareLink(risk.id)}>
                      Share this alert {shareMessageById[risk.id] ? `(${shareMessageById[risk.id]})` : ''}
                    </button>
                  </div>

                  {isExpanded ? (
                    <div className='drawer-content'>
                      <p>
                        <strong>English guidance:</strong> {risk.guidance_en}
                      </p>
                      <p>
                        <strong>Swahili guidance:</strong> {risk.guidance_sw}
                      </p>
                      <p>
                        <strong>What to do:</strong> {risk.guidance_en}
                      </p>
                      <p>
                        <strong>What not to do:</strong> {hazardMeta[hazard]?.dont || 'Do not ignore official alerts.'}
                      </p>
                      <p>
                        <strong>3 nearest rescue phones:</strong>
                      </p>
                      <ul className='units-list'>
                        {nearest.length ? (
                          nearest.map((unit) => (
                            <li key={unit.id}>
                              {unit.name}: {unit.phone_number} - {unit.is_live ? 'live now' : 'stale location'}
                              {unit.distance_m !== null ? ` - ${Math.round(unit.distance_m)}m away` : ''}
                            </li>
                          ))
                        ) : (
                          <li>No active responders nearby right now.</li>
                        )}
                      </ul>
                      <p>
                        <Link href={`/threats/${risk.id}`} className='view-all-link'>
                          Open share page
                        </Link>
                      </p>
                    </div>
                  ) : null}
                </article>
              );
            })}

            {!filteredAndSorted.length && !loading ? (
              <article className='feed-card'>
                <p className='feed-summary'>No threats match the current filters.</p>
              </article>
            ) : null}
          </div>
        </aside>
      </section>
    </main>
  );
}
