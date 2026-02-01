import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Configuration variables loaded from the .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

# Tor Configuration
TOR_CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", "9051"))
TOR_CONTROL_PASSWORD = os.getenv("TOR_CONTROL_PASSWORD")
TOR_ROTATE_INTERVAL = int(os.getenv("TOR_ROTATE_INTERVAL", "5"))  # Rotate after N requests
TOR_ROTATE_ON_ERROR = os.getenv("TOR_ROTATE_ON_ERROR", "true").lower() == "true"
TOR_SOCKS_PORT = int(os.getenv("TOR_SOCKS_PORT", "9050"))  # Default SOCKS port
TOR_MULTI_INSTANCE = os.getenv("TOR_MULTI_INSTANCE", "false").lower() == "true"
TOR_INSTANCE_COUNT = int(os.getenv("TOR_INSTANCE_COUNT", "3"))  # Number of Tor instances for multi-instance mode
TOR_INSTANCE_START_PORT = int(os.getenv("TOR_INSTANCE_START_PORT", "9050"))  # Starting port for multiple instances

# Timeout Configuration
SEARCH_TIMEOUT = int(os.getenv("SEARCH_TIMEOUT", "20"))  # Timeout for search requests (seconds)
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT", "45"))  # Timeout for scraping requests (seconds)

# Telegram OSINT (optional)
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_SESSION_PATH = os.getenv("TELEGRAM_SESSION_PATH", "robin_telegram.session")
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

# Database (optional - for --save-db)
ROBIN_DB_PATH = os.getenv("ROBIN_DB_PATH", "")  # Empty = default ~/.robin/robin.db

# Clear-web search (for People Search mode)
CLEAR_WEB_SEARCH_ENABLED = os.getenv("CLEAR_WEB_SEARCH_ENABLED", "true").lower() == "true"
DUCKDUCKGO_ENABLED = os.getenv("DUCKDUCKGO_ENABLED", "true").lower() == "true"
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")  # Optional; requires GOOGLE_API_KEY
CLEAR_WEB_MAX_RESULTS = int(os.getenv("CLEAR_WEB_MAX_RESULTS", "30"))
CLEAR_WEB_TIMEOUT = int(os.getenv("CLEAR_WEB_TIMEOUT", "15"))

# People APIs (optional - for People Search enrichment)
PEOPLE_APIS_ENABLED = os.getenv("PEOPLE_APIS_ENABLED", "false").lower() == "true"
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
EMAILREP_API_KEY = os.getenv("EMAILREP_API_KEY", "")
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")
