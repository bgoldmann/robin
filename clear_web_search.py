"""
Clear-web search for Robin People Search mode.
Returns results in the same shape as dark web search: list of {title, link}.
Supports DuckDuckGo (no key) and optional Google Custom Search.
"""
import time
from typing import List, Dict

from utils import logger

try:
    from duckduckgo_search import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    _DDGS_AVAILABLE = False


def get_duckduckgo_results(query: str, max_results: int = 20, timeout: int = 15) -> List[Dict[str, str]]:
    """Fetch clear-web results from DuckDuckGo. Returns list of {title, link}."""
    if not _DDGS_AVAILABLE:
        logger.warning("duckduckgo-search not installed. pip install duckduckgo-search")
        return []
    results: List[Dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = (r.get("title") or "").strip()
                link = (r.get("href") or r.get("link") or "").strip()
                if link:
                    results.append({"title": title or link[:80], "link": link})
        logger.debug(f"DuckDuckGo returned {len(results)} results for query: {query[:50]}")
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
    return results


def get_google_cse_results(
    query: str,
    api_key: str,
    cse_id: str,
    max_results: int = 20,
    timeout: int = 15,
) -> List[Dict[str, str]]:
    """Fetch clear-web results from Google Custom Search JSON API. Returns list of {title, link}."""
    import requests
    results: List[Dict[str, str]] = []
    if not api_key or not cse_id:
        return results
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": min(max_results, 10),
    }
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items") or []:
            link = (item.get("link") or "").strip()
            title = (item.get("title") or "").strip()
            if link:
                results.append({"title": title or link[:80], "link": link})
        logger.debug(f"Google CSE returned {len(results)} results for query: {query[:50]}")
    except Exception as e:
        logger.warning(f"Google CSE search failed: {e}")
    return results


def get_clear_web_results(
    query: str,
    max_results: int = 20,
    use_duckduckgo: bool = True,
    use_google_cse: bool = False,
    google_api_key: str = "",
    google_cse_id: str = "",
    timeout: int = 15,
) -> List[Dict[str, str]]:
    """
    Get clear-web search results in same shape as dark web: [{title, link}].
    Deduplicates by link. Respects rate limits with a short delay between back-to-back calls.
    """
    seen: set = set()
    combined: List[Dict[str, str]] = []
    if use_duckduckgo and _DDGS_AVAILABLE:
        for res in get_duckduckgo_results(query, max_results=max_results, timeout=timeout):
            link = res.get("link")
            if link and link not in seen:
                seen.add(link)
                combined.append(res)
        time.sleep(0.5)
    if use_google_cse and google_api_key and google_cse_id:
        for res in get_google_cse_results(
            query, google_api_key, google_cse_id, max_results=max_results, timeout=timeout
        ):
            link = res.get("link")
            if link and link not in seen:
                seen.add(link)
                combined.append(res)
    return combined
