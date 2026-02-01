import time
import requests
import random, re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from requests.exceptions import (
    RequestException,
    ConnectionError,
    Timeout,
    HTTPError,
    ProxyError
)

from utils import logger, create_session_with_retry, retry_with_backoff
from tor_pool import get_tor_pool
from config import SEARCH_TIMEOUT

try:
    from telegram_osint import get_telegram_results, is_telegram_configured
except ImportError:
    get_telegram_results = None
    is_telegram_configured = lambda: False

import warnings
warnings.filterwarnings("ignore")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
]

# Search engine configuration with metadata
SEARCH_ENGINES = {
    "ahmia": {
        "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 1,
        "name": "Ahmia"
    },
    "onionland": {
        "url": "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 1,
        "name": "OnionLand"
    },
    "darkrunt": {
        "url": "http://darkhuntyla64h75a3re5e2l3367lqn7ltmdzpgmr6b4nbz3q2iaxrid.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "DarkRunt"
    },
    "torgle": {
        "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",
        "query_param": "query",
        "enabled": True,
        "priority": 1,
        "name": "Torgle"
    },
    "amnesia": {
        "url": "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",
        "query_param": "query",
        "enabled": True,
        "priority": 2,
        "name": "Amnesia"
    },
    "kaizer": {
        "url": "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Kaizer"
    },
    "anima": {
        "url": "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Anima"
    },
    "tornado": {
        "url": "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Tornado"
    },
    "tornet": {
        "url": "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "TorNet"
    },
    "torland": {
        "url": "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Torland"
    },
    "findtor": {
        "url": "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Find Tor"
    },
    "excavator": {
        "url": "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",
        "query_param": "query",
        "enabled": True,
        "priority": 2,
        "name": "Excavator"
    },
    "onionway": {
        "url": "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}",
        "query_param": "s",
        "enabled": True,
        "priority": 2,
        "name": "Onionway"
    },
    "tor66": {
        "url": "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",
        "query_param": "q",
        "enabled": True,
        "priority": 2,
        "name": "Tor66"
    },
    "oss": {
        "url": "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}",
        "query_param": "search",
        "enabled": True,
        "priority": 2,
        "name": "OSS (Onion Search Server)"
    },
}

# Backward compatibility: Generate endpoint list from dictionary
SEARCH_ENGINE_ENDPOINTS = [
    engine["url"] for engine in SEARCH_ENGINES.values() if engine["enabled"]
]

# Search engine health tracking
_engine_health = {}
_engine_stats = {}

def get_tor_proxies(port: Optional[int] = None) -> Dict[str, str]:
    """
    Get Tor proxy configuration.
    
    Args:
        port: Optional specific port (uses TorPool if None)
    
    Returns:
        Dictionary with HTTP and HTTPS proxy settings
    """
    tor_pool = get_tor_pool()
    return tor_pool.get_proxy_for_request(prefer_port=port)


def verify_tor_connection() -> bool:
    """
    Verify that Tor is running and accessible.
    
    Returns:
        True if Tor is accessible, False otherwise
    """
    try:
        proxies = get_tor_proxies()
        # Try to connect to a test endpoint through Tor
        response = requests.get(
            "http://check.torproject.org/",
            proxies=proxies,
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Tor connection verification failed: {e}")
        return False


def check_search_engine_health(engine_id: str, engine_config: Dict) -> bool:
    """
    Check health of a search engine.
    
    Args:
        engine_id: Engine identifier
        engine_config: Engine configuration dictionary
        
    Returns:
        True if engine is healthy, False otherwise
    """
    if not engine_config.get("enabled", True):
        return False
    
    # Check cache first (cache for 5 minutes)
    cache_key = f"health_{engine_id}"
    if cache_key in _engine_health:
        cached_time, cached_result = _engine_health[cache_key]
        if time.time() - cached_time < 300:  # 5 minute cache
            return cached_result
    
    try:
        # Test with a simple query
        test_query = "test"
        url = engine_config["url"].format(query=test_query)
        proxies = get_tor_proxies()
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        
        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=10,
            allow_redirects=False
        )
        
        # Consider healthy if we get any response (even 404 is better than timeout)
        is_healthy = response.status_code in [200, 404, 403]  # 403 might be rate limit, but engine exists
        
        # Cache result
        _engine_health[cache_key] = (time.time(), is_healthy)
        
        # Update statistics
        if engine_id not in _engine_stats:
            _engine_stats[engine_id] = {"checks": 0, "healthy": 0}
        _engine_stats[engine_id]["checks"] += 1
        if is_healthy:
            _engine_stats[engine_id]["healthy"] += 1
        
        return is_healthy
    except Exception as e:
        logger.debug(f"Health check failed for {engine_id}: {e}")
        _engine_health[cache_key] = (time.time(), False)
        if engine_id not in _engine_stats:
            _engine_stats[engine_id] = {"checks": 0, "healthy": 0}
        _engine_stats[engine_id]["checks"] += 1
        return False


def get_enabled_search_engines(skip_health_check: bool = False) -> List[tuple]:
    """
    Get list of enabled search engines, sorted by priority and health.
    
    Args:
        skip_health_check: If True, skip health check and return all enabled engines
            by priority only (faster startup when engines are known good).
    
    Returns:
        List of (engine_id, engine_config) tuples
    """
    enabled = [
        (engine_id, config)
        for engine_id, config in SEARCH_ENGINES.items()
        if config.get("enabled", True)
    ]
    
    # Sort by priority (lower number = higher priority)
    enabled.sort(key=lambda x: x[1].get("priority", 999))
    
    if skip_health_check:
        return enabled
    
    # Check health and prioritize healthy engines
    healthy = []
    unhealthy = []
    for engine_id, config in enabled:
        if check_search_engine_health(engine_id, config):
            healthy.append((engine_id, config))
        else:
            unhealthy.append((engine_id, config))
    
    # Return healthy engines first, then unhealthy
    return healthy + unhealthy

