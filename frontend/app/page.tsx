'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  fetchCurrentRisks,
  fetchPublicRiskCount,
  fetchPublicStats,
  fetchPublicWeatherConditions,
  PublicWeatherCondition,
} from '@/lib/api';
import { RiskAssessment, RiskLevel } from '@/lib/types';

const PublicMapPreview = dynamic(() => import('@/components/PublicMapPreview'), { ssr: false });

type HazardFilter = 'all' | 'flood' | 'landslide' | 'drought' | 'earthquake';

const severityRank: Record<RiskLevel, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  safe: 1,
};

const hazardIcon: Record<HazardFilter, string> = {
  all: '⚠️',
  flood: '🌊',
  landslide: '⛰️',
  drought: '☀️',
  earthquake: '🫨',
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

function formatAgo(iso: string): string {
  const seconds = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export default function PublicHomePage() {
  const [riskCount, setRiskCount] = useState(0);
  const [stats, setStats] = useState({ counties_covered: 0, alerts_sent_today: 0, prediction_accuracy: 0 });
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [weatherConditions, setWeatherConditions] = useState<PublicWeatherCondition[]>([]);
  const [hazardFilter, setHazardFilter] = useState<HazardFilter>('all');
  const [stuck, setStuck] = useState(false);
  const seenRiskIdsRef = useRef<Set<number>>(new Set());
  const hasBootstrappedRef = useRef(false);
  const [freshIds, setFreshIds] = useState<number[]>([]);
  const [popupAlerts, setPopupAlerts] = useState<RiskAssessment[]>([]);
  const [signalEnabled, setSignalEnabled] = useState(true);
  const audioContextRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 10);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const emitAlertSignal = useCallback(() => {
    if (typeof window === 'undefined' || !signalEnabled) return;

    if ('vibrate' in navigator) {
      navigator.vibrate([120, 70, 120]);
    }

    const AudioContextConstructor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextConstructor) {
      return;
    }

    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextConstructor();
      }

      const context = audioContextRef.current;
      if (context.state === 'suspended') {
        context.resume().catch(() => undefined);
      }

      const now = context.currentTime;
      const oscillator = context.createOscillator();
      const gainNode = context.createGain();

      oscillator.type = 'triangle';
      oscillator.frequency.setValueAtTime(880, now);
      oscillator.frequency.linearRampToValueAtTime(1040, now + 0.14);

      gainNode.gain.setValueAtTime(0.0001, now);
      gainNode.gain.exponentialRampToValueAtTime(0.09, now + 0.03);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, now + 0.24);

      oscillator.connect(gainNode);
      gainNode.connect(context.destination);
      oscillator.start(now);
      oscillator.stop(now + 0.24);
    } catch {
      // Keep feed working even when audio APIs are restricted.
    }
  }, [signalEnabled]);

  const refreshAll = useCallback(async () => {
    const [countPayload, statsPayload, riskPayload, weatherPayload] = await Promise.all([
      fetchPublicRiskCount(),
      fetchPublicStats(),
      fetchCurrentRisks(),
      fetchPublicWeatherConditions(8),
    ]);
    setRiskCount(countPayload.active_threat_count);
    setStats(statsPayload);
    setWeatherConditions(weatherPayload);

    const sorted = [...riskPayload].sort((a, b) => {
      const bySeverity = severityRank[b.risk_level] - severityRank[a.risk_level];
      if (bySeverity !== 0) return bySeverity;
      return new Date(b.issued_at).getTime() - new Date(a.issued_at).getTime();
    });

    const seenRiskIds = seenRiskIdsRef.current;
    const newRisks = sorted.filter((risk) => !seenRiskIds.has(risk.id));
    sorted.forEach((risk) => seenRiskIds.add(risk.id));

    if (newRisks.length) {
      setFreshIds((prev) => [...newRisks.map((risk) => risk.id), ...prev].slice(0, 8));
      if (hasBootstrappedRef.current) {
        setPopupAlerts((prev) => [...newRisks.slice(0, 3), ...prev].slice(0, 4));
        emitAlertSignal();
      }
    }

    hasBootstrappedRef.current = true;
    setRisks(sorted);
  }, [emitAlertSignal]);

  useEffect(() => {
    refreshAll().catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 20000);
    return () => window.clearInterval(interval);
  }, [refreshAll]);

  useEffect(() => {
    if (!freshIds.length) return;
    const timeout = window.setTimeout(() => setFreshIds([]), 5500);
    return () => window.clearTimeout(timeout);
  }, [freshIds]);

  useEffect(() => {
    if (!popupAlerts.length) return;
    const timeout = window.setTimeout(() => {
      setPopupAlerts((prev) => prev.slice(1));
    }, 4500);
    return () => window.clearTimeout(timeout);
  }, [popupAlerts]);

  const filteredRisks = useMemo(() => {
    return risks.filter((risk) => {
      const hazard = getHazardType(risk.hazard_type);
      return hazardFilter === 'all' || hazard === hazardFilter;
    });
  }, [risks, hazardFilter]);

  const topFour = filteredRisks.slice(0, 4);

  const weatherTop = weatherConditions.slice(0, 6);

  function dismissPopup(riskId: number) {
    setPopupAlerts((prev) => prev.filter((risk) => risk.id !== riskId));
  }

  function formatMetric(value: number | null, suffix: string): string {
    if (value === null || Number.isNaN(value)) return 'N/A';
    return `${Math.round(value * 10) / 10}${suffix}`;
  }

  return (
    <main className='public-root'>
      <div className='public-alert-stack' aria-live='assertive'>
        <AnimatePresence>
          {popupAlerts.map((risk) => (
            <motion.article
              key={risk.id}
              initial={{ opacity: 0, x: 24, y: -10 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: 28, y: -8 }}
              transition={{ duration: 0.22 }}
              className='public-alert-toast'
            >
              <strong>New {risk.hazard_type} alert</strong>
              <p>
                {risk.ward_name}
                {risk.county_name ? `, ${risk.county_name}` : ''} - {risk.risk_level.toUpperCase()} severity.
              </p>
              <div className='public-alert-actions'>
                <Link href={`/threats/${risk.id}`} className='public-alert-link'>
                  View threat
                </Link>
                <button type='button' onClick={() => dismissPopup(risk.id)}>
                  Dismiss
                </button>
              </div>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>

      <header className={`public-nav ${stuck ? 'public-nav-stuck' : ''}`}>
        <div className='public-logo'>Safeguard AI</div>
        <nav className='public-nav-links'>
          <a href='#live-threats'>Live threats</a>
          <Link href='/how-it-works'>How it works</Link>
          <a href='#for-counties'>For counties</a>
        </nav>
        <div className='public-nav-cta'>
          <button
            type='button'
            className='public-alert-toggle'
            onClick={() => setSignalEnabled((prev) => !prev)}
            aria-pressed={signalEnabled}
          >
            Alert signal: {signalEnabled ? 'On' : 'Off'}
          </button>
          <Link href='/signin' className='public-signin'>Sign in</Link>
          <Link href='/register' className='public-get-alerts'>Get alerts</Link>
        </div>
      </header>

      <section className='public-hero'>
        <div className='hero-pill'>🔴 Live - {riskCount} active threats</div>
        <h1>AI Early Warning For Floods, Droughts, Landslides, And Earthquakes</h1>
        <p>
          Public trust starts with visible live signals. Safeguard AI continuously predicts hazard risk and routes
          life-saving guidance to communities before disaster impact escalates.
        </p>
        <div className='hero-cta'>
          <Link href='/register' className='hero-primary'>Get free alerts</Link>
          <Link href='/dashboard' className='hero-secondary'>View live map</Link>
        </div>
        <div className='hero-stats'>
          <article>
            <strong>{stats.counties_covered}</strong>
            <span>Counties covered</span>
          </article>
          <article>
            <strong>{stats.alerts_sent_today}</strong>
            <span>Alerts sent today</span>
          </article>
          <article>
            <strong>{stats.prediction_accuracy}%</strong>
            <span>Prediction accuracy</span>
          </article>
        </div>
      </section>

      <section id='live-threats' className='public-feed'>
        <div className='section-head'>
          <h2>Live Calamity Feed</h2>
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
        </div>

        <div className='public-feed-grid'>
          <AnimatePresence mode='popLayout'>
            {topFour.map((risk) => {
              const hazard = getHazardType(risk.hazard_type);
              return (
                <motion.article
                  key={risk.id}
                  layout
                  initial={freshIds.includes(risk.id) ? { y: -22, opacity: 0 } : false}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ opacity: 0, y: 12 }}
                  transition={{ duration: 0.25 }}
                  className='public-feed-card'
                >
                  <div className='feed-card-title'>
                    <div>
                      <h3>
                        <span>{hazardIcon[hazard]}</span> {risk.hazard_type}
                      </h3>
                      <p>
                        {risk.ward_name}
                        {risk.county_name ? `, ${risk.county_name}` : ''}
                      </p>
                    </div>
                    <span className={`risk-badge ${riskBadgeClass(risk.risk_level)}`}>
                      {risk.risk_level.toUpperCase()}
                    </span>
                  </div>
                  <div className='feed-card-metrics'>
                    <span>{Math.round(risk.risk_score)}% probability</span>
                    <span>{formatAgo(risk.issued_at)}</span>
                  </div>
                  <div className='probability-track'>
                    <div className='probability-fill' style={{ width: probabilityWidth(risk.risk_score) }} />
                  </div>
                  <p className='feed-summary'>{risk.summary}</p>
                </motion.article>
              );
            })}
          </AnimatePresence>
        </div>
        <Link className='view-all-link' href='/threats'>View all threats</Link>
      </section>

      <section className='public-map-preview'>
        <div className='section-head'>
          <h2>Map Preview</h2>
          <p>Click to open full live dashboard</p>
        </div>
        <Link href='/dashboard' className='map-preview-link' aria-label='Open live dashboard map'>
          <PublicMapPreview risks={risks} />
        </Link>
      </section>

      <section className='public-weather'>
        <div className='section-head'>
          <h2>Live Weather Conditions</h2>
          <p>Area-specific weather factors affecting current calamity risk</p>
        </div>
        <div className='public-weather-grid'>
          {weatherTop.map((item) => (
            <article key={item.id} className='public-weather-card'>
              <div className='public-weather-title'>
                <h3>
                  {item.ward_name}
                  {item.county_name ? `, ${item.county_name}` : ''}
                </h3>
                <span>{item.hazard_type}</span>
              </div>
              <div className='public-weather-metrics'>
                <span>Temp: {formatMetric(item.temperature_c, 'C')}</span>
                <span>Rain: {formatMetric(item.precipitation_mm, 'mm')}</span>
                <span>Wind: {formatMetric(item.wind_speed_kmh, 'km/h')}</span>
              </div>
              <p>{item.impact_summary}</p>
              <small>Observed {formatAgo(item.observed_at)}</small>
            </article>
          ))}
          {!weatherTop.length ? (
            <article className='public-weather-card'>
              <h3>Weather stream starting</h3>
              <p>Current conditions will appear as soon as fresh observations are ingested.</p>
            </article>
          ) : null}
        </div>
      </section>

      <section id='how-it-works' className='features-grid'>
        <article>
          <h3>AI predictions</h3>
          <p>Hazards are scored continuously from weather + geospatial signals.</p>
        </article>
        <article>
          <h3>SMS/WhatsApp alerts</h3>
          <p>Critical guidance reaches people on channels they already use.</p>
        </article>
        <article>
          <h3>One-tap SOS</h3>
          <p>Distress requests route to nearest rescue units with live coordinates.</p>
        </article>
        <article>
          <h3>Ward-level accuracy</h3>
          <p>Localized risk intelligence narrows response to the right communities.</p>
        </article>
        <article>
          <h3>How it works</h3>
          <p>
            Explore the full workflow from data to rescue routing in plain language.
            <br />
            <Link href='/how-it-works' className='view-all-link'>Open full guide</Link>
          </p>
        </article>
      </section>

      <section id='for-counties' className='trust-bar'>
        <span>Kenya Met Department</span>
        <span>NOAA</span>
        <span>Google Gemini AI</span>
        <span>Africa&apos;s Talking</span>
        <span>Red Cross Kenya</span>
      </section>

      <footer className='public-footer'>
        <span>© {new Date().getFullYear()} Safeguard AI</span>
        <nav>
          <a href='#'>Privacy</a>
          <a href='#'>Terms</a>
          <a href='#'>Contact</a>
        </nav>
      </footer>
    </main>
  );
}
