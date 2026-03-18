'use client';

import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import type { FeatureCollection } from 'geojson';
import type { Layer } from 'leaflet';
import { PublicCoverageStats } from '@/lib/api';

interface CoverageMapProps {
  coverage: PublicCoverageStats;
}

function colorByCount(count: number): string {
  if (count >= 800) return '#00d4aa';
  if (count >= 400) return '#2cb9ff';
  if (count >= 150) return '#f59e0b';
  if (count >= 50) return '#f97316';
  return '#334a69';
}

export default function CoverageMap({ coverage }: CoverageMapProps) {
  const center: [number, number] = [-0.6, 37.9];

  return (
    <div className='coverage-map-wrap'>
      <MapContainer center={center} zoom={6} style={{ width: '100%', height: '100%' }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors &copy; CARTO'
          url='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
        />
        <GeoJSON
          data={coverage as unknown as FeatureCollection}
          style={(feature) => ({
            color: '#0e1727',
            weight: 0.8,
            fillOpacity: 0.72,
            fillColor: colorByCount((feature?.properties as { county_user_count?: number })?.county_user_count || 0),
          })}
          onEachFeature={(feature, layer: Layer) => {
            const props = feature.properties as {
              county_name: string;
              ward_name: string;
              county_user_count: number;
              ward_user_count: number;
            };
            (layer as Layer & { bindPopup: (content: string) => void }).bindPopup(
              `<strong>${props.county_name}</strong><br/>Ward: ${props.ward_name}<br/>Registered users in county: ${props.county_user_count}<br/>Users in ward: ${props.ward_user_count}`
            );
          }}
        />
      </MapContainer>

      <div className='coverage-map-legend'>
        <h4>Adoption</h4>
        <ul>
          <li><span className='coverage-dot coverage-dot-low' /> Low</li>
          <li><span className='coverage-dot coverage-dot-mid' /> Medium</li>
          <li><span className='coverage-dot coverage-dot-high' /> High</li>
          <li><span className='coverage-dot coverage-dot-very-high' /> Very high</li>
        </ul>
      </div>
    </div>
  );
}
