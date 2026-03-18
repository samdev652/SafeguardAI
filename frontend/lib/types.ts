export type RiskLevel = 'safe' | 'medium' | 'high' | 'critical';

export interface RiskAssessment {
  id: number;
  ward_name: string;
  county_name?: string;
  village_name: string;
  hazard_type: string;
  risk_level: RiskLevel;
  risk_score: number;
  guidance_en: string;
  guidance_sw: string;
  summary: string;
  issued_at: string;
  latitude: number;
  longitude: number;
}

export interface RescueUnit {
  id: number;
  name: string;
  unit_type: string;
  phone_number: string;
  county: string;
  ward_name: string;
  distance_m: number;
  latitude: number;
  longitude: number;
}

export interface WardHeatmapFeature {
  type: 'Feature';
  geometry: GeoJSON.Geometry;
  properties: {
    ward_name: string;
    county_name: string;
    risk_level: RiskLevel;
    risk_score: number;
    hazard_type: string;
    issued_at: string | null;
  };
}

export interface WardHeatmapFeatureCollection {
  type: 'FeatureCollection';
  features: WardHeatmapFeature[];
}