@retry_with_backoff(max_retries=3, backoff_factor=0.5, exceptions=(ConnectionError, Timeout, ProxyError))
def fetch_search_results(endpoint: str, query: str) -> List[Dict[str, str]]:
    """
    Fetch search results from a single search engine endpoint.
    
    Args:
        endpoint: Search engine endpoint URL template
        query: Search query string
        
    Returns:
        List of dictionaries with 'title' and 'link' keys
    """
    url = endpoint.format(query=query)
    headers = {
        "User-Agent": random.choice(USER_AGENTS)
    }
    proxies = get_tor_proxies()
    
    # Extract port for statistics tracking
    port_used = None
    try:
        port_used = int(proxies["http"].split(":")[-1])
    except (ValueError, IndexError):
        pass
    
    session = create_session_with_retry(max_retries=2, timeout=(10, SEARCH_TIMEOUT))
    
    try:
        response = session.get(url, headers=headers, proxies=proxies, timeout=SEARCH_TIMEOUT)
        response.raise_for_status()
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = []
            for a in soup.find_all('a'):
                try:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)
                    if not href or not title:
                        continue
                    
                    # Extract onion links
                    link_matches = re.findall(r'https?:\/\/[^\/]*\.onion[^\s<>"{}|\\^`\[\]]*', href)
                    if link_matches:
                        links.append({"title": title, "link": link_matches[0]})
                except (KeyError, AttributeError, IndexError) as e:
                    logger.debug(f"Error parsing link element: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error parsing link: {e}")
                    continue
            
            logger.debug(f"Fetched {len(links)} results from {endpoint[:50]}...")
            # Record success in Tor pool
            if port_used:
                tor_pool = get_tor_pool()
                tor_pool.record_success(port_used)
            return links
        else:
            logger.warning(f"Non-200 status code {response.status_code} from {endpoint[:50]}...")
            if port_used:
                tor_pool = get_tor_pool()
                tor_pool.record_failure(port_used)
            return []
            
    except Timeout as e:
        logger.warning(f"Timeout fetching results from {endpoint[:50]}...: {e}")
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []
    except ConnectionError as e:
        logger.warning(f"Connection error fetching results from {endpoint[:50]}...: {e}")
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []
    except ProxyError as e:
        logger.error(f"Proxy error (Tor issue?) fetching results from {endpoint[:50]}...: {e}")
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []
    except HTTPError as e:
        logger.warning(f"HTTP error {e.response.status_code} from {endpoint[:50]}...: {e}")
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []
    except RequestException as e:
        logger.warning(f"Request error fetching results from {endpoint[:50]}...: {e}")
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching results from {endpoint[:50]}...: {e}", exc_info=True)
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
        return []

def get_search_results(
    refined_query: str,
    max_workers: int = 5,
    include_telegram: bool = False,
    skip_health_check: bool = False,
) -> List[Dict[str, str]]:
    """
    Get search results from all configured search engines (and optionally Telegram).

    Tor engines and Telegram (when include_telegram and configured) run in the same
    executor; results are merged and deduplicated by link.
    
    Args:
        refined_query: Search query string.
        max_workers: Number of concurrent workers.
        include_telegram: Whether to include Telegram OSINT results.
        skip_health_check: If True, skip engine health check for faster startup.
    """
    logger.info(f"Starting search with query: {refined_query[:100]}...")
    
    # Verify Tor connection before starting
    if not verify_tor_connection():
        logger.warning("Tor connection verification failed, but continuing anyway...")
    
    # Get enabled engines (sorted by priority and health, unless skip_health_check)
    enabled_engines = get_enabled_search_engines(skip_health_check=skip_health_check)
    logger.info(f"Using {len(enabled_engines)} enabled search engines")
    
    # Build tasks: Tor engines + optional Telegram
    tasks = [
        ("tor", engine_id, engine_config)
        for engine_id, engine_config in enabled_engines
    ]
    if include_telegram and get_telegram_results and is_telegram_configured():
        tasks.append(("telegram", "telegram", None))
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {}
        for kind, engine_id, engine_config in tasks:
            if kind == "telegram":
                future_to_task[executor.submit(get_telegram_results, refined_query, 50)] = (
                    "telegram",
                    {"name": "Telegram"},
                )
            else:
                future_to_task[
                    executor.submit(fetch_search_results, engine_config["url"], refined_query)
                ] = (engine_id, engine_config)
        
        for future in as_completed(future_to_task):
            engine_id, engine_config = future_to_task[future]
            try:
                result_urls = future.result()
                if result_urls is None:
                    result_urls = []
                results.extend(result_urls)
                if engine_id not in _engine_stats:
                    _engine_stats[engine_id] = {"requests": 0, "successes": 0, "results": 0}
                _engine_stats[engine_id]["requests"] += 1
                _engine_stats[engine_id]["successes"] += 1
                _engine_stats[engine_id]["results"] += len(result_urls)
            except Exception as e:
                logger.error(f"Error getting results from {engine_config.get('name', engine_id)}: {e}")
                if engine_id not in _engine_stats:
                    _engine_stats[engine_id] = {"requests": 0, "successes": 0, "results": 0}
                _engine_stats[engine_id]["requests"] += 1

    # Deduplicate results based on the link
    seen_links: set = set()
    unique_results = []
    for res in results:
        link = res.get("link")
        if link and link not in seen_links:
            seen_links.add(link)
            unique_results.append(res)
    
    logger.info(f"Found {len(unique_results)} unique results from {len(tasks)} source(s)")
    return unique_results