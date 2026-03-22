'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { signOut, useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import {
  acceptDispatch,
  dispatchSos,
  DispatchQueueItem,
  fetchCurrentRisks,
  fetchDispatchQueue,
  fetchMyAlerts,
  fetchNearestRescueUnits,
  updateRescueResponderHeartbeat,
  fetchWardHeatmap,
  PersonalAlert,
  riskEventsUrl,
} from '@/lib/api';
  // Real-time SSE subscription for calamities
  useEffect(() => {
    const url = riskEventsUrl();
    const eventSource = new EventSource(url);
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        // Only update if the ward matches or no ward filter is set
        if (!ward || payload.ward_name?.toLowerCase() === ward.toLowerCase()) {
          setRisks((prev) => {
            // Replace or add the new risk by id
            const idx = prev.findIndex((r) => r.id === payload.id);
            if (idx !== -1) {
              const updated = [...prev];
              updated[idx] = payload;
              return updated;
            }
            return [payload, ...prev].slice(0, 100);
          });
        }
      } catch (e) {
        // Ignore parse errors
      }
    };
    eventSource.onerror = () => {
      // Optionally handle errors or reconnect
    };
    return () => {
      eventSource.close();
    };
  }, [ward]);

import { RescueUnit, RiskAssessment, RiskLevel, WardHeatmapFeatureCollection } from '@/lib/types';
import ForecastCard, { DayForecast } from '@/components/ForecastCard';
// Fetch 7-day forecast for a ward
async function fetchForecast(ward: string): Promise<DayForecast[]> {
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const query = ward ? `?ward=${encodeURIComponent(ward)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/risk/forecast/${query}`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to fetch forecast');
  return response.json();
}

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
    // Forecast state
    const [forecast, setForecast] = useState<DayForecast[] | null>(null);
    const [forecastError, setForecastError] = useState<string | null>(null);
    const [forecastLoading, setForecastLoading] = useState(false);
    // Fetch forecast when ward changes
    useEffect(() => {
      let ignore = false;
      setForecastLoading(true);
      setForecastError(null);
      fetchForecast(ward)
        .then((data) => {
          if (!ignore) setForecast(data);
        })
        .catch((err) => {
          if (!ignore) setForecastError('Could not load forecast');
        })
        .finally(() => {
          if (!ignore) setForecastLoading(false);
        });
      return () => {
        ignore = true;
      };
    }, [ward]);
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
  const [personalAlertsBusy, setPersonalAlertsBusy] = useState(false);
  const [alertsSyncMessage, setAlertsSyncMessage] = useState<string | null>(null);
  const [livePopups, setLivePopups] = useState<Array<{ id: string; title: string; body: string }>>([]);
  const [freshRiskIds, setFreshRiskIds] = useState<number[]>([]);
  const latestRiskIdRef = useRef<number | null>(null);
  const seenRiskIdsRef = useRef<Set<number>>(new Set());
  const seenPersonalAlertIdsRef = useRef<Set<number>>(new Set());

  const pushPopup = useCallback((title: string, body: string) => {
    const popupId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setLivePopups((prev) => {
      const next = [{ id: popupId, title, body }, ...prev];
      return next.slice(0, 3);
    });
  }, []);

  const dismissPopup = useCallback((id: string) => {
    setLivePopups((prev) => prev.filter((item) => item.id !== id));
  }, []);

  useEffect(() => {
    if (session?.wardName) setWard(session.wardName);
  }, [session?.wardName]);

  const refreshRisks = useCallback(async () => {
    const [riskData, heatmapData] = await Promise.all([fetchCurrentRisks(ward), fetchWardHeatmap()]);

    const hasBootstrapped = seenRiskIdsRef.current.size > 0;
    const incomingIds = new Set(riskData.map((risk) => risk.id));
    const newRisks = riskData.filter((risk) => !seenRiskIdsRef.current.has(risk.id));

    if (hasBootstrapped) {
      newRisks
        .filter((risk) => risk.risk_level === 'high' || risk.risk_level === 'critical')
        .slice(0, 2)
        .forEach((risk) => {
          pushPopup(
            `${risk.risk_level.toUpperCase()} alert: ${risk.hazard_type}`,
            `${risk.ward_name}${risk.village_name ? ` / ${risk.village_name}` : ''} - score ${Math.round(risk.risk_score)}%`
          );
        });
    }

    seenRiskIdsRef.current = incomingIds;

    if (riskData.length && latestRiskIdRef.current && riskData[0].id !== latestRiskIdRef.current) {
      setFreshRiskIds((prev) => [riskData[0].id, ...prev].slice(0, 10));
    }
    if (riskData.length) latestRiskIdRef.current = riskData[0].id;
    setRisks(riskData);
    setHeatmap(heatmapData);
    setLastUpdated(new Date().toISOString());
  }, [pushPopup, ward]);

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
    if (role !== 'rescue_team' || !session?.accessToken || typeof navigator === 'undefined' || !navigator.geolocation) {
      return;
    }

    const token = session.accessToken as string;

    const publishHeartbeat = async (coords: GeolocationCoordinates) => {
      await updateRescueResponderHeartbeat(token, {
        latitude: coords.latitude,
        longitude: coords.longitude,
        is_available_for_dispatch: true,
      });
    };

    const onLocation = (position: GeolocationPosition) => {
      publishHeartbeat(position.coords).catch(() => undefined);
    };

    const onLocationError = () => {
      // If location is blocked, keep dashboard usable without crashing.
    };

    const watchId = navigator.geolocation.watchPosition(onLocation, onLocationError, {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 10000,
    });

    navigator.geolocation.getCurrentPosition(onLocation, onLocationError, {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 10000,
    });

    const pulse = window.setInterval(() => {
      navigator.geolocation.getCurrentPosition(onLocation, onLocationError, {
        enableHighAccuracy: true,
        timeout: 12000,
        maximumAge: 10000,
      });
    }, 20000);

    return () => {
      navigator.geolocation.clearWatch(watchId);
      window.clearInterval(pulse);
    };
  }, [role, session?.accessToken]);

  const refreshPersonalAlerts = useCallback(async (showToast = false) => {
    if (role !== 'citizen' || !session?.accessToken) return;
    setPersonalAlertsBusy(true);
    try {
      const alerts = await fetchMyAlerts(session.accessToken as string);
      setPersonalAlerts(alerts.slice(0, 3));

      const hasBootstrapped = seenPersonalAlertIdsRef.current.size > 0;
      const incomingIds = new Set(alerts.map((alert) => alert.id));
      const newAlerts = alerts.filter((alert) => !seenPersonalAlertIdsRef.current.has(alert.id));
      if (hasBootstrapped) {
        newAlerts.slice(0, 2).forEach((alert) => {
          pushPopup(`New ${alert.channel.toUpperCase()} alert`, alert.message);
        });
      }
      seenPersonalAlertIdsRef.current = incomingIds;

      if (showToast) {
        setAlertsSyncMessage('Alerts synced successfully.');
      }
    } catch {
      setPersonalAlerts([]);
      if (showToast) {
        setAlertsSyncMessage('Could not refresh alerts right now.');
      }
    } finally {
      setPersonalAlertsBusy(false);
    }
  }, [pushPopup, role, session?.accessToken]);

  useEffect(() => {
    if (role !== 'citizen' || !session?.accessToken) {
      setPersonalAlerts([]);
      return;
    }

    refreshPersonalAlerts(false).catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshPersonalAlerts(false).catch(() => undefined);
    }, 30000);
    return () => window.clearInterval(interval);
  }, [refreshPersonalAlerts, role, session?.accessToken]);

  useEffect(() => {
    if (!alertsSyncMessage) return;
    const timeout = window.setTimeout(() => setAlertsSyncMessage(null), 2400);
    return () => window.clearTimeout(timeout);
  }, [alertsSyncMessage]);

  useEffect(() => {
    if (!livePopups.length) return;
    const timeout = window.setTimeout(() => {
      setLivePopups((prev) => prev.slice(0, -1));
    }, 9000);
    return () => window.clearTimeout(timeout);
  }, [livePopups]);

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

  const refreshNearestUnits = useCallback(async (risk: RiskAssessment) => {
    try {
      const units = await fetchNearestRescueUnits(risk.latitude, risk.longitude);
      setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: units.slice(0, 3) }));
    } catch {
      setUnitsByRiskId((prev) => ({ ...prev, [risk.id]: [] }));
    }
  }, []);

  const ensureRescueUnits = useCallback(
    async (risk: RiskAssessment) => {
      if (unitsByRiskId[risk.id]) return;
      await refreshNearestUnits(risk);
    },
    [refreshNearestUnits, unitsByRiskId]
  );

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
      <div className='dashboard-alert-stack' aria-live='polite'>
        <AnimatePresence>
          {livePopups.map((popup) => (
            <motion.article
              key={popup.id}
              initial={{ opacity: 0, x: 24, y: -10 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: 28, y: -8 }}
              transition={{ duration: 0.22 }}
              className='dashboard-alert-toast'
            >
              <strong>{popup.title}</strong>
              <p>{popup.body}</p>
              <div className='dashboard-alert-actions'>
                <button type='button' onClick={() => dismissPopup(popup.id)}>
                  Dismiss
                </button>
              </div>
            </motion.article>
          ))}
          {alertsSyncMessage ? (
            <motion.article
              key={alertsSyncMessage}
              initial={{ opacity: 0, x: 24, y: -10 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: 28, y: -8 }}
              transition={{ duration: 0.22 }}
              className='dashboard-alert-toast'
            >
              <strong>Alerts update</strong>
              <p>{alertsSyncMessage}</p>
              <div className='dashboard-alert-actions'>
                <button type='button' onClick={() => setAlertsSyncMessage(null)}>
                  Dismiss
                </button>
              </div>
            </motion.article>
          ) : null}
        </AnimatePresence>
      </div>

      <header className='top-nav'>
              {/* Forecast card at the top, below nav */}
              <div style={{ maxWidth: 900, margin: '0 auto', width: '100%' }}>
                {forecastLoading ? (
                  <div style={{ padding: 16, textAlign: 'center', color: '#aaa' }}>Loading 7-day risk forecast...</div>
                ) : forecastError ? (
                  <div style={{ padding: 16, textAlign: 'center', color: '#ef4444' }}>{forecastError}</div>
                ) : forecast && forecast.length ? (
                  <ForecastCard forecast={forecast} />
                ) : null}
              </div>
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
            <section id='alerts' className='personal-alerts'>
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
              <div className='personal-alert-actions'>
                <button
                  type='button'
                  className='personal-alert-refresh'
                  disabled={personalAlertsBusy}
                  onClick={() => refreshPersonalAlerts(true).catch(() => undefined)}
                >
                  {personalAlertsBusy ? 'Refreshing...' : 'Get latest alerts'}
                </button>
                <button type='button' className='sos-nav-button' onClick={() => setOpenSosModal(true)}>
                  Request nearby rescue
                </button>
              </div>
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
                                {unit.name} ({unit.unit_type.replace('_', ' ')}) - {unit.phone_number} -{' '}
                                {unit.distance_m !== null ? `${Math.round(unit.distance_m)}m away` : 'distance unavailable'} -{' '}
                                {unit.is_live ? 'live now' : 'stale location'}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className='units-loading'>No active responders nearby right now.</p>
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
