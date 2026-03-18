'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import Image from 'next/image';
import { useEffect, useMemo, useState } from 'react';
import { useSession } from 'next-auth/react';
import {
  acknowledgeRisk,
  countyAlertsExportUrl,
  CountyAlertHistoryItem,
  CountyOverviewResponse,
  CountyUser,
  DispatchLogItem,
  fetchCountyAlertHistory,
  fetchCountyDispatchLog,
  fetchCountyIncidents,
  fetchCountyOverview,
  fetchCountyUsers,
  fetchCurrentRisks,
  IncidentReport,
  updateIncidentReport,
} from '@/lib/api';
import { RiskAssessment } from '@/lib/types';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const RiskMap = dynamic(() => import('@/components/RiskMap'), { ssr: false });

export type CountyTab =
  | 'overview'
  | 'active-threats'
  | 'alert-history'
  | 'registered-users'
  | 'incident-reports'
  | 'dispatch-log'
  | 'settings';

const tabMeta: Array<{ key: CountyTab; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'active-threats', label: 'Active threats' },
  { key: 'alert-history', label: 'Alert history' },
  { key: 'registered-users', label: 'Registered users' },
  { key: 'incident-reports', label: 'Incident reports' },
  { key: 'dispatch-log', label: 'Dispatch log' },
  { key: 'settings', label: 'Settings' },
];

function riskBadgeClass(level: string): string {
  if (level === 'critical') return 'badge-critical';
  if (level === 'high') return 'badge-high';
  if (level === 'medium') return 'badge-medium';
  return 'badge-safe';
}

