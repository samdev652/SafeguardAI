'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { fetchPublicCoverageStats, PublicCoverageStats } from '@/lib/api';

const CoverageMap = dynamic(() => import('@/components/CoverageMap'), { ssr: false });

const processSteps = [
  {
    number: '01',
    icon: '📡',
    title: 'Data collected',
    description:
      'Safeguard AI ingests weather, geospatial, and field observations across Kenya in near real-time. This gives the system broad visibility before hazards escalate.',
  },
  {
    number: '02',
    icon: '✨',
    title: 'Gemini AI analyzes',
    description:
      'Gemini AI evaluates hazard signals, trend changes, and local context for each ward. The model converts raw data into understandable risk intelligence.',
  },
  {
    number: '03',
    icon: '📊',
    title: 'Risk score generated',
    description:
      'Each area receives a risk level from safe to critical, plus confidence and guidance. County teams can quickly identify which locations need action first.',
  },
  {
    number: '04',
    icon: '📲',
    title: 'Alert dispatched',
    description:
      'People in affected areas receive alerts through SMS, WhatsApp, and push channels. Messages are plain-language and actionable to support rapid decisions.',
  },
  {
    number: '05',
    icon: '🚑',
    title: 'Rescue routed',
    description:
      'When risk becomes severe, response teams see location-specific intelligence instantly. Nearest rescue units are surfaced for faster dispatch and coordination.',
  },
] as const;

const faqs = [
  {
    q: 'Is it free?',
    a: 'Yes. Public risk alerts are free for citizens. County and partner workflows can include advanced coordination features.',
  },
  {
    q: 'How accurate is it?',
    a: 'Accuracy varies by hazard type and data quality, but Safeguard AI continuously recalibrates using new observations and historical patterns.',
  },
  {
    q: 'What languages?',
    a: 'Alerts are available in English and Swahili, with language preference set during registration.',
  },
  {
    q: 'How do I unsubscribe?',
    a: 'You can stop alerts from your settings or by sending the channel-specific opt-out keyword when provided in the message.',
  },
  {
    q: 'What data do you collect?',
    a: 'We collect only essential profile and location context needed for targeted alerts and response coordination. We do not sell personal data.',
  },
  {
    q: 'How fast are alerts sent?',
    a: 'Critical alerts are dispatched as soon as risk thresholds are crossed, typically within seconds of model confirmation.',
  },
] as const;

export default function HowItWorksPage() {
  const [coverage, setCoverage] = useState<PublicCoverageStats | null>(null);
  const [faqOpen, setFaqOpen] = useState<number | null>(0);

  useEffect(() => {
    fetchPublicCoverageStats()
      .then(setCoverage)
      .catch(() => setCoverage({ type: 'FeatureCollection', features: [], counties: [], total_registered_users: 0 }));
  }, []);

  const topCounties = useMemo(() => {
    if (!coverage) return [];
    return [...coverage.counties].sort((a, b) => b.registered_users - a.registered_users).slice(0, 4);
  }, [coverage]);

  return (
    <main className='public-root'>
      <header className='public-nav public-nav-stuck'>
        <div className='public-logo'>Safeguard AI</div>
        <nav className='public-nav-links'>
          <Link href='/'>Home</Link>
          <Link href='/threats'>Live threats</Link>
          <Link href='/register'>Get alerts</Link>
        </nav>
        <div className='public-nav-cta'>
          <Link href='/signin' className='public-signin'>Sign in</Link>
          <Link href='/register' className='public-get-alerts'>Get free alerts</Link>
        </div>
      </header>

      <section className='how-hero'>
        <p className='how-accent'>How Safeguard AI Works</p>
        <h1>From early signals to life-saving action in five steps.</h1>
        <p>
          Built for citizens, county officials, and humanitarian partners, Safeguard AI turns complex hazard data into
          clear, timely alerts and coordinated response decisions.
        </p>
      </section>

      <section className='how-process'>
        <div className='section-head'>
          <h2>Process Flow</h2>
        </div>
        <div className='how-process-grid'>
          {processSteps.map((step, index) => (
            <motion.article
              key={step.number}
              className='how-step-card'
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.22 }}
              transition={{ delay: index * 0.06, duration: 0.35 }}
            >
              <span className='how-step-number'>{step.number}</span>
              <h3>
                <span>{step.icon}</span> {step.title}
              </h3>
              <p>{step.description}</p>
            </motion.article>
          ))}
        </div>
      </section>

      <section className='how-alert-preview'>
        <div className='section-head'>
          <h2>What an alert looks like</h2>
        </div>
        <div className='how-phones'>
          <article className='phone-mock'>
            <header>
              <strong>SMS Alert</strong>
              <span>Safeguard AI</span>
            </header>
            <div className='phone-bubble'>
              FLOOD ALERT: Westlands risk now HIGH (86%). Move to higher ground. Avoid flooded roads. Call local
              rescue: +254700000001.
            </div>
          </article>
          <article className='phone-mock'>
            <header>
              <strong>WhatsApp Alert</strong>
              <span>Safeguard AI Bot</span>
            </header>
            <div className='phone-bubble phone-bubble-whatsapp'>
              ⚠️ Landslide risk rising in Elgeyo-Marakwet. Nenda maeneo salama mara moja. Reply SOS for rapid support.
            </div>
          </article>
        </div>
      </section>

      <section className='how-coverage'>
        <div className='section-head'>
          <h2>Coverage map</h2>
          <p>{coverage ? `${coverage.total_registered_users.toLocaleString()} registered users` : 'Loading coverage'}</p>
        </div>
        <div className='how-coverage-map'>
          {coverage ? <CoverageMap coverage={coverage} /> : <div className='how-coverage-loading'>Loading map...</div>}
        </div>
        <div className='how-county-list'>
          {topCounties.map((county) => (
            <article key={county.county_name}>
              <strong>{county.county_name}</strong>
              <span>{county.registered_users.toLocaleString()} users</span>
            </article>
          ))}
        </div>
      </section>

      <section className='how-faq'>
        <div className='section-head'>
          <h2>FAQ</h2>
        </div>
        <div className='how-faq-list'>
          {faqs.map((item, index) => {
            const open = faqOpen === index;
            return (
              <article key={item.q} className='how-faq-item'>
                <button type='button' onClick={() => setFaqOpen(open ? null : index)}>
                  <span>{item.q}</span>
                  <strong>{open ? '−' : '+'}</strong>
                </button>
                <motion.div
                  initial={false}
                  animate={{ height: open ? 'auto' : 0, opacity: open ? 1 : 0 }}
                  transition={{ duration: 0.22 }}
                  className='how-faq-answer'
                >
                  <p>{item.a}</p>
                </motion.div>
              </article>
            );
          })}
        </div>
      </section>

      <section className='how-cta'>
        <h2>Join 12,000 Kenyans already protected</h2>
        <Link href='/register' className='hero-primary'>
          Get free alerts
        </Link>
      </section>
    </main>
  );
}
