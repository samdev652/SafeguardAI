import os
import requests

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL') or 'gemini-pro'

if not GEMINI_API_KEY:
    raise ValueError('GEMINI_API_KEY is not set in the environment.')

print(f"Using GEMINI_MODEL={GEMINI_MODEL}")
print(f"Using GEMINI_API_KEY={'*' * len(GEMINI_API_KEY) if GEMINI_API_KEY else None}")

url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}'
payload = {
    'contents': [{'parts': [{'text': 'Hello from Gemini!'}]}],
    'generationConfig': {'responseMimeType': 'text/plain'},
}

try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    print('Gemini API response:', response.json())
except Exception as e:
    print('Gemini API error:', e)
    if hasattr(e, 'response') and e.response is not None:
        print('Error response:', e.response.text)
