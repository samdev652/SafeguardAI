'use client';

import { MapContainer, TileLayer, CircleMarker } from 'react-leaflet';
import { RiskAssessment } from '@/lib/types';

function riskColor(level: string): string {
  if (level === 'critical') return '#EF4444';
  if (level === 'high') return '#F97316';
  if (level === 'medium') return '#F59E0B';
  return '#00D4AA';
}

function markerRadius(level: string): number {
  if (level === 'critical') return 9;
  if (level === 'high') return 8;
  if (level === 'medium') return 7;
  return 6;
}

export default function PublicMapPreview({ risks }: { risks: RiskAssessment[] }) {
  const center: [number, number] = risks.length
    ? [risks[0].latitude, risks[0].longitude]
    : [-1.286389, 36.817223];

  return (
    <MapContainer
      center={center}
      zoom={6}
      style={{ width: '100%', height: '100%' }}
      dragging={false}
      scrollWheelZoom={false}
      doubleClickZoom={false}
      zoomControl={false}
      attributionControl={false}
      keyboard={false}
      touchZoom={false}
      boxZoom={false}
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors &copy; CARTO'
        url='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      />
      {risks.map((risk) => (
        <CircleMarker
          key={risk.id}
          center={[risk.latitude, risk.longitude]}
          radius={markerRadius(risk.risk_level)}
          pathOptions={{
            color: riskColor(risk.risk_level),
            fillColor: riskColor(risk.risk_level),
            fillOpacity: 0.36,
            weight: 1.5,
            className: `threat-marker marker-${risk.risk_level}`,
          }}
        />
      ))}
    </MapContainer>
  );
}
