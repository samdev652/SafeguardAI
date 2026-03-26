import logging
import requests
from datetime import datetime, timedelta
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor
from math import radians, cos, sin, asin, sqrt

logger = logging.getLogger(__name__)

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance in kilometers between two points on the earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers
    return c * r

def fetch_open_meteo_current(lat: float, lon: float) -> dict:
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m&timezone=Africa%2FNairobi"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json().get('current', {})
    except Exception as e:
        logger.error(f"Open-Meteo fetch failed: {e}")
        return {}

def fetch_nasa_power_data(lat: float, lon: float) -> dict:
    cache_key = f"nasa_power:{lat}:{lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    today = datetime.utcnow()
    start_date = today - timedelta(days=30)
    end_str = today.strftime('%Y%m%d')
    start_str = start_date.strftime('%Y%m%d')

    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M,RH2M,WS2M,GWETROOT,GWETTOP&community=AG&longitude={lon}&latitude={lat}&start={start_str}&end={end_str}&format=JSON"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        props = data.get('properties', {}).get('parameter', {})
        
        if props:
            rain_values = list(props.get('PRECTOTCORR', {}).values())
            valid_rain = [v for v in rain_values if v != -999.0]
            rain_30d = sum(valid_rain) if valid_rain else 0
            rain_7d = sum(valid_rain[-7:]) if len(valid_rain) >= 7 else sum(valid_rain)
            
            prev_7d = sum(valid_rain[-14:-7]) if len(valid_rain) >= 14 else sum(valid_rain[:7])
            trend = "increasing" if rain_7d > prev_7d else "decreasing"
            
            root_sm = list(props.get('GWETROOT', {}).values())
            valid_root = [v for v in root_sm if v != -999.0]
            avg_root_sm = sum(valid_root[-7:]) / len(valid_root[-7:]) if valid_root else 0
            
            top_sm = list(props.get('GWETTOP', {}).values())
            valid_top = [v for v in top_sm if v != -999.0]
            avg_top_sm = sum(valid_top[-7:]) / len(valid_top[-7:]) if valid_top else 0

            avg_temp = 0
            t2m = list(props.get('T2M', {}).values())
            valid_temp = [v for v in t2m if v != -999.0]
            if valid_temp:
                avg_temp = sum(valid_temp[-7:]) / len(valid_temp[-7:])

            result = {
                'rain_7d_mm': round(rain_7d, 2),
                'rain_30d_mm': round(rain_30d, 2),
                'trend': trend,
                'avg_soil_moisture_root': round(avg_root_sm, 3),
                'avg_soil_moisture_top': round(avg_top_sm, 3),
                'avg_temp_7d': round(avg_temp, 1)
            }
            cache.set(cache_key, result, timeout=10800) # 3 hours
            return result
        return {}
    except Exception as e:
        logger.error(f"NASA POWER fetch failed: {e}")
        return {}

def fetch_usgs_earthquake_data(lat: float, lon: float) -> dict:
    cache_key = "usgs:kenya_earthquakes"
    quakes = cache.get(cache_key)
    
    if quakes is None:
        today = datetime.utcnow()
        start_date = today - timedelta(days=7)
        url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_date.isoformat()}Z&endtime={today.isoformat()}Z&minlatitude=-5&maxlatitude=5&minlongitude=33&maxlongitude=42&minmagnitude=2.5&orderby=time"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            quakes = response.json().get('features', [])
            cache.set(cache_key, quakes, timeout=1800) # 30 mins
        except Exception as e:
            logger.error(f"USGS fetch failed: {e}")
            quakes = []

    if not quakes:
        return {
            'recent_earthquakes_7d': 0,
            'max_magnitude': 0,
            'most_recent_time': None,
            'nearest_distance_km': None,
            'seismic_activity_detected': False
        }

    total_quakes = len(quakes)
    max_mag = max((q['properties']['mag'] for q in quakes if q['properties'].get('mag') is not None), default=0)
    most_recent = quakes[0]
    recent_time = datetime.fromtimestamp(most_recent['properties']['time']/1000).isoformat()
    
    min_dist = float('inf')
    for q in quakes:
        coords = q['geometry']['coordinates']
        q_lon, q_lat = coords[0], coords[1]
        dist = haversine(lon, lat, q_lon, q_lat)
        if dist < min_dist:
            min_dist = dist
            
    activity_detected = total_quakes >= 2 or max_mag > 3.5

    return {
        'recent_earthquakes_7d': total_quakes,
        'max_magnitude': max_mag,
        'most_recent_time': recent_time,
        'nearest_distance_km': round(min_dist, 1) if min_dist != float('inf') else None,
        'seismic_activity_detected': activity_detected
    }

def fetch_noaa_forecast_data(lat: float, lon: float) -> dict:
    cache_key = f"noaa_gfs:{lat}:{lon}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"https://api.open-meteo.com/v1/gfs?latitude={lat}&longitude={lon}&daily=precipitation_sum,precipitation_probability_max,windspeed_10m_max&timezone=Africa%2FNairobi&forecast_days=7"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        daily = data.get('daily', {})
        
        if daily:
            rain_sums = daily.get('precipitation_sum', [])
            probs = daily.get('precipitation_probability_max', [])
            winds = daily.get('windspeed_10m_max', [])
            
            result = {
                'forecast_rain_7d_mm': round(sum([r for r in rain_sums if r is not None]), 2),
                'max_rain_probability': max([p for p in probs if p is not None], default=0),
                'max_wind_speed_kmh': max([w for w in winds if w is not None], default=0),
                'daily_forecast': daily
            }
            cache.set(cache_key, result, timeout=7200) # 2 hours
            return result
        return {}
    except Exception as e:
        logger.error(f"NOAA GFS fetch failed: {e}")
        return {}

def fetch_weather_for_location(lat: float, lon: float) -> dict:
    enriched = {}
    sources_success = []
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        f_om = executor.submit(fetch_open_meteo_current, lat, lon)
        f_nasa = executor.submit(fetch_nasa_power_data, lat, lon)
        f_usgs = executor.submit(fetch_usgs_earthquake_data, lat, lon)
        f_noaa = executor.submit(fetch_noaa_forecast_data, lat, lon)
        
        try:
            om_data = f_om.result(timeout=12)
            if om_data:
                enriched['open_meteo'] = om_data
                sources_success.append("open_meteo")
        except Exception:
            enriched['open_meteo'] = {}
            
        try:
            nasa_data = f_nasa.result(timeout=12)
            if nasa_data:
                enriched['nasa_power'] = nasa_data
                sources_success.append("nasa_power")
        except Exception:
            enriched['nasa_power'] = {}
            
        try:
            usgs_data = f_usgs.result(timeout=12)
            if usgs_data:
                enriched['usgs'] = usgs_data
                sources_success.append("usgs")
        except Exception:
            enriched['usgs'] = {}
            
        try:
            noaa_data = f_noaa.result(timeout=12)
            if noaa_data:
                enriched['noaa_gfs'] = noaa_data
                sources_success.append("noaa_gfs")
        except Exception:
            enriched['noaa_gfs'] = {}

    quality_score = len(sources_success)
    if quality_score < 3:
        logger.warning(f"Data quality low for location ({lat}, {lon}): score {quality_score}/4")
        
    enriched['data_sources'] = sources_success
    enriched['data_quality_score'] = max(1, quality_score)
    return enriched
