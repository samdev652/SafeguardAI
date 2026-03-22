import { RiskAssessment, RescueUnit, RiskLevel, WardHeatmapFeatureCollection } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function parseRiskResponse(response: Response): Promise<RiskAssessment[]> {
  if (!response.ok) throw new Error('Failed to fetch risks');
  return response.json();
}

export async function fetchCurrentRisks(ward?: string): Promise<RiskAssessment[]> {
  const query = ward ? `?ward=${encodeURIComponent(ward)}` : '';
  const primaryResponse = await fetch(`${API_BASE_URL}/api/risk/current/${query}`, {
    cache: 'no-store',
  });

  if (primaryResponse.ok) {
    return parseRiskResponse(primaryResponse);
  }

  // Backward-compatible fallback while older backend path is still in use.
  const fallbackResponse = await fetch(`${API_BASE_URL}/api/hazards/risks/${query}`, {
    cache: 'no-store',
  });
  return parseRiskResponse(fallbackResponse);
}

export interface PublicRiskCount {
  active_threat_count: number;
}

export interface PublicStats {
  counties_covered: number;
  alerts_sent_today: number;
  prediction_accuracy: number;
}

export interface PublicWeatherCondition {
  id: number;
  ward_name: string;
  county_name: string | null;
  hazard_type: string;
  severity_index: number;
  temperature_c: number | null;
  precipitation_mm: number | null;
  wind_speed_kmh: number | null;
  observed_at: string;
  impact_summary: string;
}