export default function CountyPortalPage({ section }: { section: CountyTab }) {
  const { data: session, status } = useSession();
  const token = session?.accessToken as string | undefined;

  const [overview, setOverview] = useState<CountyOverviewResponse | null>(null);
  const [countyRisks, setCountyRisks] = useState<RiskAssessment[]>([]);
  const [history, setHistory] = useState<CountyAlertHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyCount, setHistoryCount] = useState(0);
  const [users, setUsers] = useState<CountyUser[]>([]);
  const [incidents, setIncidents] = useState<IncidentReport[]>([]);
  const [dispatchLog, setDispatchLog] = useState<DispatchLogItem[]>([]);
  const [busyRiskIds, setBusyRiskIds] = useState<number[]>([]);

  const [historyStartDate, setHistoryStartDate] = useState('');
  const [historyEndDate, setHistoryEndDate] = useState('');
  const [historyHazard, setHistoryHazard] = useState('');
  const [historyChannel, setHistoryChannel] = useState('');
  const [historyRiskLevel, setHistoryRiskLevel] = useState('');

  useEffect(() => {
    if (status !== 'authenticated' || !token || session?.role !== 'county_official') return;

    fetchCountyOverview(token)
      .then(setOverview)
      .catch(() => setOverview(null));

    fetchCountyUsers(token)
      .then(setUsers)
      .catch(() => setUsers([]));

    fetchCountyIncidents(token)
      .then(setIncidents)
      .catch(() => setIncidents([]));

    fetchCountyDispatchLog(token)
      .then(setDispatchLog)
      .catch(() => setDispatchLog([]));
  }, [status, token, session?.role]);

  useEffect(() => {
    if (!overview) return;
    fetchCurrentRisks()
      .then((allRisks) =>
        setCountyRisks(allRisks.filter((risk) => (risk.county_name || '').toLowerCase() === overview.county.toLowerCase()))
      )
      .catch(() => setCountyRisks([]));
  }, [overview]);

  useEffect(() => {
    if (status !== 'authenticated' || !token || session?.role !== 'county_official') return;
    fetchCountyAlertHistory(token, {
      page: String(historyPage),
      ...(historyStartDate ? { start_date: historyStartDate } : {}),
      ...(historyEndDate ? { end_date: historyEndDate } : {}),
      ...(historyHazard ? { hazard_type: historyHazard } : {}),
      ...(historyChannel ? { channel: historyChannel } : {}),
      ...(historyRiskLevel ? { risk_level: historyRiskLevel } : {}),
    })
      .then((response) => {
        setHistory(response.results);
        setHistoryCount(response.count);
      })
      .catch(() => {
        setHistory([]);
        setHistoryCount(0);
      });
  }, [
    status,
    token,
    session?.role,
    historyPage,
    historyStartDate,
    historyEndDate,
    historyHazard,
    historyChannel,
    historyRiskLevel,
  ]);

  const exportUrl = useMemo(() => {
    if (!overview) return '#';
    return countyAlertsExportUrl(overview.county);
  }, [overview]);

  async function onAcknowledge(riskId: number) {
    if (!token) return;
    setBusyRiskIds((prev) => [...prev, riskId]);
    try {
      await acknowledgeRisk(token, riskId);
    } finally {
      setBusyRiskIds((prev) => prev.filter((id) => id !== riskId));
    }
  }

  async function onIncidentUpdate(reportId: number, patch: Partial<Pick<IncidentReport, 'status' | 'internal_notes'>>) {
    if (!token) return;
    const updated = await updateIncidentReport(token, reportId, patch);
    setIncidents((prev) => prev.map((item) => (item.id === reportId ? updated : item)));
  }

  if (status === 'loading') {
    return <main className='county-loading'>Loading county portal...</main>;
  }

  if (status !== 'authenticated' || session?.role !== 'county_official') {
    return (
      <main className='county-loading'>
        County officials only. <Link href='/signin'>Sign in</Link>
      </main>
    );
  }

  return (
    <main className='county-root'>
      <aside className='county-sidebar'>
        <div className='county-brand'>Safeguard AI</div>
        <p className='county-subtitle'>County Portal</p>
        <nav>
          {tabMeta.map((item) => (
            <Link
              key={item.key}
              className={`county-nav-item ${section === item.key ? 'county-nav-item-active' : ''}`}
              href={`/county/${item.key}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <Link className='county-home-link' href='/'>
          Back to public site
        </Link>
      </aside>

      <section className='county-main'>
        {section === 'overview' ? (
          <>
            <header className='county-head'>
              <h1>County Overview {overview ? `- ${overview.county}` : ''}</h1>
              <p>Analytics and decision support for county disaster teams.</p>
            </header>

            <div className='county-metric-grid'>
              <article>
                <span>Active threats</span>
                <strong>{overview?.metrics.active_threats ?? 0}</strong>
              </article>
              <article>
                <span>Alerts sent today</span>
                <strong>{overview?.metrics.alerts_sent_today ?? 0}</strong>
              </article>
              <article>
                <span>Registered users</span>
                <strong>{overview?.metrics.registered_users ?? 0}</strong>
              </article>
              <article>
                <span>Open incidents</span>
                <strong>{overview?.metrics.open_incidents ?? 0}</strong>
              </article>
            </div>

            <section className='county-chart-card'>
              <h2>7-day Alerts by Calamity Type</h2>
              <div className='county-chart-wrap'>
                <ResponsiveContainer width='100%' height={320}>
                  <AreaChart data={overview?.chart || []}>
                    <defs>
                      <linearGradient id='floodGradient' x1='0' y1='0' x2='0' y2='1'>
                        <stop offset='5%' stopColor='#00d4aa' stopOpacity={0.8} />
                        <stop offset='95%' stopColor='#00d4aa' stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray='3 3' stroke='#22344f' />
                    <XAxis dataKey='date' stroke='#9fb6d8' />
                    <YAxis stroke='#9fb6d8' />
                    <Tooltip />
                    <Legend />
                    <Area type='monotone' dataKey='flood' stackId='1' stroke='#00d4aa' fill='url(#floodGradient)' />
                    <Area type='monotone' dataKey='landslide' stackId='1' stroke='#f59e0b' fill='#f59e0b33' />
                    <Area type='monotone' dataKey='drought' stackId='1' stroke='#f97316' fill='#f9731633' />
                    <Area type='monotone' dataKey='earthquake' stackId='1' stroke='#ef4444' fill='#ef444433' />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className='county-table-card'>
              <h2>Most Recent Risk Assessments</h2>
              <table className='county-table'>
                <thead>
                  <tr>
                    <th>Location</th>
                    <th>Type</th>
                    <th>Risk level</th>
                    <th>Probability</th>
                    <th>Time</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {(overview?.recent_risks || []).map((risk) => (
                    <tr key={risk.id}>
                      <td>{risk.location}</td>
                      <td>{risk.type}</td>
                      <td>
                        <span className={`risk-badge ${riskBadgeClass(risk.risk_level)}`}>{risk.risk_level}</span>
                      </td>
                      <td>{risk.probability}%</td>
                      <td>{new Date(risk.time).toLocaleString()}</td>
                      <td>
                        <button
                          type='button'
                          className='county-action-btn'
                          onClick={() => onAcknowledge(risk.id)}
                          disabled={busyRiskIds.includes(risk.id)}
                        >
                          {busyRiskIds.includes(risk.id) ? 'Saving...' : 'Acknowledge'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        ) : null}

        {section === 'active-threats' ? (
          <section className='county-tab-panel'>
            <h2>Active Threats - {overview?.county || 'Your county'}</h2>
            <div className='dashboard-split'>
              <div className='map-panel'>
                <RiskMap risks={countyRisks} />
              </div>
              <aside className='feed-panel'>
                <div className='feed-list'>
                  {countyRisks.map((risk) => (
                    <article key={risk.id} className='feed-card'>
                      <div className='feed-card-title'>
                        <div>
                          <h3>{risk.hazard_type}</h3>
                          <p>{risk.ward_name}</p>
                        </div>
                        <span className={`risk-badge ${riskBadgeClass(risk.risk_level)}`}>{risk.risk_level.toUpperCase()}</span>
                      </div>
                      <p className='feed-summary'>{risk.summary}</p>
                    </article>
                  ))}
                </div>
              </aside>
            </div>
          </section>
        ) : null}

        {section === 'alert-history' ? (
          <section className='county-tab-panel'>
            <h2>Alert History</h2>
            <div className='county-filter-row'>
              <input type='date' value={historyStartDate} onChange={(e) => setHistoryStartDate(e.target.value)} />
              <input type='date' value={historyEndDate} onChange={(e) => setHistoryEndDate(e.target.value)} />
              <input placeholder='Calamity type' value={historyHazard} onChange={(e) => setHistoryHazard(e.target.value)} />
              <select value={historyChannel} onChange={(e) => setHistoryChannel(e.target.value)}>
                <option value=''>All channels</option>
                <option value='sms'>SMS</option>
                <option value='whatsapp'>WhatsApp</option>
                <option value='push'>Push</option>
              </select>
              <select value={historyRiskLevel} onChange={(e) => setHistoryRiskLevel(e.target.value)}>
                <option value=''>All levels</option>
                <option value='safe'>Safe</option>
                <option value='medium'>Medium</option>
                <option value='high'>High</option>
                <option value='critical'>Critical</option>
              </select>
              <a href={exportUrl} className='county-action-btn'>
                Export CSV
              </a>
            </div>
            <table className='county-table'>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Ward</th>
                  <th>Calamity</th>
                  <th>Channel</th>
                  <th>Risk</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => (
                  <tr key={row.id}>
                    <td>{new Date(row.created_at).toLocaleString()}</td>
                    <td>{row.ward_name}</td>
                    <td>{row.hazard_type}</td>
                    <td>{row.channel.toUpperCase()}</td>
                    <td>{row.risk_level}</td>
                    <td>{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className='county-pagination'>
              <button type='button' onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}>
                Prev
              </button>
              <span>
                Page {historyPage} of {Math.max(1, Math.ceil(historyCount / 20))}
              </span>
              <button type='button' onClick={() => setHistoryPage((p) => p + 1)}>
                Next
              </button>
            </div>
          </section>
        ) : null}

        {section === 'registered-users' ? (
          <section className='county-tab-panel'>
            <h2>Registered Users ({users.length})</h2>
            <table className='county-table'>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Ward</th>
                  <th>Language</th>
                  <th>Channels</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.full_name}</td>
                    <td>{user.phone_number}</td>
                    <td>{user.ward_name}</td>
                    <td>{user.preferred_language.toUpperCase()}</td>
                    <td>{(user.channels || []).join(', ')}</td>
                    <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        {section === 'incident-reports' ? (
          <section className='county-tab-panel'>
            <h2>Incident Reports</h2>
            <div className='county-incident-grid'>
              {incidents.map((incident) => (
                <article key={incident.id} className='county-incident-card'>
                  <div className='county-incident-photo'>
                    {incident.photo_url ? (
                      <Image src={incident.photo_url} alt='Incident evidence' fill sizes='(max-width: 1120px) 100vw, 30vw' />
                    ) : (
                      <span>No photo</span>
                    )}
                  </div>
                  <p>{incident.description}</p>
                  <small>{incident.location_name || `${incident.ward_name} - ${incident.county_name}`}</small>
                  <small>{new Date(incident.created_at).toLocaleString()}</small>
                  <select
                    value={incident.status}
                    onChange={(e) => onIncidentUpdate(incident.id, { status: e.target.value as IncidentReport['status'] })}
                  >
                    <option value='open'>Open</option>
                    <option value='in_progress'>In Progress</option>
                    <option value='resolved'>Resolved</option>
                  </select>
                  <textarea
                    value={incident.internal_notes || ''}
                    placeholder='Internal notes'
                    onChange={(e) => onIncidentUpdate(incident.id, { internal_notes: e.target.value })}
                  />
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {section === 'dispatch-log' ? (
          <section className='county-tab-panel'>
            <h2>Dispatch Log</h2>
            <table className='county-table'>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Ward</th>
                  <th>Hazard</th>
                  <th>Status</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {dispatchLog.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>{item.ward_name}</td>
                    <td>{item.hazard_type || 'N/A'}</td>
                    <td>{item.status}</td>
                    <td>{item.description || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        {section === 'settings' ? (
          <section className='county-tab-panel'>
            <h2>Settings</h2>
            <p>County-level notification preferences and escalation thresholds will appear here.</p>
          </section>
        ) : null}
      </section>
    </main>
  );
}
