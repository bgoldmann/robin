import random
import requests
import threading
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
from requests.exceptions import (
    RequestException,
    ConnectionError,
    Timeout,
    HTTPError,
    ProxyError
)

from utils import logger, create_session_with_retry, retry_with_backoff, log_tor_metrics
from tor_controller import init_tor_controller, TorController
from tor_pool import get_tor_pool
from config import (
    TOR_CONTROL_PORT,
    TOR_CONTROL_PASSWORD,
    TOR_ROTATE_INTERVAL,
    TOR_ROTATE_ON_ERROR,
    SCRAPE_TIMEOUT
)

import warnings
warnings.filterwarnings("ignore")

# Define a list of rotating user agents.
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

# Global counter and lock for thread-safe Tor rotation
request_counter = 0
counter_lock = threading.Lock()

# Global Tor controller instance (lazy initialization)
_tor_controller: Optional[TorController] = None
_controller_lock = threading.Lock()


def get_tor_controller() -> Optional[TorController]:
    """
    Get or initialize global Tor controller instance.
    
    Returns:
        TorController instance or None if initialization fails
    """
    global _tor_controller
    if _tor_controller is None:
        with _controller_lock:
            if _tor_controller is None:
                _tor_controller = init_tor_controller(
                    control_port=TOR_CONTROL_PORT,
                    control_password=TOR_CONTROL_PASSWORD
                )
    return _tor_controller

@retry_with_backoff(max_retries=2, backoff_factor=0.5, exceptions=(ConnectionError, Timeout, ProxyError))
def scrape_single(
    url_data: Dict[str, str],
    rotate: bool = False,
    rotate_interval: int = None,
    control_port: int = None,
    control_password: Optional[str] = None
) -> Tuple[str, str]:
    """
    Scrapes a single URL.
    If the URL is an onion site, routes the request through Tor.
    
    Args:
        url_data: Dictionary with 'link' and 'title' keys
        rotate: Whether to rotate Tor circuit
        rotate_interval: Interval for circuit rotation (uses config default if None)
        control_port: Tor control port (uses config default if None)
        control_password: Tor control password (uses config default if None)
        
    Returns:
        Tuple of (url, scraped_text)
    """
    global request_counter
    
    url = url_data.get('link', '')
    title = url_data.get('title', '')
    
    if not url:
        logger.warning("No URL provided in url_data")
        return url, title
    
    use_tor = ".onion" in url
    
    # Get proxy configuration (use TorPool if enabled, otherwise single instance)
    proxies = None
    port_used = None
    if use_tor:
        tor_pool = get_tor_pool()
        proxies = tor_pool.get_proxy_for_request()
        # Extract port from proxy URL for statistics
        try:
            port_used = int(proxies["http"].split(":")[-1])
        except (ValueError, IndexError):
            port_used = None
        
        # Handle circuit rotation if enabled
        if rotate:
            rotation_interval = rotate_interval or TOR_ROTATE_INTERVAL
            with counter_lock:
                request_counter += 1
                should_rotate = (request_counter % rotation_interval == 0)
            
            if should_rotate:
                controller = get_tor_controller()
                if controller and controller.is_connected():
                    if controller.rotate_circuit():
                        logger.debug(f"Circuit rotated before scraping {url[:50]}...")
                        # Get exit node info for logging
                        exit_info = controller.get_exit_node_info()
                        if exit_info:
                            logger.debug(f"Using exit node: {exit_info.get('nickname', 'Unknown')}")
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS)
    }
    
    session = create_session_with_retry(max_retries=2, timeout=(15, SCRAPE_TIMEOUT))
    
    try:
        response = session.get(url, headers=headers, proxies=proxies, timeout=SCRAPE_TIMEOUT)
        response.raise_for_status()
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            scraped_text = title + " " + soup.get_text(separator=' ', strip=True)
            # Clean up whitespace
            scraped_text = ' '.join(scraped_text.split())
            logger.debug(f"Successfully scraped {url[:50]}... ({len(scraped_text)} chars)")
            
            # Record success in Tor pool and log metrics
            if port_used:
                tor_pool = get_tor_pool()
                tor_pool.record_success(port_used)
                stats = tor_pool.port_stats.get(port_used, {})
                if stats.get("requests", 0) % 10 == 0:  # Log every 10 requests
                    log_tor_metrics(port_used, stats)
        else:
            logger.warning(f"Non-200 status code {response.status_code} for {url[:50]}...")
            scraped_text = title
            
    except Timeout as e:
        logger.warning(f"Timeout scraping {url[:50]}...: {e}")
        scraped_text = title
        if port_used and TOR_ROTATE_ON_ERROR:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
            # Try to rotate circuit on error
            if rotate:
                controller = get_tor_controller()
                if controller and controller.is_connected():
                    controller.rotate_circuit()
    except ConnectionError as e:
        logger.warning(f"Connection error scraping {url[:50]}...: {e}")
        scraped_text = title
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
            if TOR_ROTATE_ON_ERROR and rotate:
                controller = get_tor_controller()
                if controller and controller.is_connected():
                    controller.rotate_circuit()
    except ProxyError as e:
        logger.error(f"Proxy error (Tor issue?) scraping {url[:50]}...: {e}")
        scraped_text = title
        if port_used:
            tor_pool = get_tor_pool()
            tor_pool.record_failure(port_used)
            if TOR_ROTATE_ON_ERROR and rotate:
                controller = get_tor_controller()
                if controller and controller.is_connected():
                    controller.rotate_circuit()
    except HTTPError as e:
        logger.warning(f"HTTP error {e.response.status_code if e.response else 'unknown'} for {url[:50]}...: {e}")
        scraped_text = title
    except RequestException as e:
        logger.warning(f"Request error scraping {url[:50]}...: {e}")
        scraped_text = title
    except Exception as e:
        logger.error(f"Unexpected error scraping {url[:50]}...: {e}", exc_info=True)
        scraped_text = title
    
    return url, scraped_text

def scrape_multiple(urls_data: List[Dict[str, str]], max_workers: int = 5, max_chars: int = 1200) -> Dict[str, str]:
    """
    Scrapes multiple URLs concurrently using a thread pool.
    
    Args:
        urls_data: List of dictionaries with 'link' and 'title' keys
        max_workers: Number of concurrent threads for scraping
        max_chars: Maximum characters to keep from each scraped page
        
    Returns:
        Dictionary mapping each URL to its scraped content
    """
    if not urls_data:
        logger.warning("No URLs provided for scraping")
        return {}
    
    logger.info(f"Scraping {len(urls_data)} URLs with {max_workers} workers...")
    results: Dict[str, str] = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single, url_data): url_data
            for url_data in urls_data
        }
        
        completed = 0
        for future in as_completed(future_to_url):
            url_data = future_to_url[future]
            try:
                url, content = future.result()
                if len(content) > max_chars:
                    content = content[:max_chars] + "..."
                results[url] = content
                completed += 1
                if completed % 5 == 0:
                    logger.debug(f"Scraped {completed}/{len(urls_data)} URLs...")
            except Exception as e:
                logger.error(f"Error processing result for {url_data.get('link', 'unknown')[:50]}...: {e}")
                # Still add the URL with title as fallback
                results[url_data.get('link', '')] = url_data.get('title', '')
    
    logger.info(f"Successfully scraped {len(results)} URLs")
    return results