export async function fetchPublicRiskCount(): Promise<PublicRiskCount> {
  const response = await fetch(`${API_BASE_URL}/api/risk/count/`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to fetch public risk count');
  return response.json();
}

export async function fetchPublicStats(): Promise<PublicStats> {
  const response = await fetch(`${API_BASE_URL}/api/stats/public/`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to fetch public stats');
  return response.json();
}

export async function fetchPublicWeatherConditions(limit = 12): Promise<PublicWeatherCondition[]> {
  const response = await fetch(`${API_BASE_URL}/api/risk/weather-conditions/?limit=${limit}`, {
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch public weather conditions');
  return response.json();
}

export interface CoverageFeature {
  type: 'Feature';
  geometry: GeoJSON.Geometry;
  properties: {
    ward_name: string;
    county_name: string;
    county_user_count: number;
    ward_user_count: number;
  };
}

export interface PublicCoverageStats {
  type: 'FeatureCollection';
  features: CoverageFeature[];
  counties: Array<{
    county_name: string;
    registered_users: number;
  }>;
  total_registered_users: number;
}

export async function fetchPublicCoverageStats(): Promise<PublicCoverageStats> {
  const response = await fetch(`${API_BASE_URL}/api/stats/coverage/`, { cache: 'no-store' });
  if (!response.ok) throw new Error('Failed to fetch public coverage stats');
  return response.json();
}

export async function fetchLatestRisks(ward?: string): Promise<RiskAssessment[]> {
  return fetchCurrentRisks(ward);
}

export async function fetchNearestRescueUnits(latitude: number, longitude: number): Promise<RescueUnit[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/rescue/units/nearest/?latitude=${latitude}&longitude=${longitude}`,
    { cache: 'no-store' }
  );
  if (!response.ok) throw new Error('Failed to fetch rescue units');
  return response.json();
}

export interface RescueResponderHeartbeatPayload {
  latitude: number;
  longitude: number;
  is_available_for_dispatch?: boolean;
  unit_type?: string;
}

export async function updateRescueResponderHeartbeat(
  token: string,
  payload: RescueResponderHeartbeatPayload
): Promise<RescueUnit> {
  const response = await fetch(`${API_BASE_URL}/api/rescue/responders/heartbeat/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to update responder heartbeat');
  return response.json();
}

export async function dispatchSos(token: string, description: string): Promise<{ rescue_request_id: number }> {
  const response = await fetch(`${API_BASE_URL}/api/rescue/sos/dispatch/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ description }),
  });
  if (!response.ok) throw new Error('Failed to dispatch SOS');
  return response.json();
}

export interface DispatchQueueItem {
  id: number;
  status: 'pending' | 'dispatched' | 'resolved';
  description: string;
  created_at: string;
  dispatched_at: string | null;
  citizen_name: string;
  citizen_phone_number: string;
  ward_name: string;
  village_name: string;
  latitude: number;
  longitude: number;
}

export async function fetchDispatchQueue(token: string): Promise<DispatchQueueItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/rescue/dispatch-queue/`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch dispatch queue');
  return response.json();
}

export async function acceptDispatch(token: string, requestId: number): Promise<DispatchQueueItem> {
  const response = await fetch(`${API_BASE_URL}/api/rescue/dispatch-queue/${requestId}/accept/`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Failed to accept dispatch');
  return response.json();
}

export interface PersonalAlert {
  id: number;
  message: string;
  channel: 'sms' | 'whatsapp' | 'push';
  status: 'pending' | 'sent' | 'failed';
  created_at: string;
}

export async function fetchMyAlerts(token: string): Promise<PersonalAlert[]> {
  const response = await fetch(`${API_BASE_URL}/api/alerts/my/`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch personal alerts');
  return response.json();
}

export function riskEventsUrl(): string {
  return `${API_BASE_URL}/api/hazards/risks/events/`;
}

export async function fetchWardHeatmap(county?: string): Promise<WardHeatmapFeatureCollection> {
  const query = county ? `?county=${encodeURIComponent(county)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/hazards/risks/ward-heatmap/${query}`, {
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch ward heatmap');
  return response.json();
}

export interface RegisterCitizenPayload {
  full_name: string;
  email: string;
  password: string;
  phone_number: string;
  ward_name: string;
  village_name?: string;
  preferred_language: 'en' | 'sw';
  channels: string[];
  latitude: number;
  longitude: number;
}

export async function registerCitizen(payload: RegisterCitizenPayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/citizens/register/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const firstError = Object.values(data)[0];
    const errorMessage = Array.isArray(firstError) ? String(firstError[0]) : 'Registration failed';
    throw new Error(errorMessage);
  }
}

export interface LocationSearchResult {
  id: number;
  ward_name: string;
  county_name: string;
  latitude: number;
  longitude: number;
}

export async function searchLocations(query: string): Promise<LocationSearchResult[]> {
  const response = await fetch(`${API_BASE_URL}/api/locations/search/?q=${encodeURIComponent(query)}`, {
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to search locations');
  return response.json();
}

export interface OtpSendResponse {
  detail: string;
  phone: string;
  channel?: 'sms' | 'whatsapp';
  dev_otp?: string;
  provider: {
    sent: boolean;
    provider: string;
    reason?: string;
    response?: string;
  };
}

export async function sendRegistrationOtp(phone: string, channel: 'sms' | 'whatsapp' = 'sms'): Promise<OtpSendResponse> {
  const response = await fetch(`${API_BASE_URL}/api/alerts/otp/send/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phone, channel }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const phoneError = Array.isArray(data?.phone) ? data.phone[0] : data?.phone;
    const message = (data && (data.detail || phoneError)) || 'Could not send OTP';
    throw new Error(String(message));
  }
  return response.json();
}

export async function verifyRegistrationOtp(phone: string, otp: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/alerts/otp/verify/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ phone, otp }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(String(data.detail || data.otp?.[0] || 'OTP verification failed'));
  }
}

export interface AlertSubscriptionResponse {
  detail: string;
  ward_name: string;
  risk_level: RiskLevel;
  channels: string[];
}

export async function subscribeToAlerts(payload: {
  ward_id: number;
  phone: string;
  channels: string[];
}): Promise<AlertSubscriptionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/alerts/subscribe/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(String(data.detail || data.ward_id?.[0] || data.phone?.[0] || 'Subscription failed'));
  }
  return response.json();
}

export interface CountyOverviewResponse {
  county: string;
  metrics: {
    active_threats: number;
    alerts_sent_today: number;
    registered_users: number;
    open_incidents: number;
  };
  chart: Array<{
    date: string;
    flood: number;
    landslide: number;
    drought: number;
    earthquake: number;
    other: number;
  }>;
  recent_risks: Array<{
    id: number;
    location: string;
    type: string;
    risk_level: RiskLevel;
    probability: number;
    time: string;
  }>;
}

export async function fetchCountyOverview(token: string, county?: string): Promise<CountyOverviewResponse> {
  const query = county ? `?county=${encodeURIComponent(county)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/county/overview/${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch county overview');
  return response.json();
}

export async function acknowledgeRisk(token: string, riskId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/risk/${riskId}/acknowledge/`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error('Failed to acknowledge risk');
}

export interface CountyAlertHistoryItem {
  id: number;
  county_name: string;
  ward_name: string;
  hazard_type: string;
  risk_level: string;
  channel: 'sms' | 'whatsapp' | 'push';
  status: 'pending' | 'sent' | 'failed';
  message: string;
  created_at: string;
  sent_at: string | null;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export async function fetchCountyAlertHistory(
  token: string,
  params: Record<string, string>
): Promise<PaginatedResponse<CountyAlertHistoryItem>> {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${API_BASE_URL}/api/alerts/history/?${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch alert history');
  return response.json();
}

export function countyAlertsExportUrl(county: string): string {
  return `${API_BASE_URL}/api/alerts/export/?county=${encodeURIComponent(county)}&format=csv`;
}

export interface IncidentReport {
  id: number;
  county_name: string;
  ward_name: string;
  location_name: string;
  latitude: number;
  longitude: number;
  photo_url: string;
  description: string;
  status: 'open' | 'in_progress' | 'resolved';
  internal_notes: string;
  created_at: string;
  updated_at: string;
}

export async function fetchCountyIncidents(token: string, county?: string): Promise<IncidentReport[]> {
  const query = county ? `?county=${encodeURIComponent(county)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/alerts/incidents/${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch incidents');
  return response.json();
}

export async function updateIncidentReport(
  token: string,
  id: number,
  payload: Partial<Pick<IncidentReport, 'status' | 'internal_notes'>>
): Promise<IncidentReport> {
  const response = await fetch(`${API_BASE_URL}/api/alerts/incidents/${id}/`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to update incident report');
  return response.json();
}

export interface DispatchLogItem {
  id: number;
  ward_name: string;
  status: 'pending' | 'dispatched' | 'resolved';
  description: string;
  hazard_type: string | null;
  created_at: string;
  dispatched_at: string | null;
}

export async function fetchCountyDispatchLog(token: string, county?: string): Promise<DispatchLogItem[]> {
  const query = county ? `?county=${encodeURIComponent(county)}` : '';
  const response = await fetch(`${API_BASE_URL}/api/alerts/dispatch-log/${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch dispatch log');
  return response.json();
}

export interface CountyUser {
  id: number;
  full_name: string;
  phone_number: string;
  ward_name: string;
  village_name: string;
  preferred_language: string;
  channels: string[];
  role: string;
  created_at: string;
}

export async function fetchCountyUsers(token: string): Promise<CountyUser[]> {
  const response = await fetch(`${API_BASE_URL}/api/citizens/county-users/`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!response.ok) throw new Error('Failed to fetch county users');
  return response.json();
}
