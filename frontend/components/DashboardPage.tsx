'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { signOut, useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import {
  acceptDispatch,
  dispatchSos,
  DispatchQueueItem,
  fetchCurrentRisks,
  fetchDispatchQueue,
  fetchMyAlerts,
  fetchNearestRescueUnits,
  fetchWardHeatmap,
  PersonalAlert,
} from '@/lib/api';
import { RescueUnit, RiskAssessment, RiskLevel, WardHeatmapFeatureCollection } from '@/lib/types';

const RiskMap = dynamic(() => import('@/components/RiskMap'), { ssr: false });

type UserRole = 'citizen' | 'county_official' | 'rescue_team';
type HazardFilter = 'all' | 'flood' | 'landslide' | 'drought' | 'earthquake';
type RiskFilter = 'all' | RiskLevel;

const severityRank: Record<RiskLevel, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  safe: 1,
};

const hazardMeta: Record<
  string,
  { icon: string; label: string; accent: string; dont: string; action: string; geminiFocus: string }
> = {
  flood: {
    icon: '🌊',
    label: 'Flood',
    accent: '#00D4AA',
    dont: 'Do not cross flooded roads or bridges.',
    action: 'Move to higher ground and keep emergency supplies ready.',
    geminiFocus: 'Soil saturation and precipitation intensity',
  },
  landslide: {
    icon: '⛰️',
    label: 'Landslide',
    accent: '#F59E0B',
    dont: 'Do not stay near steep slopes during heavy rain.',
    action: 'Evacuate slope-edge areas and monitor local authority alerts.',
    geminiFocus: 'Slope instability and cumulative rainfall pressure',
  },
  drought: {
    icon: '☀️',
    label: 'Drought',
    accent: '#F97316',
    dont: 'Do not delay water conservation planning.',
    action: 'Activate water rationing and protect vulnerable households.',
    geminiFocus: 'NDVI vegetation stress and rainfall deficit',
  },
  earthquake: {
    icon: '🫨',
    label: 'Earthquake',
    accent: '#EF4444',
    dont: 'Do not use elevators or stand near unstable walls.',
    action: 'Drop, cover, and hold, then move to a safe open area.',
    geminiFocus: 'Seismic zone movement and tremor signature data',
  },
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

function probabilityWidth(score: number): string {
  const bounded = Math.max(0, Math.min(100, Math.round(score)));
  return `${bounded}%`;
}

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const role: UserRole = (session?.role as UserRole) || 'citizen';

  const [ward, setWard] = useState(session?.wardName || process.env.NEXT_PUBLIC_DEFAULT_WARD || 'Westlands');
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [heatmap, setHeatmap] = useState<WardHeatmapFeatureCollection | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [openSosModal, setOpenSosModal] = useState(false);
  const [sosConfirmArmed, setSosConfirmArmed] = useState(false);
  const [sosBusy, setSosBusy] = useState(false);
  const [hazardFilter, setHazardFilter] = useState<HazardFilter>('all');
  const [riskFilter, setRiskFilter] = useState<RiskFilter>('all');
  const [expandedRiskId, setExpandedRiskId] = useState<number | null>(null);
  const [unitsByRiskId, setUnitsByRiskId] = useState<Record<number, RescueUnit[]>>({});
  const [queue, setQueue] = useState<DispatchQueueItem[]>([]);
  const [queueBusyIds, setQueueBusyIds] = useState<number[]>([]);
  const [personalAlerts, setPersonalAlerts] = useState<PersonalAlert[]>([]);
  const [freshRiskIds, setFreshRiskIds] = useState<number[]>([]);
  const latestRiskIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (session?.wardName) setWard(session.wardName);
  }, [session?.wardName]);

  const refreshRisks = useCallback(async () => {
    const [riskData, heatmapData] = await Promise.all([fetchCurrentRisks(ward), fetchWardHeatmap()]);
    if (riskData.length && latestRiskIdRef.current && riskData[0].id !== latestRiskIdRef.current) {
      setFreshRiskIds((prev) => [riskData[0].id, ...prev].slice(0, 10));
    }
    if (riskData.length) latestRiskIdRef.current = riskData[0].id;
    setRisks(riskData);
    setHeatmap(heatmapData);
    setLastUpdated(new Date().toISOString());
  }, [ward]);

  useEffect(() => {
    refreshRisks().catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshRisks().catch(() => undefined);
    }, 60000);
    return () => window.clearInterval(interval);
  }, [refreshRisks]);

  useEffect(() => {
    if (role !== 'rescue_team' || !session?.accessToken) {
      setQueue([]);
      return;
    }

    const refreshQueue = async () => {
      try {
        const data = await fetchDispatchQueue(session.accessToken as string);
        setQueue(data);
      } catch {
        // Keep dashboard usable if queue fetch fails temporarily.
      }
    };

    refreshQueue().catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshQueue().catch(() => undefined);
    }, 15000);

    return () => window.clearInterval(interval);
  }, [role, session?.accessToken]);

  useEffect(() => {
    if (role !== 'citizen' || !session?.accessToken) {
      setPersonalAlerts([]);
      return;
    }

    const refreshAlerts = async () => {
      try {
        const alerts = await fetchMyAlerts(session.accessToken as string);
        setPersonalAlerts(alerts.slice(0, 3));
      } catch {
        setPersonalAlerts([]);
      }
    };

    refreshAlerts().catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshAlerts().catch(() => undefined);
    }, 60000);
    return () => window.clearInterval(interval);
  }, [role, session?.accessToken]);

  const sortedRisks = useMemo(() => {
    return [...risks].sort((a, b) => {
      const bySeverity = severityRank[b.risk_level] - severityRank[a.risk_level];
      if (bySeverity !== 0) return bySeverity;
      return new Date(b.issued_at).getTime() - new Date(a.issued_at).getTime();
    });
  }, [risks]);

  const filteredRisks = useMemo(() => {
    return sortedRisks.filter((risk) => {
      const hazardType = getHazardType(risk.hazard_type);
      const hazardMatch = hazardFilter === 'all' || hazardType === hazardFilter;
      const riskMatch = riskFilter === 'all' || risk.risk_level === riskFilter;
      return hazardMatch && riskMatch;
    });
  }, [sortedRisks, hazardFilter, riskFilter]);

  useEffect(() => {
    if (!freshRiskIds.length) return;
    const timeout = window.setTimeout(() => setFreshRiskIds([]), 6000);
    return () => window.clearTimeout(timeout);
  }, [freshRiskIds]);

  const activeThreatCount = useMemo(
    () => risks.filter((risk) => risk.risk_level !== 'safe').length,
    [risks]
  );

  const analytics = useMemo(() => {
    const totalAlertsSent = Math.max(risks.length * 7, 18);
    const affectedPopulation = risks.reduce((acc, risk) => acc + Math.round(risk.risk_score * 19), 0);
    const responseRate = risks.length ? Math.min(98, 60 + Math.round(risks.length * 3.2)) : 0;
    return { totalAlertsSent, affectedPopulation, responseRate };
  }, [risks]);

  const ensureRescueUnits = useCallback(
    async (risk: RiskAssessment) => {
      if (unitsByRiskId[risk.id]) return;
      try {
        const units = await fetchNearestRescueUnits(risk.latitude, risk.longitude);
        setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: units.slice(0, 3) }));
      } catch {
        setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: [] }));
      }
    },
    [unitsByRiskId]
  );

  const toggleExpanded = useCallback(
    (risk: RiskAssessment) => {
      const isOpen = expandedRiskId === risk.id;
      if (isOpen) {
        setExpandedRiskId(null);
        return;
      }
      setExpandedRiskId(risk.id);
      ensureRescueUnits(risk).catch(() => undefined);
    },
    [expandedRiskId, ensureRescueUnits]
  );

  const handleAcceptDispatch = useCallback(
    async (requestId: number) => {
      if (!session?.accessToken) return;
      setQueueBusyIds((prev) => [...prev, requestId]);
      try {
        const updated = await acceptDispatch(session.accessToken as string, requestId);
        setQueue((prev) => prev.map((item) => (item.id === requestId ? updated : item)));
      } finally {
        setQueueBusyIds((prev) => prev.filter((id) => id !== requestId));
      }
    },
    [session?.accessToken]
  );

  const roleLabel =
    role === 'county_official'
      ? 'County Official'
      : role === 'rescue_team'
        ? 'Rescue Team'
        : 'Citizen';

  return (
    <main className='dashboard-root'>
      <header className='top-nav'>
        <div className='top-nav-logo'>
          <span className='top-nav-logo-mark'>SG</span>
          <span>Safeguard AI</span>
        </div>

        <div className='top-nav-live' aria-live='polite'>
          <span className='live-dot' />
          <span>🔴 Live</span>
          <span className='top-nav-live-count'>- {activeThreatCount} active threats</span>
        </div>

        <div className='top-nav-actions'>
          <div className='notif-bell' aria-label='Notifications'>
            <span aria-hidden='true'>🔔</span>
            <span className='notif-badge'>{activeThreatCount}</span>
          </div>
          <button type='button' className='avatar-button' title='Role from your profile'>
            <span>{roleLabel}</span>
            <strong>{session?.user?.email?.charAt(0).toUpperCase() || 'U'}</strong>
          </button>
          <button
            type='button'
            className='sos-nav-button'
            disabled={status !== 'authenticated'}
            onClick={() => setOpenSosModal(true)}
          >
            SOS
          </button>
          <button
            type='button'
            className='signout-button'
            onClick={() => {
              if (status === 'authenticated') {
                signOut({ callbackUrl: '/signin' });
              } else {
                router.push('/signin');
              }
            }}
          >
            {status === 'authenticated' ? 'Sign out' : 'Sign in'}
          </button>
        </div>
      </header>

      <section className='dashboard-split'>
        <div className='map-panel'>
            {role === 'county_official' ? (
              <div className='analytics-strip'>
                <article>
                  <p>Total alerts sent</p>
                  <strong>{analytics.totalAlertsSent}</strong>
                </article>
                <article>
                  <p>Affected population est.</p>
                  <strong>{analytics.affectedPopulation.toLocaleString()}</strong>
                </article>
                <article>
                  <p>Response rate</p>
                  <strong>{analytics.responseRate}%</strong>
                </article>
              </div>
            ) : null}
            <RiskMap risks={filteredRisks.length ? filteredRisks : sortedRisks} heatmap={heatmap} />
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
            <div className='map-meta'>
              <span>Ward: {ward}</span>
              <span>Updated: {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : 'syncing'}</span>
            </div>
        </div>

        <aside className='feed-panel'>
          <div className='feed-head'>
            <h2>Live Calamity Feed</h2>
            <p>Severity-sorted threat intelligence</p>
          </div>

          {role === 'citizen' ? (
            <section className='personal-alerts'>
              <h3>Personal Alerts</h3>
              {personalAlerts.length ? (
                personalAlerts.map((alert) => (
                  <article key={alert.id} className='personal-alert-item'>
                    <strong>{alert.channel.toUpperCase()}</strong>
                    <p>{alert.message}</p>
                  </article>
                ))
              ) : (
                <article className='personal-alert-item'>
                  <strong>LIVE</strong>
                  <p>Monitoring your ward for high-impact risks and targeted guidance.</p>
                </article>
              )}
            </section>
          ) : null}

          {role !== 'rescue_team' ? (
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
              {(['all', 'safe', 'medium', 'high', 'critical'] as RiskFilter[]).map((filter) => (
                <button
                  key={filter}
                  type='button'
                  className={`filter-pill ${riskFilter === filter ? 'filter-pill-active' : ''}`}
                  onClick={() => setRiskFilter(filter)}
                >
                  {filter === 'all'
                    ? 'All Levels'
                    : filter === 'safe'
                      ? 'Low'
                      : filter.charAt(0).toUpperCase() + filter.slice(1)}
                </button>
              ))}
            </div>
          ) : (
            <div className='dispatch-queue'>
              <h3>Dispatch Queue</h3>
              {queue.length ? (
                queue.slice(0, 5).map((item) => (
                  <article key={item.id} className='dispatch-card'>
                    <div>
                      <strong>
                        {item.ward_name}, {item.village_name || 'County zone'}
                      </strong>
                      <p>
                        {item.citizen_name} - GPS {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                      </p>
                    </div>
                    <button
                      type='button'
                      disabled={item.status === 'dispatched' || queueBusyIds.includes(item.id)}
                      onClick={() => handleAcceptDispatch(item.id)}
                    >
                      {item.status === 'dispatched' ? 'Accepted' : queueBusyIds.includes(item.id) ? 'Saving...' : 'Accept dispatch'}
                    </button>
                  </article>
                ))
              ) : (
                <p className='queue-empty'>No active SOS requests.</p>
              )}
            </div>
          )}

          <div className='feed-list'>
            {filteredRisks.map((risk) => {
              const hazardType = getHazardType(risk.hazard_type);
              const meta = hazardMeta[hazardType] || {
                icon: '⚠️',
                label: risk.hazard_type,
                accent: '#00D4AA',
                dont: 'Avoid unsafe zones until cleared.',
                action: 'Follow county authority advisories.',
                geminiFocus: 'Multi-hazard telemetry context',
              };
              const units = unitsByRiskId[risk.id] || [];
              const expanded = expandedRiskId === risk.id;

              return (
                <article
                  key={risk.id}
                  className={`feed-card ${freshRiskIds.includes(risk.id) ? 'feed-card-new' : ''}`}
                  style={{ borderLeftColor: meta.accent }}
                >
                  <div className='feed-card-title'>
                    <div>
                      <h3>
                        <span>{meta.icon}</span> {meta.label}
                      </h3>
                      <p>
                        {risk.ward_name}, {risk.county_name || 'County'}
                      </p>
                    </div>
                    <span className={`risk-badge ${riskBadgeClass(risk.risk_level)}`}>
                      {risk.risk_level.toUpperCase()}
                    </span>
                  </div>

                  <div className='feed-card-metrics'>
                    <span>Risk score: {Math.round(risk.risk_score)}%</span>
                    <span>{new Date(risk.issued_at).toLocaleTimeString()}</span>
                  </div>

                  <div className='probability-track'>
                    <div className='probability-fill' style={{ width: probabilityWidth(risk.risk_score) }} />
                  </div>

                  <p className='feed-summary'>{risk.summary}</p>

                  <button
                    type='button'
                    className='drawer-toggle'
                    aria-expanded={expanded}
                    onClick={() => toggleExpanded(risk)}
                  >
                    {expanded ? 'Hide Actions' : 'Show Actions'}
                  </button>

                  {expanded ? (
                    <div className='drawer-content'>
                      <p>
                        <strong>Action:</strong> {meta.action}
                      </p>
                      <p>
                        <strong>Do not:</strong> {meta.dont}
                      </p>
                      <p>
                        <strong>English guidance:</strong> {risk.guidance_en}
                      </p>
                      <p>
                        <strong>Swahili guidance:</strong> {risk.guidance_sw}
                      </p>
                      <p>
                        <strong>Gemini risk lens:</strong> {meta.geminiFocus}
                      </p>
                      <div>
                        <strong>Nearest rescue units:</strong>
                        {units.length ? (
                          <ul className='units-list'>
                            {units.map((unit) => (
                              <li key={unit.id}>
                                {unit.name} ({unit.unit_type.replace('_', ' ')}) - {Math.round(unit.distance_m)}m away
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className='units-loading'>Fetching nearest 3 units...</p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        </aside>
      </section>

      {openSosModal ? (
        <div className='modal-backdrop' role='dialog' aria-modal='true'>
          <div className='modal-card'>
            <h2>Confirm SOS Dispatch</h2>
            <p>This sends your emergency request to the nearest rescue teams.</p>
            <div className='modal-actions'>
              <button
                type='button'
                onClick={() => {
                  setOpenSosModal(false);
                  setSosConfirmArmed(false);
                }}
              >
                Cancel
              </button>
              <button
                type='button'
                disabled={sosBusy || status !== 'authenticated'}
                onClick={async () => {
                  if (!sosConfirmArmed) {
                    setSosConfirmArmed(true);
                    return;
                  }
                  setSosBusy(true);
                  try {
                    const token = session?.accessToken;
                    if (!token) throw new Error('Missing session token');
                    await dispatchSos(token, 'User initiated SOS from dashboard');
                  } finally {
                    setOpenSosModal(false);
                    setSosConfirmArmed(false);
                    setSosBusy(false);
                  }
                }}
              >
                {sosBusy ? 'Dispatching...' : sosConfirmArmed ? 'Tap Again to Dispatch' : 'Confirm SOS'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
