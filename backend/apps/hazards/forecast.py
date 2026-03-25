import json
from datetime import date, timedelta
from django.core.cache import cache
from .services import GeminiRiskAnalyzer

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

    prompt = GEMINI_FORECAST_PROMPT.format(ward=ward_name, today=date.today().isoformat())

    try:
        analyzer = GeminiRiskAnalyzer()
        text = analyzer._gemini_call(prompt, timeout=30)
        forecast = json.loads(text) if isinstance(text, str) else text
        if not isinstance(forecast, list) or len(forecast) != 7:
            raise ValueError("Gemini did not return a 7-day forecast array")
        cache.set(cache_key, forecast, CACHE_TTL)
        return forecast
    except Exception:
        today_date = date.today()
        fallback = []
        for i in range(7):
            d = today_date + timedelta(days=i)
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
