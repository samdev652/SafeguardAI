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

    // Sort by Risk Level first, then by probability (risk_score) descending
    const sorted = [...riskPayload].sort((a, b) => {
      const bySeverity = severityRank[b.risk_level] - severityRank[a.risk_level];
      if (bySeverity !== 0) return bySeverity;
      return b.risk_score - a.risk_score;
    });

    const seenRiskIds = seenRiskIdsRef.current;
    const newRisks = sorted.filter((risk) => !seenRiskIds.has(risk.id));
    sorted.forEach((risk) => seenRiskIds.add(risk.id));

    if (newRisks.length) {
      setFreshIds((prev) => [...newRisks.map((risk) => risk.id), ...prev].slice(0, 8));
      if (hasBootstrappedRef.current) {
        setPopupAlerts((prev) => [...newRisks.slice(0, 3), ...prev].slice(0, 4));
        emitAlertSignal();
        
        const latestDanger = newRisks.find(r => r.risk_level === 'high' || r.risk_level === 'critical');
        if (latestDanger) {
           window.dispatchEvent(new CustomEvent('safeguard:new_alert', { detail: latestDanger }));
        }
      }
    }

    hasBootstrappedRef.current = true;
    setRisks(sorted);
  }, [emitAlertSignal]);

  // Handle 30s API polling
  useEffect(() => {
    refreshAll().catch(() => undefined);
    const interval = window.setInterval(() => {
      refreshAll().catch(() => undefined);
    }, 30000);
    return () => window.clearInterval(interval);
  }, [refreshAll]);

  // Clear fresh flashes
  useEffect(() => {
    if (!freshIds.length) return;
    const timeout = window.setTimeout(() => setFreshIds([]), 5500);
    return () => window.clearTimeout(timeout);
  }, [freshIds]);

  // Clear popups
  useEffect(() => {
    if (!popupAlerts.length) return;
    const timeout = window.setTimeout(() => {
      setPopupAlerts((prev) => prev.slice(1));
    }, 4500);
    return () => window.clearTimeout(timeout);
  }, [popupAlerts]);

  const [countyFilter, setCountyFilter] = useState('All');
  const [rotationIndex, setRotationIndex] = useState(0);

  // Reset rotation when filter changes
  useEffect(() => setRotationIndex(0), [countyFilter]);

  const filteredRisks = useMemo(() => {
    return risks.filter((risk) => {
      return countyFilter === 'All' || risk.county_name === countyFilter;
    });
  }, [risks, countyFilter]);

  // 8-second rotation for 6 cards at a time
  useEffect(() => {
    if (filteredRisks.length <= 6) {
      if (rotationIndex !== 0) setRotationIndex(0);
      return;
    }
    const interval = window.setInterval(() => {
      setRotationIndex((prev) => (prev + 6 >= filteredRisks.length ? 0 : prev + 6));
    }, 8000);
    return () => window.clearInterval(interval);
  }, [filteredRisks.length, rotationIndex]);

  const visibleRisks = filteredRisks.slice(rotationIndex, rotationIndex + 6);
  // Pad if we reach the end and there are fewer than 6, so UI doesn't completely empty out awkwardly
  const displayRisks = visibleRisks.length < 6 && filteredRisks.length > 6 
      ? [...visibleRisks, ...filteredRisks.slice(0, 6 - visibleRisks.length)] 
      : visibleRisks;

  const activeHighCritical = risks.filter(r => r.risk_level === 'high' || r.risk_level === 'critical');
  const [activeAlertIndex, setActiveAlertIndex] = useState(0);

  useEffect(() => {
    if (activeHighCritical.length <= 1) return;
    const interval = window.setInterval(() => {
      setActiveAlertIndex(prev => (prev + 1) % activeHighCritical.length);
    }, 5000); // 5 seconds slowly fades to the next alert
    return () => window.clearInterval(interval);
  }, [activeHighCritical.length]);
  
  const currentAlert = activeHighCritical[activeAlertIndex >= activeHighCritical.length ? 0 : activeAlertIndex];

  const weatherTop = weatherConditions.slice(0, 6);

  const ALL_COUNTIES = ["Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit", "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya", "Taita-Taveta", "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir", "West Pokot"];

  const countyRisks = useMemo(() => {
    const map: Record<string, string> = {};
    ALL_COUNTIES.forEach(c => map[c] = 'safe');
    
    risks.forEach(r => {
      if (!r.county_name) return;
      const current = map[r.county_name];
      if (!current) {
          map[r.county_name] = r.risk_level;
      } else if (severityRank[r.risk_level] > severityRank[current as RiskLevel]) {
          map[r.county_name] = r.risk_level;
      }
    });
    return map;
  }, [risks, ALL_COUNTIES]);

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
                <Link href='/dashboard' className='public-alert-link'>
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
        <h1>Kenya's first AI-powered disaster early warning system</h1>
        <p>
          Safeguard AI continuously monitors satellite data and weather patterns to predict and alert Kenyan communities about impending disasters before they strike.
        </p>
        <div className='hero-cta'>
          <Link href='/register' className='hero-primary'>Get Free Alerts</Link>
          <Link href='/dashboard' className='hero-secondary'>View Live Map</Link>
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

      {/* Professional Emergency Alert Banner */}
      {currentAlert && (
        <div style={{
          width: '100%',
          background: 'linear-gradient(90deg, #450a0a 0%, #7f1d1d 50%, #450a0a 100%)',
          borderTop: '2px solid #ef4444',
          borderBottom: '2px solid #ef4444',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          gap: '20px',
          boxShadow: '0 8px 24px rgba(220, 38, 38, 0.25)',
          zIndex: 40,
          position: 'relative',
          flexWrap: 'wrap'
        }}>
          <div style={{
            background: '#ef4444',
            color: '#fff',
            padding: '6px 14px',
            borderRadius: '4px',
            fontWeight: 800,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexShrink: 0,
            boxShadow: '0 0 12px rgba(239,68,68,0.5)'
          }}>
            <motion.span 
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
              style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#fff' }}
            />
            CRITICAL WARNING
          </div>
          
          <div style={{ flex: 1, minWidth: '280px', position: 'relative' }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={currentAlert.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.4 }}
                style={{ color: '#fef2f2', fontSize: '1rem', lineHeight: '1.4' }}
              >
                <strong style={{ color: '#fca5a5', marginRight: '8px', fontSize: '1.05rem', letterSpacing: '0.02em' }}>
                  {currentAlert.hazard_type.toUpperCase()} IN {currentAlert.ward_name.toUpperCase()}, {currentAlert.county_name?.toUpperCase()}:
                </strong>
                <span style={{ fontWeight: 400 }}>{currentAlert.summary}</span>
              </motion.div>
            </AnimatePresence>
          </div>
          
          {activeHighCritical.length > 1 && (
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexShrink: 0 }}>
              {activeHighCritical.map((_, i) => (
                <div 
                  key={i} 
                  style={{ 
                    width: '6px', 
                    height: '6px', 
                    borderRadius: '50%', 
                    background: i === (activeAlertIndex >= activeHighCritical.length ? 0 : activeAlertIndex) ? '#fca5a5' : 'rgba(252, 165, 165, 0.2)',
                    transition: 'background 0.3s'
                  }} 
                />
              ))}
            </div>
          )}
        </div>
      )}

      <section id='live-threats' className='public-feed'>
        <div className='section-head'>
          <h2>Live Calamity Feed</h2>
          <div className='filter-row' style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '16px' }}>
            {['All', 'Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Murang\'a', 'Turkana', 'Kilifi', 'Busia', 'Tana River', 'Mandera'].map((filter) => (
              <button
                key={filter}
                type='button'
                className={`filter-pill ${countyFilter === filter ? 'filter-pill-active' : ''}`}
                onClick={() => setCountyFilter(filter)}
                style={{
                  background: countyFilter === filter ? '#3b82f6' : 'rgba(59, 130, 246, 0.1)',
                  color: countyFilter === filter ? '#fff' : '#60a5fa',
                  border: '1px solid rgba(59, 130, 246, 0.2)',
                  padding: '6px 14px',
                  borderRadius: '20px',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        <div className='public-feed-grid'>
          <AnimatePresence mode='popLayout'>
            {displayRisks.map((risk) => {
              const hazard = getHazardType(risk.hazard_type);
              const dotColor = risk.risk_level === 'critical' ? '#ef4444' : risk.risk_level === 'high' ? '#f97316' : risk.risk_level === 'medium' ? '#f59e0b' : '#22c55e';
              
              return (
                <motion.article
                  key={`${risk.id}-${rotationIndex}`}
                  layout
                  initial={{ opacity: 0, scale: 0.95, y: -20 }}
                  animate={{ y: 0, opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, y: 20, scale: 0.95 }}
                  transition={{ duration: 0.4 }}
                  className='public-feed-card'
                >
                  <div className='feed-card-title'>
                    <div>
                      <h3 style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>{hazardIcon[hazard]}</span> {risk.hazard_type}
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: dotColor, display: 'inline-block' }} title={risk.county_name} />
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
                    <div className='probability-fill' style={{ width: probabilityWidth(risk.risk_score), backgroundColor: dotColor }} />
                  </div>
                  <p className='feed-summary'>{risk.summary}</p>
                </motion.article>
              );
            })}
          </AnimatePresence>
        </div>
        
        {/* National 47-County Summary Strip */}
        <div style={{ marginTop: '32px', padding: '24px', background: 'rgba(0,0,0,0.25)', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <h3 style={{ fontSize: '0.85rem', color: '#9ca3af', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>National 47-County Coverage Status</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
            {ALL_COUNTIES.map(c => {
               const level = (countyRisks[c] || 'safe') as RiskLevel;
               const colors = { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', safe: '#22c55e' };
               const sizes = { critical: '24px', high: '20px', medium: '16px', safe: '14px' };
               return (
                 <div 
                   key={c} 
                   title={`${c}: ${level.toUpperCase()}`} 
                   style={{ width: sizes[level], height: sizes[level], backgroundColor: colors[level], borderRadius: '4px', transition: 'all 0.3s' }} 
                 />
               );
            })}
          </div>
        </div>

        <Link className='view-all-link' href='/dashboard' style={{ display: 'block', marginTop: '24px' }}>View all threats</Link>
      </section>

      <section className='public-map-preview'>
        <div className='section-head'>
          <h2>Map Preview</h2>
          <p>Click to open full public live map</p>
        </div>
        <Link href='/dashboard' className='map-preview-link' aria-label='Open public live map'>
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
        <span>Google Gemini AI</span>
        <span>Africa&apos;s Talking</span>
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
