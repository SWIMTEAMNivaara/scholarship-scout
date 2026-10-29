from scout.tinyfish_client import search, fetch

def build_queries(profile):
    state = profile.get("state", "Karnataka")
    course = profile.get("course", "undergraduate engineering")
    branch = profile.get("branch", "")
    queries = [
        f"{state} government scholarship {course} official scholarship portal",
        f"India merit based scholarship {course} undergraduate official 2026 2027",
        f"India need based scholarship undergraduate students official application",
    ]
    if branch:
        queries.append(f"India STEM engineering scholarship {branch} undergraduate official")
    return queries

def discover_scholarships(profile, limit=10):
    found = []
    seen = set()
    purpose = "Find legitimate scholarship schemes relevant to an Indian undergraduate student; prioritize official government portals and scholarship providers."
    for query in build_queries(profile):
        for result in search(query, purpose, location="IN", language="en"):
            url = (result.get("url") or "").strip()
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            result = dict(result)
            result.setdefault("query_used", query)
            found.append(result)
            if len(found) >= limit:
                return found
    return found

def fetch_scholarship_details(urls):
    purpose = "Extract scholarship name, eligibility requirements, household income limit, academic criteria, benefits, deadline, required documents, and official application links. Preserve uncertainty; do not infer missing values."
    pages = fetch(urls, purpose)
    normalized = []
    for page in pages:
        normalized.append({
            "url": page.get("url") or page.get("final_url") or "",
            "final_url": page.get("final_url") or "",
            "title": page.get("title") or "",
            "description": page.get("description") or "",
            "text": page.get("text") or "",
            "error": page.get("error"),
        })
    return normalized
