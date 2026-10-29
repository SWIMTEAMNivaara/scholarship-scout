import os
import requests

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"

class TinyFishError(RuntimeError):
    pass

def _headers():
    key = os.getenv("TINYFISH_API_KEY", "").strip()
    if not key:
        raise TinyFishError("TINYFISH_API_KEY is missing. Add it to .env and restart Streamlit.")
    return {"X-API-Key": key, "Accept": "application/json"}

def search(query, purpose, location="IN", language="en", page=0):
    params = {
        "query": query,
        "purpose": purpose,
        "location": location,
        "language": language,
        "page": page,
    }
    response = requests.get(SEARCH_URL, headers=_headers(), params=params, timeout=45)
    if not response.ok:
        raise TinyFishError(f"TinyFish Search returned HTTP {response.status_code}: {response.text[:400]}")
    payload = response.json()
    results = payload.get("results", [])
    return results if isinstance(results, list) else []

def fetch(urls, purpose):
    if not urls:
        return []
    body = {"urls": urls[:10], "format": "markdown", "purpose": purpose}
    response = requests.post(
        FETCH_URL,
        headers={**_headers(), "Content-Type": "application/json"},
        json=body,
        timeout=110,
    )
    if not response.ok:
        raise TinyFishError(f"TinyFish Fetch returned HTTP {response.status_code}: {response.text[:400]}")
    payload = response.json()
    return payload.get("results", []) if isinstance(payload.get("results", []), list) else []
