import React from 'react';

export type RiskLevel = 'safe' | 'medium' | 'high' | 'critical';

export interface DayForecast {
  date: string;
  flood_risk_level: RiskLevel;
  landslide_risk_level: RiskLevel;
  drought_risk_level: RiskLevel;
  overall_risk_level: RiskLevel;
  summary: string;
}

function riskColor(level: RiskLevel): string {
  switch (level) {
    case 'critical':
      return '#EF4444'; // red
    case 'high':
      return '#F59E0B'; // orange
    case 'medium':
      return '#FBBF24'; // amber
    case 'safe':
    default:
      return '#22C55E'; // green
  }
}

export default function ForecastCard({ forecast }: { forecast: DayForecast[] }) {
  return (
    <div className="forecast-card" style={{ marginBottom: 24 }}>
      <h2 style={{ fontWeight: 600, fontSize: 18, marginBottom: 8 }}>7-Day Personal Risk Forecast</h2>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between' }}>
        {forecast.map((day, idx) => (
          <div
            key={day.date}
            style={{
              flex: 1,
              background: riskColor(day.overall_risk_level),
              color: '#fff',
              borderRadius: 8,
              padding: 10,
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              boxShadow: '0 1px 4px rgba(0,0,0,0.07)',
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 15 }}>{new Date(day.date).toLocaleDateString(undefined, { weekday: 'short' })}</div>
            <div style={{ fontSize: 13, margin: '2px 0 4px 0' }}>{day.summary}</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>
              <span>Flood: <b>{day.flood_risk_level}</b></span><br />
              <span>Landslide: <b>{day.landslide_risk_level}</b></span><br />
              <span>Drought: <b>{day.drought_risk_level}</b></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
