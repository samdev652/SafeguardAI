'use client';

import { CircleMarker, MapContainer, TileLayer } from 'react-leaflet';

interface RegisterWardMapProps {
  latitude: number;
  longitude: number;
}

export default function RegisterWardMap({ latitude, longitude }: RegisterWardMapProps) {
  return (
    <MapContainer
      center={[latitude, longitude]}
      zoom={12}
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
      <CircleMarker
        center={[latitude, longitude]}
        radius={10}
        pathOptions={{ color: '#00d4aa', fillColor: '#00d4aa', fillOpacity: 0.35, weight: 2 }}
      />
      <CircleMarker
        center={[latitude, longitude]}
        radius={20}
        pathOptions={{ color: '#00d4aa', fillColor: '#00d4aa', fillOpacity: 0.1, weight: 1 }}
      />
    </MapContainer>
  );
}
