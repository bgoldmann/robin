"""
People OSINT orchestrator for Robin.
Runs person-centric investigation: validate input, expand queries, search (dark + Telegram + clear web),
optional people APIs, filter, scrape, build profile, generate people summary.
"""
from typing import List, Dict, Any, Optional, Tuple

from utils import logger, extract_iocs, merge_iocs
from people_utils import validate_person_input, normalize_person_input
from llm import expand_person_queries, filter_results, generate_people_summary
from search import get_search_results
from scrape import scrape_multiple
from clear_web_search import get_clear_web_results
from config import (
    CLEAR_WEB_SEARCH_ENABLED,
    DUCKDUCKGO_ENABLED,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    CLEAR_WEB_MAX_RESULTS,
    CLEAR_WEB_TIMEOUT,
    PEOPLE_APIS_ENABLED,
    HUNTER_API_KEY,
    EMAILREP_API_KEY,
    HIBP_API_KEY,
)

try:
    from people_apis import fetch_people_api_profiles, fetch_people_api_snippets
except ImportError:
    fetch_people_api_profiles = None
    fetch_people_api_snippets = None


def _build_profile(
    person_input: Dict[str, Any],
    scraped_urls: List[str],
    all_iocs: Dict[str, List[str]],
    api_snippets: List[str],
    social_links: List[str],
) -> Dict[str, Any]:
    """Build person profile dict for report and summary."""
    profile: Dict[str, Any] = {
        "name": person_input.get("name"),
        "aliases": [],
        "emails": list(person_input.get("emails") or []),
        "usernames": list(person_input.get("usernames") or []),
        "phones": list(person_input.get("phones") or []),
        "social_links": list(social_links or []),
        "dark_web_mentions": list(scraped_urls or []),
        "iocs": dict(all_iocs) if all_iocs else {},
        "api_snippets": list(api_snippets or []),
    }
    return profile


def run_people_investigation(
    llm,
    person_input: Dict[str, Any],
    threads: int = 5,
    extract_iocs_flag: bool = False,
    include_telegram: bool = False,
    include_clear_web: bool = True,
    skip_health_check: bool = False,
    rotate_circuit: bool = False,
    rotate_interval: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, str]], Dict[str, str], str, Dict[str, List[str]]]:
    """
    Run a people-centric OSINT investigation.
    Returns: (person_input, profile, search_results_list, scraped_results, summary, all_iocs).
    """
    # 1) Query expansion
    expanded = expand_person_queries(llm, person_input)
    dark_queries = expanded.get("dark_web") or []
    clear_queries = expanded.get("clear_web") or []

    # 2) Dark web + Telegram
    all_search_results: List[Dict[str, str]] = []
    seen_links: set = set()
    for q in dark_queries[:5]:
        query_str = (q.replace(" ", "+") if isinstance(q, str) else str(q)).replace(" ", "+")
        try:
            results = get_search_results(
                query_str,
                max_workers=threads,
                include_telegram=include_telegram,
                skip_health_check=skip_health_check,
            )
            for r in results:
                link = r.get("link")
                if link and link not in seen_links:
                    seen_links.add(link)
                    all_search_results.append(r)
        except Exception as e:
            logger.warning(f"Dark/TG search failed for query '{q[:50]}': {e}")

    # 3) Clear-web
    if include_clear_web and CLEAR_WEB_SEARCH_ENABLED and clear_queries:
        use_google = bool(GOOGLE_API_KEY and GOOGLE_CSE_ID)
        for q in clear_queries[:5]:
            query_str = q if isinstance(q, str) else str(q)
            try:
                clear_results = get_clear_web_results(
                    query_str,
                    max_results=CLEAR_WEB_MAX_RESULTS,
                    use_duckduckgo=DUCKDUCKGO_ENABLED,
                    use_google_cse=use_google,
                    google_api_key=GOOGLE_API_KEY or "",
                    google_cse_id=GOOGLE_CSE_ID or "",
                    timeout=CLEAR_WEB_TIMEOUT,
                )
                for r in clear_results:
                    link = r.get("link")
                    if link and link not in seen_links:
                        seen_links.add(link)
                        all_search_results.append(r)
            except Exception as e:
                logger.warning(f"Clear-web search failed for '{query_str[:50]}': {e}")

    # 4) People APIs (snippets + social links)
    api_snippets: List[str] = []
    social_links: List[str] = []
    if PEOPLE_APIS_ENABLED and (HUNTER_API_KEY or EMAILREP_API_KEY or HIBP_API_KEY):
        emails = person_input.get("emails") or []
        if fetch_people_api_profiles and emails:
            try:
                api_data = fetch_people_api_profiles(
                    emails,
                    hunter_api_key=HUNTER_API_KEY or "",
                    emailrep_api_key=EMAILREP_API_KEY or "",
                )
                social_links = api_data.get("social_links") or []
                api_snippets = api_data.get("api_snippets") or []
            except Exception as e:
                logger.warning(f"People API profiles failed: {e}")
        if fetch_people_api_snippets and emails:
            try:
                extra = fetch_people_api_snippets(
                    emails,
                    hunter_api_key=HUNTER_API_KEY or "",
                    emailrep_api_key=EMAILREP_API_KEY or "",
                    hibp_api_key=HIBP_API_KEY or "",
                )
                for s in extra:
                    if s and s not in api_snippets:
                        api_snippets.append(s)
            except Exception as e:
                logger.warning(f"People API snippets failed: {e}")

    # 5) Filter and scrape
    primary_query = dark_queries[0] if dark_queries else (clear_queries[0] if clear_queries else "person")
    search_filtered = filter_results(llm, primary_query, all_search_results)
    if not search_filtered:
        search_filtered = all_search_results[:20]
    scraped_results = scrape_multiple(
        search_filtered,
        max_workers=threads,
        rotate=rotate_circuit,
        rotate_interval=rotate_interval,
    )

    # 6) IOCs
    all_iocs: Dict[str, List[str]] = {}
    if extract_iocs_flag:
        for url, content in scraped_results.items():
            iocs = extract_iocs(content)
            if iocs:
                all_iocs = merge_iocs(all_iocs, iocs)

    # 7) Profile
    profile = _build_profile(
        person_input,
        list(scraped_results.keys()),
        all_iocs,
        api_snippets,
        social_links,
    )

    # 8) People summary
    summary = generate_people_summary(llm, person_input, scraped_results, profile)

    return person_input, profile, all_search_results, scraped_results, summary, all_iocs
