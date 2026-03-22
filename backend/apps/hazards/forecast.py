import json
import requests
from django.conf import settings
from django.core.cache import cache

GEMINI_FORECAST_PROMPT = (
    "You are a disaster risk analyst for Kenya. For the next 7 days, return a JSON array of 7 objects, one per day, each with keys: date (YYYY-MM-DD), flood_risk_level, landslide_risk_level, drought_risk_level, overall_risk_level, summary. "
    "Risk levels must be one of: safe, medium, high, critical. "
    "Summarize the main risk for each day in one line. "
    "Ward: {ward}. Today is {today}."
)

CACHE_PREFIX = "forecast:ward:"
CACHE_TTL = 60 * 60 * 6  # 6 hours


def get_seven_day_forecast(ward_name: str) -> list:
    cache_key = f"{CACHE_PREFIX}{ward_name.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    from datetime import date
    prompt = GEMINI_FORECAST_PROMPT.format(ward=ward_name, today=date.today().isoformat())
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        forecast = json.loads(text) if isinstance(text, str) else text
        if not isinstance(forecast, list) or len(forecast) != 7:
            raise ValueError("Gemini did not return a 7-day forecast array")
        cache.set(cache_key, forecast, CACHE_TTL)
        return forecast
    except Exception:
        # fallback: 7 days of safe
        from datetime import date, timedelta
        today = date.today()
        fallback = []
        for i in range(7):
            d = today + timedelta(days=i)
            fallback.append({
                "date": d.isoformat(),
                "flood_risk_level": "safe",
                "landslide_risk_level": "safe",
                "drought_risk_level": "safe",
                "overall_risk_level": "safe",
                "summary": "No significant risk expected.",
            })
        cache.set(cache_key, fallback, CACHE_TTL)
        return fallback
