# Changelog

All notable changes to the Robin project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **People Search (OSINT)** - Person-centric deep people search and OSINT:
  - CLI: `robin people --name "John Doe" --email j@x.com --username johndoe` (at least one of name, email, username, phone required)
  - API: `POST /investigate/people` with body `{ "name", "email", "username", "phone" }`
  - Web UI: "People Search" mode with name, email, username, phone fields
  - Multi-source: dark web + Telegram + clear web (DuckDuckGo, optional Google CSE) + optional people APIs (Hunter, EmailRep, HIBP breach presence)
  - Person profile (aliases, emails, usernames, phones, social links, dark/clear web mentions, IOCs, API snippets) and people-specific narrative summary
  - Config: `CLEAR_WEB_SEARCH_ENABLED`, `DUCKDUCKGO_ENABLED`, `GOOGLE_CSE_ID`, `PEOPLE_APIS_ENABLED`, `HUNTER_API_KEY`, `EMAILREP_API_KEY`, `HIBP_API_KEY` (see `.env.example`)
  - People search must be used only for lawful purposes (e.g. authorized investigations, research). Do not use for stalking or harassment.
- **API Server Mode** - REST API for programmatic access (`robin api`):
  - Endpoints: `/health`, `/search`, `/investigate`
  - API key auth via `X-API-Key` header when `ROBIN_API_KEY` is set
  - Rate limiting (slowapi)
  - OpenAPI docs at `/docs`
- **Batch Processing** - Run multiple queries from file (`robin batch -b queries.txt`)
  - Sequential processing with aggregated IOCs and combined report
  - Markdown, JSON, PDF output
- **PDF Report Generation** - Shareable reports (`--format pdf` or `--format all`)
  - Pure-Python PDF via reportlab (no system deps like cairo)
  - Web UI PDF download
- **Database Integration** - SQLite persistence (`--save-db`)
  - Tables: investigations, search_results, iocs
  - Default path: `~/.robin/robin.db` (configurable via `ROBIN_DB_PATH`)
- **STIX/MISP IOC Export** - Threat intel formats when `--extract-iocs`:
  - STIX 2.x bundle (JSON)
  - MISP-compatible Event/Attribute JSON
- **Circuit Rotation** - Tor circuit rotation during scraping:
  - CLI: `--rotate-circuit`, `--rotate-interval`
  - UI: Advanced Settings "Enable Circuit Rotation"
- **Skip Health Check** - Faster startup (`--skip-health-check` / UI option)
- **Telegram OSINT** - Optional Telegram source alongside dark web search:
  - Public post search via Telethon (`SearchPostsRequest`) and optional global search in joined chats (`SearchGlobalRequest`)
  - CLI flag `--telegram` to include Telegram results; Web UI checkbox "Include Telegram search"
  - Config: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_PATH`, `TELEGRAM_ENABLED` (see `.env.example`)
  - First-time login via session file (phone + code); results merged with dark web and passed through existing filter/scrape/summary pipeline
  - Scrape layer supports pre-filled `content` so Telegram items skip HTTP; filter/summary handle t.me and telegram:// links
- **Comprehensive logging system** - Structured logging with configurable levels and file output
- **Input validation** - Query validation and sanitization to prevent security issues
- **Retry mechanisms** - Exponential backoff retry decorators for resilient operations
- **IOC extraction** - Automatic extraction of Indicators of Compromise (IPs, domains, emails, hashes, crypto addresses, etc.)
- **Multiple export formats** - JSON and CSV export options in addition to Markdown
- **Enhanced error handling** - Specific exception handling with detailed error messages
- **Tor connection verification** - Health check for Tor connectivity before operations
- **Progress tracking** - Better user feedback with detailed progress indicators
- **Research and improvements document** (`RESEARCH_AND_IMPROVEMENTS.md`) with comprehensive analysis
- **Quick improvements reference** (`QUICK_IMPROVEMENTS.md`) for quick lookup
- **Changelog file** for tracking project changes

### Changed
- **Error handling** - Replaced bare `except:` clauses with specific exception handling
- **Request handling** - Added connection pooling and retry strategies using `requests.Session`
- **LLM error handling** - Improved error handling for all LLM providers (not just OpenAI)
- **Scraping** - Enhanced scraping with better error recovery and logging
- **Search** - Improved search result parsing with better error handling
- **Type hints** - Added type hints throughout codebase for better code quality

### Fixed
- **Missing time import in search.py** - `check_search_engine_health()` now imports `time`
- **Advanced Settings not applied** - Tor rotate and interval now passed from UI to scrape layer
- **Silent failures** - All errors now properly logged and reported
- **Rate limit handling** - Better handling of LLM API rate limits with fallbacks
- **Index errors** - Fixed potential index errors in result filtering
- **Memory issues** - Better handling of large content with truncation

### Security
- **Input sanitization** - Added query validation to prevent injection attacks
- **Error message security** - Sensitive information no longer exposed in error messages
- **URL validation** - Added URL format validation before processing

---

## [Current Version]

### Features
- Multi-model LLM support (GPT-4o, GPT-4.1, Claude 3.5 Sonnet, Llama 3.1, Gemini 2.5 Flash)
- Dark web search across 15+ search engines
- Concurrent scraping with configurable threads
- CLI and Web UI modes
- Investigation summary generation
- Docker support
- Tor integration for dark web access

### Known Issues
- Bare exception handling in search and scrape modules
- No logging system implemented
- Tor circuit rotation not fully implemented
- Limited error handling for LLM API calls
- No input validation on user queries

---

## Future Improvements

See `RESEARCH_AND_IMPROVEMENTS.md` for comprehensive list of planned improvements including:

### Critical Fixes
- Proper error handling with specific exceptions
- Comprehensive logging system
- Input validation and sanitization
- Tor circuit rotation implementation
- Retry mechanisms with exponential backoff

### New Features
- IOC (Indicators of Compromise) extraction and export
- Configuration management system
- Multiple export formats (JSON, CSV, PDF)
- API server mode
- Database integration
- Threat intelligence platform integration
- Progress tracking and reporting
- Advanced filtering options

### Optimizations
- Request optimization with connection pooling
- Memory optimization
- LLM token optimization
- Async/await implementation
- Caching strategies

---

**Note:** This changelog will be updated as improvements are implemented.

