"""
Optional people APIs for Robin People Search mode.
Hunter, EmailRep, HIBP (breach presence only). Each returns normalized structure
for profile aggregation. Only call when PEOPLE_APIS_ENABLED and keys are set.
"""
import requests
from typing import List, Dict, Any, Optional

from utils import logger


def _request(
    method: str,
    url: str,
    timeout: int = 10,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    try:
        r = requests.request(
            method,
            url,
            headers=headers or {},
            params=params,
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json() if r.text else {}
        if r.status_code == 404:
            return None
        logger.debug(f"API {url[:50]} status {r.status_code}")
        return None
    except Exception as e:
        logger.debug(f"API request failed {url[:50]}: {e}")
        return None


def hunter_domain_search(api_key: str, domain: str) -> Dict[str, Any]:
    """
    Hunter domain search: emails associated with domain.
    Returns { source: "hunter", profiles: [{email, type}], raw: {...} }.
    """
    if not api_key or not domain:
        return {"source": "hunter", "profiles": [], "raw": {}}
    url = "https://api.hunter.io/v2/domain-search"
    params = {"domain": domain.strip(), "api_key": api_key}
    data = _request("GET", url, params=params)
    if not data:
        return {"source": "hunter", "profiles": [], "raw": {}}
    profiles = []
    for e in (data.get("data") or {}).get("emails") or []:
        email = (e.get("value") or e.get("email") or "").strip()
        if email:
            profiles.append({"email": email, "type": (e.get("type") or "unknown")})
    return {"source": "hunter", "profiles": profiles, "raw": data}


def hunter_email_verifier(api_key: str, email: str) -> Dict[str, Any]:
    """Hunter email verifier: validity and score. Returns normalized snippet."""
    if not api_key or not email:
        return {"source": "hunter", "profiles": [], "raw": {}}
    url = "https://api.hunter.io/v2/email-verifier"
    params = {"email": email.strip(), "api_key": api_key}
    data = _request("GET", url, params=params)
    if not data:
        return {"source": "hunter", "profiles": [], "raw": {}}
    d = (data.get("data") or {})
    score = d.get("score")
    result = d.get("result", "")
    snippet = f"Hunter: {result} (score {score})" if score is not None else f"Hunter: {result}"
    return {"source": "hunter", "profiles": [], "raw": data, "snippet": snippet}


def emailrep_query(api_key: str, email: str) -> Dict[str, Any]:
    """
    EmailRep.io query: reputation and linked profiles.
    API: GET https://emailrep.io/{email} with X-Api-Key header.
    Returns { source: "emailrep", profiles: [urls], raw: {...}, snippet: str }.
    """
    if not email:
        return {"source": "emailrep", "profiles": [], "raw": {}}
    url = f"https://emailrep.io/{email.strip()}"
    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key
    data = _request("GET", url, headers=headers or None)
    if not data:
        return {"source": "emailrep", "profiles": [], "raw": {}}
    profiles = []
    for d in (data.get("details") or {}).get("profiles") or []:
        if isinstance(d, str):
            profiles.append(d)
        elif isinstance(d, dict) and d.get("url"):
            profiles.append(d["url"])
    snippet = f"EmailRep: reputation {data.get('reputation', 'N/A')}"
    if data.get("suspicious"):
        snippet += "; suspicious"
    return {"source": "emailrep", "profiles": profiles, "raw": data, "snippet": snippet}


def hibp_breach_check(api_key: str, email: str) -> Dict[str, Any]:
    """
    HIBP breached account check. Returns only breach presence (no raw breach data).
    { source: "hibp", breached: bool, count: int, snippet: str }.
    """
    if not email:
        return {"source": "hibp", "breached": False, "count": 0, "snippet": "HIBP: not checked"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email.strip()}"
    headers = {"hibp-api-key": api_key} if api_key else {}
    # Without key, HIBP returns 401; we treat as "not checked"
    data = _request("GET", url, headers=headers)
    if data is None:
        return {"source": "hibp", "breached": False, "count": 0, "snippet": "HIBP: not checked (or API key required)"}
    count = len(data) if isinstance(data, list) else 0
    snippet = f"HIBP: account in {count} breach(es)" if count else "HIBP: no known breaches"
    return {"source": "hibp", "breached": count > 0, "count": count, "snippet": snippet}


def fetch_people_api_snippets(
    emails: List[str],
    hunter_api_key: str = "",
    emailrep_api_key: str = "",
    hibp_api_key: str = "",
) -> List[str]:
    """
    Call enabled people APIs for given emails and return list of one-line snippets
    for profile aggregation. Respects missing keys (skips that API).
    """
    snippets: List[str] = []
    for email in (emails or [])[:5]:
        if hunter_api_key:
            res = hunter_email_verifier(hunter_api_key, email)
            if res.get("snippet"):
                snippets.append(res["snippet"])
        if emailrep_api_key:
            res = emailrep_query(emailrep_api_key, email)
            if res.get("snippet"):
                snippets.append(res["snippet"])
        if hibp_api_key:
            res = hibp_breach_check(hibp_api_key, email)
            if res.get("snippet") and "not checked" not in res["snippet"].lower():
                snippets.append(res["snippet"])
    return snippets


def fetch_people_api_profiles(
    emails: List[str],
    hunter_api_key: str = "",
    emailrep_api_key: str = "",
) -> Dict[str, Any]:
    """
    Gather structured profile data from Hunter and EmailRep (social profiles, etc.)
    for person profile. Returns dict with social_links, api_snippets, and raw per source.
    """
    social_links: List[str] = []
    api_snippets: List[str] = []
    for email in (emails or [])[:5]:
        if emailrep_api_key:
            res = emailrep_query(emailrep_api_key, email)
            for p in res.get("profiles") or []:
                if p and p not in social_links:
                    social_links.append(p)
            if res.get("snippet"):
                api_snippets.append(res["snippet"])
        if hunter_api_key:
            domain = email.split("@")[-1] if "@" in email else ""
            if domain:
                res = hunter_domain_search(hunter_api_key, domain)
                for p in res.get("profiles") or []:
                    em = p.get("email") if isinstance(p, dict) else p
                    if em and em not in [email]:
                        pass  # could add to emails list
                if res.get("profiles"):
                    api_snippets.append(f"Hunter: {len(res['profiles'])} email(s) for domain {domain}")
    return {"social_links": social_links, "api_snippets": api_snippets}
