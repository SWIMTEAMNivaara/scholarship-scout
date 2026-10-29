import re
from urllib.parse import urlparse


def _first(patterns, text, flags=re.IGNORECASE | re.MULTILINE):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            return " ".join(value.split()).strip(" .,:;")
    return ""


def _clean_text(value, limit=500):
    return " ".join((value or "").split()).strip()[:limit]


def build_scholarship_record(search_result, page, profile):
    title = _clean_text(page.get("title") or search_result.get("title") or "Scholarship opportunity", 240)
    text = page.get("text") or ""
    description = page.get("description") or search_result.get("snippet") or ""
    source_url = page.get("final_url") or page.get("url") or search_result.get("url", "")
    domain = urlparse(source_url).netloc.replace("www.", "")

    deadline = _first([
        r"(?:last date|application deadline|closing date|deadline|apply before|applications close)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})",
        r"(?:last date|application deadline|closing date|deadline|apply before|applications close)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?:last date|application deadline|closing date|deadline)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
    ], text)
    income = _first([
        r"(?:family|annual household|parental|parents'? annual|annual family)\s+(?:income|income limit)\s*(?:must be|should be|of|not exceed|below|less than|up to)?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\s*(?:lakh|lakhs|LPA))?)",
        r"(?:income limit|family income|annual income)\s*[:\-]?\s*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\s*(?:lakh|lakhs|LPA))?)",
    ], text)
    benefits = _first([
        r"(?:scholarship amount|award amount|financial assistance|scholarship worth|benefit of|amount of scholarship)\s*[:\-]?\s*([^\.\n]{5,180})",
        r"(up to\s+₹?\s?[\d,]+(?:\s*(?:per annum|per year|annually|monthly))?[^\.\n]{0,100})",
        r"(₹\s?[\d,]+\s*(?:per annum|per year|annually|monthly))",
    ], text)
    docs = _first([
        r"(?:documents required|required documents|documents needed)\s*[:\-]?\s*([^\n]{10,320})",
    ], text)
    academic = _first([
        r"((?:minimum|at least|not less than|aggregate of)[^\.\n]{0,100}\d{2,3}(?:\.\d+)?\s*%)",
        r"(\d{2,3}(?:\.\d+)?\s*%[^\.\n]{0,90}(?:minimum marks|or above|and above))",
    ], text)
    eligibility = _first([
        r"(?:eligibility criteria|who can apply|eligible candidates|eligibility)\s*[:\-]?\s*([^\n]{20,420})",
    ], text)
    provider = _first([
        r"(?:provided by|offered by|scholarship provider|administered by)\s*[:\-]?\s*([^\.\n]{3,120})",
    ], text)
    cycle = _first([
        r"(20\d{2}\s*[-–/]\s*20\d{2})",
        r"((?:academic|application) year\s*[:\-]?\s*20\d{2}(?:\s*[-–/]\s*20\d{2})?)",
    ], text)
    application_url = page.get("application_url") or page.get("apply_url") or ""
    if not str(application_url).startswith("http"):
        application_url = ""

    return {
        "name": title, "title": title, "url": source_url,
        "application_url": application_url,
        "source_name": domain or search_result.get("site_name", "Search result"),
        "provider": provider, "summary": _clean_text(description, 500),
        "snippet": search_result.get("snippet", ""), "deadline": deadline or "",
        "application_cycle": cycle or "", "income_limit": income or "",
        "benefits": benefits or "", "documents": docs or "",
        "academic_criteria": academic or "", "eligibility_text": eligibility or "",
        "page_text_excerpt": text[:16000],
        "detail_extraction_note": "Fields are extracted from available page text and may be incomplete. Verify every detail on the provider's official page.",
    }
