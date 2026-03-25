'use client';

import { MapContainer, TileLayer, CircleMarker, Popup, GeoJSON } from 'react-leaflet';
import { Fragment } from 'react';
import type { Layer } from 'leaflet';
import type { FeatureCollection } from 'geojson';
import { RiskAssessment, WardHeatmapFeatureCollection } from '@/lib/types';

interface RiskMapProps {
  risks: RiskAssessment[];
  heatmap?: WardHeatmapFeatureCollection | null;
}

function riskColor(level: string): string {
  if (level === 'critical') return '#EF4444';
  if (level === 'high') return '#f97316';
  if (level === 'medium') return '#F59E0B';
  return '#00D4AA';
}

function markerRadius(level: string): number {
  if (level === 'critical') return 14;
  if (level === 'high') return 12;
  if (level === 'medium') return 10;
  return 8;
}

function projectedSpreadDistance(level: string): number {
  if (level === 'critical') return 0.03;
  if (level === 'high') return 0.022;
  if (level === 'medium') return 0.015;
  return 0.01;
}

function projectedReachDots(risk: RiskAssessment): Array<[number, number]> {
  const d = projectedSpreadDistance(risk.risk_level);
  const lat = risk.latitude;
  const lon = risk.longitude;
  const hazard = risk.hazard_type.toLowerCase();

  if (hazard.includes('flood')) {
    // Downstream-like corridor spread for flood waters.
    return [
      [lat - d * 0.4, lon + d * 0.2],
      [lat - d * 0.9, lon + d * 0.35],
      [lat - d * 1.3, lon + d * 0.1],
      [lat - d * 1.1, lon - d * 0.25],
      [lat - d * 0.6, lon - d * 0.35],
    ];
  }

  if (hazard.includes('drought')) {
    // Broad, diffuse spread across neighboring zones.
    return [
      [lat + d * 1.2, lon],
      [lat - d * 1.2, lon],
      [lat, lon + d * 1.2],
      [lat, lon - d * 1.2],
      [lat + d * 0.8, lon + d * 0.8],
      [lat - d * 0.8, lon + d * 0.8],
      [lat + d * 0.8, lon - d * 0.8],
      [lat - d * 0.8, lon - d * 0.8],
    ];
  }

  if (hazard.includes('landslide')) {
    // Elongated runout zone down a slope direction.
    return [
      [lat - d * 0.3, lon + d * 0.15],
      [lat - d * 0.8, lon + d * 0.28],
      [lat - d * 1.2, lon + d * 0.42],
      [lat - d * 1.5, lon + d * 0.55],
    ];
  }

  if (hazard.includes('earthquake')) {
    // Radial impact pattern for quake tremors.
    return [
      [lat + d, lon],
      [lat - d, lon],
      [lat, lon + d],
      [lat, lon - d],
      [lat + d * 0.7, lon + d * 0.7],
      [lat - d * 0.7, lon + d * 0.7],
      [lat + d * 0.7, lon - d * 0.7],
      [lat - d * 0.7, lon - d * 0.7],
    ];
  }

  // Offsets approximate nearby potential impact corridors around the source.
  return [
    [lat + d, lon + d * 0.2],
    [lat - d * 0.7, lon + d],
    [lat + d * 0.6, lon - d],
    [lat - d, lon - d * 0.3],
  ];
}

export default function RiskMap({ risks, heatmap }: RiskMapProps) {
  const center: [number, number] = risks.length
    ? [risks[0].latitude, risks[0].longitude]
    : [-1.286389, 36.817223];

  return (
    <MapContainer center={center} zoom={7} style={{ width: '100%', height: '100%' }} scrollWheelZoom>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors &copy; CARTO'
        url='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      />
      {heatmap ? (
        <GeoJSON
          data={heatmap as FeatureCollection}
          style={(feature) => ({
            color: '#ffffff',
            opacity: 0.28,
            weight: 0.8,
            fillColor: riskColor((feature?.properties as { risk_level?: string })?.risk_level || 'safe'),
            fillOpacity: 0.26,
          })}
          onEachFeature={(feature, layer: Layer) => {
            const props = feature.properties as {
              ward_name: string;
              county_name: string;
              risk_level: string;
              risk_score: number;
              hazard_type: string;
            };
            (layer as Layer & { bindPopup: (content: string) => void }).bindPopup(
              `<strong>${props.ward_name}</strong><br/>County: ${props.county_name}<br/>Risk: ${props.risk_level.toUpperCase()} (${props.risk_score.toFixed(1)}%)<br/>Hazard: ${props.hazard_type}`
            );
          }}
        />
      ) : null}
      {risks.map((risk) => (
        <Fragment key={`risk-fragment-${risk.id}`}>
          <CircleMarker
            key={`risk-${risk.id}`}
            center={[risk.latitude, risk.longitude]}
            radius={markerRadius(risk.risk_level)}
            pathOptions={{
              color: riskColor(risk.risk_level),
              fillColor: riskColor(risk.risk_level),
              fillOpacity: 0.38,
              weight: 2,
              className: `threat-marker marker-${risk.risk_level}`,
            }}
          >
            <Popup>
              <strong>{risk.hazard_type.toUpperCase()}</strong>
              <br />
              {risk.ward_name} / {risk.village_name || 'County zone'}
              <br />
              Risk: {risk.risk_level.toUpperCase()} ({Math.round(risk.risk_score)}%)
              <br />
              <em style={{ fontSize: '11px', color: '#a7b6d2' }}>
                What to do now: {risk.guidance_en || risk.summary}
              </em>
            </Popup>
          </CircleMarker>

          {projectedReachDots(risk).map((point, index) => (
            <CircleMarker
              key={`risk-${risk.id}-reach-${index}`}
              center={point}
              radius={5}
              pathOptions={{
                color: riskColor(risk.risk_level),
                fillColor: riskColor(risk.risk_level),
                fillOpacity: 0.2,
                opacity: 0.85,
                weight: 1,
              }}
            >
              <Popup>
                <strong>Projected Reach</strong>
                <br />
                {risk.hazard_type.toUpperCase()} may extend to nearby areas.
              </Popup>
            </CircleMarker>
          ))}
        </Fragment>
      ))}
    </MapContainer>
  );
}
