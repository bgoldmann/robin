<div align="center">
   <img src=".github/assets/logo.png" alt="Robin Logo" width="300">
   <br>
   <a href="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml"><img alt="Build" src="https://github.com/apurvsinghgautam/robin/actions/workflows/binary.yml/badge.svg"></a>
   <a href="https://github.com/apurvsinghgautam/robin/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/apurvsinghgautam/robin"></a>
   <a href="https://hub.docker.com/r/apurvsg/robin"><img alt="Docker Pulls" src="https://img.shields.io/docker/pulls/apurvsg/robin"></a>
   <h1>Robin: AI-Powered Dark Web OSINT Tool</h1>
   <p><strong>Professional-grade open source intelligence tool for dark web investigations</strong></p>
   <p>
      <a href="#features">Features</a> •
      <a href="#installation">Installation</a> •
      <a href="#usage">Usage</a> •
      <a href="#configuration">Configuration</a> •
      <a href="#documentation">Documentation</a> •
      <a href="#contributing">Contributing</a>
   </p>
</div>

![Demo](.github/assets/screen.png)
![Demo UI](.github/assets/screen-ui.png)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## 🎯 Overview

**Robin** is an advanced AI-powered Open Source Intelligence (OSINT) tool designed for conducting dark web investigations. It combines the power of Large Language Models (LLMs) with automated dark web search and content analysis to provide comprehensive threat intelligence reports.

### Key Capabilities

- **Intelligent Query Refinement**: Uses AI to optimize search queries for better dark web results
- **Multi-Engine Search**: Searches across 15+ dark web search engines simultaneously
- **AI-Powered Filtering**: Automatically filters and ranks results by relevance
- **Content Extraction**: Scrapes and analyzes content from dark web sites
- **IOC Extraction**: Automatically extracts Indicators of Compromise (IPs, domains, emails, hashes, crypto addresses, etc.)
- **Comprehensive Reporting**: Generates detailed investigation summaries with actionable insights
- **Dual Interface**: Command-line interface for automation and web UI for interactive use
- **People Search (OSINT)**: Person-centric deep people search across dark web, Telegram, clear web, and optional people APIs (Hunter, EmailRep, HIBP), with unified person profile and narrative summary

---

## People Search (OSINT)

Robin includes a **People Search** mode for person-centric OSINT. You provide one or more identifiers (name, email, username, phone); Robin expands them into search queries, runs dark web + Telegram + clear web search, optionally calls people APIs (Hunter, EmailRep, HIBP), and produces a **person profile** plus an **investigation summary** and IOCs.

- **Inputs**: At least one of name, email, username, phone (comma-separated for multiple emails/usernames).
- **Sources**: Existing dark web (15+ engines) and optional Telegram; clear web (DuckDuckGo, optional Google Custom Search); optional people APIs (Hunter.io, EmailRep.io, Have I Been Pwned for breach presence only).
- **Output**: Structured person profile (emails, usernames, phones, social links, dark/clear web mentions, IOCs, API snippets) and a people-focused narrative summary. Same export options (Markdown, JSON, PDF, IOCs).
- **Legal / ethics**: People search must be used only for lawful purposes (e.g. authorized investigations, research). Do not use for stalking or harassment. Only public or semi-public data is aggregated; HIBP is used only for breach presence with API key and ToS compliance.

**CLI:** `robin people --name "John Doe" --email j@example.com --username johndoe`  
**API:** `POST /investigate/people` with JSON body `{ "name", "email", "username", "phone" }`  
**Web UI:** Select "People Search" mode and fill in the person identifier fields.

---

## ✨ Features

### Core Features

- 🤖 **Multi-Model LLM Support**
  - OpenAI GPT-4o, GPT-4.1
  - Anthropic Claude 3.5 Sonnet
  - Google Gemini 2.5 Flash
  - Local models via Ollama (Llama 3.1, etc.)

- 🔍 **Advanced Search Capabilities**
  - Concurrent search across 15+ dark web search engines
  - Automatic search engine health monitoring
  - Priority-based engine selection
  - Result deduplication and ranking

- 🕷️ **Intelligent Scraping**
  - Concurrent multi-threaded scraping
  - Automatic Tor routing for .onion sites
  - User-Agent rotation
  - Content cleaning and extraction
  - Retry mechanisms with exponential backoff

- 🧠 **AI-Powered Analysis**
  - Query refinement for optimal search results
  - Intelligent result filtering (top 20 most relevant)
  - Comprehensive investigation summary generation
  - Context-aware artifact extraction

- 🔐 **Tor Integration**
  - Automatic Tor circuit rotation
  - Multiple Tor instance support for improved performance
  - Circuit health monitoring
  - Exit node information tracking
  - Connection verification and retry logic

- 📊 **IOC Extraction**
  - Automatic extraction of 11+ IOC types:
    - IPv4/IPv6 addresses
    - Domain names (including .onion)
    - Email addresses
    - URLs
    - Hash values (MD5, SHA1, SHA256)
    - Cryptocurrency addresses (Bitcoin, Ethereum)
    - Phone numbers
  - IOC deduplication and merging
  - Multiple export formats (JSON, CSV, Text)

- 📝 **Export Options**
  - Markdown reports
  - JSON with full metadata
  - CSV for structured data
  - Separate IOC exports
  - Customizable output formats

### User Interface Features

- 💻 **Web UI (Streamlit)**
  - Real-time progress tracking with percentages
  - Interactive IOC visualization with tabs
  - Search history and saved queries
  - Result preview with expandable sections
  - Tor status dashboard
  - Statistics and metrics display
  - Advanced settings panel
  - Multiple export format selection

- 🖥️ **CLI Interface**
  - Full-featured command-line interface
  - Progress indicators with spinners
  - Configurable logging levels
  - Batch processing support
  - Script-friendly output

### Advanced Features

- 🔄 **Resilience & Reliability**
  - Comprehensive error handling
  - Retry mechanisms with exponential backoff
  - Graceful degradation on failures
  - Connection pooling for performance
  - Health monitoring and automatic recovery

- 📈 **Observability**
  - Structured logging system
  - Configurable log levels (DEBUG, INFO, WARNING, ERROR)
  - File and console logging
  - Performance metrics tracking
  - Operation statistics

- 🛡️ **Security**
  - Input validation and sanitization
  - Query length limits
  - URL format validation
  - Secure API key handling
  - Tor circuit isolation
  - Error message sanitization

---

## 🚀 Installation

### Prerequisites

- **Tor**: Required for dark web access
  - Linux/Windows (WSL): `sudo apt install tor`
  - macOS: `brew install tor`
  - Verify Tor is running: `tor --version`

- **Python 3.10+** (for development installation)
- **Docker** (for containerized deployment)

### Method 1: Docker (Recommended)

The easiest way to run Robin with all dependencies:

```bash
# Pull the latest image
docker pull apurvsg/robin:latest

# Run with Web UI
docker run --rm \
   -v "$(pwd)/.env:/app/.env" \
   --add-host=host.docker.internal:host-gateway \
   -p 8501:8501 \
   apurvsg/robin:latest ui --ui-port 8501 --ui-host 0.0.0.0

# Run CLI mode
docker run --rm \
   -v "$(pwd)/.env:/app/.env" \
   --add-host=host.docker.internal:host-gateway \
   apurvsg/robin:latest cli -m gpt4o -q "your query here"
```

### Method 2: Pre-built Binary

Download the appropriate binary for your system from the [latest release](https://github.com/apurvsinghgautam/robin/releases/latest):

```bash
# Linux
wget https://github.com/apurvsinghgautam/robin/releases/latest/download/robin-linux.zip
unzip robin-linux.zip
chmod +x robin
./robin --help

# macOS
wget https://github.com/apurvsinghgautam/robin/releases/latest/download/robin-macos.zip
unzip robin-macos.zip
chmod +x robin
./robin --help
```

### Method 3: Python Development Installation

For development or customization:

```bash
# Clone the repository
git clone https://github.com/apurvsinghgautam/robin.git
cd robin

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python main.py --help
```

---

## ⚡ Quick Start

### 1. Configure API Keys

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Required: At least one LLM provider API key
OPENAI_API_KEY=your_openai_api_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# OR
GOOGLE_API_KEY=your_google_api_key_here

# Optional: For local models
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### 2. Start Tor

Ensure Tor is running:

```bash
# Check if Tor is running
tor --version

# Start Tor service (if not running)
# Linux/WSL
sudo systemctl start tor
# macOS
brew services start tor
```

### 3. Run Your First Investigation

**CLI Mode:**
```bash
robin cli -m gpt4o -q "ransomware payments" -t 8 --extract-iocs
```

**Web UI Mode:**
```bash
robin ui --ui-port 8501
# Open http://localhost:8501 in your browser
```

---

## 📖 Usage

### CLI Mode

#### Basic Usage

```bash
robin cli -m gpt4o -q "your search query" -t 12
```

#### Advanced Usage

```bash
# With IOC extraction and JSON export
robin cli -m claude-3-5-sonnet-latest \
  -q "data breach credentials" \
  -t 8 \
  --extract-iocs \
  --format json \
  --output investigation_report

# With custom logging
robin cli -m gpt4o \
  -q "zero-day exploits" \
  --log-level DEBUG \
  --log-file robin.log \
  --extract-iocs \
  --format both
```

#### CLI Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--model` | `-m` | LLM model (gpt4o, gpt-4.1, claude-3-5-sonnet-latest, llama3.1, gemini-2.5-flash) | `gpt4o` |
| `--query` | `-q` | Dark web search query (required) | - |
| `--threads` | `-t` | Number of concurrent threads for scraping | `5` |
| `--output` | `-o` | Output filename (without extension) | Auto-generated |
| `--format` | `-f` | Output format (markdown, json, both, pdf, all) | `markdown` |
| `--extract-iocs` | - | Extract and export Indicators of Compromise | `false` |
| `--telegram` | - | Include Telegram OSINT search (public posts and joined chats) | `false` |
| `--rotate-circuit` | - | Enable Tor circuit rotation during scraping | `false` |
| `--rotate-interval` | - | Rotate Tor circuit after N requests | TOR_ROTATE_INTERVAL |
| `--skip-health-check` | - | Skip search engine health check for faster startup | `false` |
| `--save-db` | - | Save investigation to SQLite database | `false` |
| `--log-level` | - | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `--log-file` | - | Optional log file path | None |

#### Example Commands

```bash
# Basic investigation
robin cli -m gpt4o -q "ransomware payments"

# High-performance investigation with IOC extraction
robin cli -m gpt-4.1 -q "sensitive credentials exposure" -t 16 --extract-iocs --format both

# Using local Ollama model
robin cli -m llama3.1 -q "zero days" -t 8

# With detailed logging
robin cli -m gemini-2.5-flash -q "threat actor profiles" --log-level DEBUG --log-file debug.log

# With Telegram OSINT (requires TELEGRAM_* env vars)
robin cli -m gpt4o -q "ransomware" --telegram --extract-iocs

# With circuit rotation and PDF output
robin cli -m gpt4o -q "ransomware" --rotate-circuit --format pdf --extract-iocs

# Save to database
robin cli -m gpt4o -q "data breach" --extract-iocs --save-db

# People Search (at least one of --name, --email, --username, --phone)
robin people --name "John Doe" --email j@example.com --username johndoe --extract-iocs --format json
robin people --email target@example.com --telegram
```

#### Batch Mode

Process multiple queries from a file (one query per line):

```bash
robin batch -b queries.txt -m gpt4o -t 8 --extract-iocs --format all
```

#### API Server Mode

Run the REST API for programmatic access:

```bash
# Start API server (default: http://0.0.0.0:8000)
robin api --port 8000

# With API key (set ROBIN_API_KEY in .env)
robin api -p 8000
```

Endpoints: `GET /health`, `POST /search`, `POST /investigate`. Docs at `/docs`.

### Web UI Mode

#### Starting the Web UI

```bash
# Default (localhost:8501)
robin ui

# Custom port and host
robin ui --ui-port 8080 --ui-host 0.0.0.0
```

#### Web UI Features

1. **Settings Panel** (Sidebar)
   - LLM model selection
   - Thread count configuration
   - IOC extraction toggle
   - Include Telegram search (when configured)
   - Export format selection

2. **Advanced Settings** (Expandable)
   - Tor circuit rotation
   - Multi-instance Tor configuration
   - Timeout settings

3. **Search History**
   - View recent queries
   - Quick re-run from history
   - Save favorite queries

4. **Tor Status Dashboard**
   - Connection status
   - Active circuit count
   - Exit node information
   - Rotation statistics

5. **Statistics Panel**
   - Total queries executed
   - IOCs extracted
   - Results found
   - Average query time

6. **Real-time Progress**
   - Progress bars with percentages
   - Stage-by-stage status updates
   - ETA calculations

7. **IOC Visualization**
   - Tabs organized by IOC type
   - Count metrics per type
   - Export options (JSON, CSV, Text)

8. **Result Preview**
   - Expandable result cards
   - URL and title display
   - Content preview (first 200 chars)

9. **Export Options**
   - Multiple format downloads
   - Separate IOC exports
   - Custom filename support

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

#### LLM API Keys (Required: At least one)

```env
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key
OLLAMA_BASE_URL=http://127.0.0.1:11434  # For local Ollama
```

#### Tor Configuration

```env
# Tor Control Port (for circuit rotation)
TOR_CONTROL_PORT=9051

# Tor Control Password (if configured)
TOR_CONTROL_PASSWORD=

# Circuit Rotation Settings
TOR_ROTATE_INTERVAL=5              # Rotate after N requests
TOR_ROTATE_ON_ERROR=true           # Rotate on errors

# Multi-Instance Tor (for performance)
TOR_MULTI_INSTANCE=false           # Enable multiple Tor instances
TOR_INSTANCE_COUNT=3               # Number of instances
TOR_INSTANCE_START_PORT=9050       # Starting port
```

#### Timeout Configuration

```env
SEARCH_TIMEOUT=20                  # Search request timeout (seconds)
SCRAPE_TIMEOUT=45                  # Scraping timeout (seconds)
```

#### Telegram OSINT (Optional)

To include Telegram in investigations (public posts and joined chats), obtain API credentials from [my.telegram.org](https://my.telegram.org/) and set:

```env
TELEGRAM_API_ID=your_api_id        # Integer from my.telegram.org
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_PATH=robin_telegram.session   # Optional; default robin_telegram.session
TELEGRAM_ENABLED=true
```

- **First-time login**: The first time you use Telegram OSINT, you must authorize the app (phone number + code). Run a query with `--telegram` (CLI) or enable "Include Telegram search" (UI); if the session is not yet authorized, follow the instructions to complete login. Session data is stored in `TELEGRAM_SESSION_PATH` so you do not need to log in again.
- **CLI**: Use the `--telegram` flag to merge Telegram results with dark web results.
- **Web UI**: Enable the "Include Telegram search" checkbox in Settings.
- **Legal / ToS**: Use only for lawful OSINT (e.g. threat intelligence, authorized investigations). Comply with Telegram's Terms of Service and applicable laws. Only public channel posts and (optionally) search within your own joined chats are used; no access to private chats.

#### Clear-web and People APIs (Optional – People Search mode)

People Search uses clear-web search (DuckDuckGo, optional Google CSE) and optional people APIs for enrichment:

```env
# Clear-web search (People Search)
CLEAR_WEB_SEARCH_ENABLED=true
DUCKDUCKGO_ENABLED=true
GOOGLE_CSE_ID=                    # Optional; requires GOOGLE_API_KEY
CLEAR_WEB_MAX_RESULTS=30
CLEAR_WEB_TIMEOUT=15

# People APIs (Hunter, EmailRep, HIBP)
PEOPLE_APIS_ENABLED=false
HUNTER_API_KEY=
EMAILREP_API_KEY=
HIBP_API_KEY=                     # Have I Been Pwned – breach presence only
```

- **People search must be used only for lawful purposes** (e.g. authorized investigations, research). Do not use for stalking or harassment.
- HIBP is used only for breach presence (has this email been in a breach?) with API key and ToS compliance; no raw breach data.

### Streamlit Configuration

Edit `.streamlit/config.toml` for UI customization:

```toml
[server]
runOnSave = true

[theme]
base = "dark"
primaryColor = "#FF4B4B"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#262730"
textColor = "#FAFAFA"
font = "sans serif"
```

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  User Interface Layer                   │
│  ┌──────────────┐              ┌──────────────┐       │
│  │   CLI Mode   │              │   Web UI     │       │
│  │  (main.py)   │              │  (ui.py)     │       │
│  └──────┬───────┘              └──────┬───────┘       │
└─────────┼──────────────────────────────┼───────────────┘
          │                              │
          └──────────────┬────────────────┘
                        │
          ┌─────────────▼───────────────┐
          │     Core Workflow Engine     │
          │         (main.py)            │
          └─────────────┬───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│   LLM Layer  │ │ Search Layer│ │ Scrape Layer│
│   (llm.py)   │ │ (search.py) │ │ (scrape.py) │
└───────┬──────┘ └──────┬──────┘ └──────┬──────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
          ┌─────────────▼───────────────┐
          │    Utility Layer            │
          │    (utils.py)               │
          │  - Logging                  │
          │  - Validation               │
          │  - Retry Mechanisms         │
          │  - IOC Extraction           │
          └─────────────────────────────┘
                        │
          ┌─────────────▼───────────────┐
          │    Tor Management Layer      │
          │  - tor_controller.py         │
          │  - tor_pool.py               │
          └─────────────────────────────┘
```

### Data Flow

1. **User Input** → Query validation
2. **Query Refinement** → LLM optimizes search query
3. **Dark Web Search** → Concurrent search across 15+ engines via Tor
4. **Result Filtering** → LLM selects top 20 relevant results
5. **Content Scraping** → Concurrent scraping with Tor routing
6. **IOC Extraction** → Automatic extraction (if enabled)
7. **Summary Generation** → LLM generates comprehensive report
8. **Export** → Multiple format options

### Key Components

- **`main.py`**: CLI entry point and workflow orchestration
- **`ui.py`**: Streamlit web interface
- **`llm.py`**: LLM operations (refinement, filtering, summarization)
- **`llm_utils.py`**: LLM configuration and model management
- **`search.py`**: Dark web search engine integration
- **`telegram_osint.py`**: Telegram OSINT (public posts and joined-chat search via Telethon)
- **`scrape.py`**: Content scraping with Tor support (and pre-filled content for Telegram)
- **`tor_controller.py`**: Tor circuit rotation and management
- **`tor_pool.py`**: Multiple Tor instance management
- **`utils.py`**: Utilities (logging, validation, IOC extraction, retry mechanisms)
- **`config.py`**: Configuration management

---

## 🔧 Troubleshooting

### Common Issues

#### Tor Connection Issues

**Problem**: `Tor connection verification failed`

**Solutions**:
1. Verify Tor is running: `tor --version`
2. Check Tor service status:
   ```bash
   # Linux/WSL
   sudo systemctl status tor
   
   # macOS
   brew services list | grep tor
   ```
3. Restart Tor service:
   ```bash
   sudo systemctl restart tor  # Linux
   brew services restart tor   # macOS
   ```
4. Verify Tor SOCKS port (default: 9050):
   ```bash
   netstat -an | grep 9050
   ```

#### LLM API Errors

**Problem**: `Failed to initialize LLM`

**Solutions**:
1. Verify API key is set in `.env` file
2. Check API key validity
3. Verify API quota/credits available
4. For Ollama: Ensure Ollama is running and accessible
   ```bash
   curl http://127.0.0.1:11434/api/tags
   ```

#### No Search Results

**Problem**: `No results found`

**Solutions**:
1. Try refining your query (be more specific)
2. Check Tor connection status
3. Verify search engines are accessible
4. Increase timeout values in `.env`
5. Check logs for specific errors:
   ```bash
   robin cli -m gpt4o -q "test" --log-level DEBUG --log-file debug.log
   ```

#### Scraping Failures

**Problem**: `Failed to scrape results`

**Solutions**:
1. Reduce thread count (`-t 3` instead of `-t 16`)
2. Increase scrape timeout in `.env`
3. Enable circuit rotation for better anonymity
4. Check Tor circuit health

#### Memory Issues

**Problem**: Application crashes or becomes slow

**Solutions**:
1. Reduce thread count
2. Limit number of results processed
3. Use IOC extraction selectively
4. Clear cache in Web UI

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# CLI with debug logging
robin cli -m gpt4o -q "your query" --log-level DEBUG --log-file debug.log

# Check log file
tail -f debug.log
```

### Performance Optimization

1. **Increase Threads**: Use more threads for faster processing
   ```bash
   robin cli -m gpt4o -q "query" -t 16
   ```

2. **Enable Multi-Instance Tor**: For better concurrency
   ```env
   TOR_MULTI_INSTANCE=true
   TOR_INSTANCE_COUNT=5
   ```

3. **Optimize Timeouts**: Adjust based on your network
   ```env
   SEARCH_TIMEOUT=15
   SCRAPE_TIMEOUT=30
   ```

---

## 🛡️ Security

### Security Best Practices

1. **API Key Security**
   - Never commit `.env` files to version control
   - Use environment variables in production
   - Rotate API keys regularly
   - Use separate keys for development/production

2. **Tor Security**
   - Keep Tor updated to latest version
   - Use circuit rotation for sensitive investigations
   - Monitor exit node information
   - Consider using VPN in addition to Tor

3. **Data Privacy**
   - Be cautious with sensitive queries
   - Review LLM provider privacy policies
   - Encrypt stored results if containing sensitive data
   - Implement data retention policies

4. **Input Validation**
   - All queries are validated and sanitized
   - URL format validation before processing
   - Length limits prevent abuse

### Legal and Ethical Considerations

⚠️ **Important**: This tool is intended for:
- Legitimate security research
- Authorized penetration testing
- Law enforcement investigations (with proper authorization)
- Academic research
- Threat intelligence gathering (for defensive purposes)

**Do NOT use for**:
- Unauthorized access to systems
- Illegal activities
- Harassment or doxxing
- Violating terms of service

Always ensure compliance with:
- Local and international laws
- Institutional policies
- Terms of service of APIs and services used
- Ethical guidelines for security research

---

## 📚 Documentation

### Additional Documentation

- **[CHANGELOG.md](CHANGELOG.md)**: Version history and changes
- **[DEEP_ANALYSIS.md](DEEP_ANALYSIS.md)**: Comprehensive codebase analysis
- **[RESEARCH_AND_IMPROVEMENTS.md](RESEARCH_AND_IMPROVEMENTS.md)**: Research findings and recommendations
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**: Implementation details
- **[QUICK_IMPROVEMENTS.md](QUICK_IMPROVEMENTS.md)**: Quick reference guide

### API Documentation

For programmatic usage, see the inline documentation in source files:
- `main.py`: CLI command reference
- `llm.py`: LLM operation functions
- `search.py`: Search engine integration
- `scrape.py`: Scraping functions
- `utils.py`: Utility functions

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests if applicable
5. Update documentation
6. Commit: `git commit -m 'Add amazing feature'`
7. Push: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/robin.git
cd robin

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 mypy pytest

# Run tests (when available)
pytest

# Format code
black .

# Lint code
flake8 .
```

### Contribution Areas

We welcome contributions in:
- New search engines
- Additional LLM providers
- UI/UX improvements
- Performance optimizations
- Documentation
- Bug fixes
- Test coverage
- Security enhancements

### Code Style

- Follow PEP 8 style guide
- Use type hints
- Add docstrings to functions
- Write clear commit messages
- Update CHANGELOG.md for user-facing changes

---

## 📊 Performance

### Benchmarks

Typical performance metrics (varies by query and network):

- **Query Refinement**: 2-5 seconds
- **Search (15 engines)**: 30-60 seconds
- **Filtering**: 5-10 seconds
- **Scraping (20 URLs)**: 60-120 seconds
- **Summary Generation**: 10-30 seconds
- **Total Time**: ~2-4 minutes per investigation

### Optimization Tips

1. Use appropriate thread count (8-12 for most systems)
2. Enable multi-instance Tor for better concurrency
3. Cache results when possible
4. Use faster LLM models for non-critical operations
5. Process results in batches for large investigations

---

## 🗺️ Roadmap

### Planned Features

- [x] API server mode (RESTful API)
- [x] Database integration for result storage (SQLite)
- [x] Threat intelligence platform integration (STIX, MISP export)
- [ ] Advanced analytics and visualization
- [ ] Query templates and saved searches
- [ ] Batch processing mode
- [ ] PDF report generation
- [ ] Multi-language support
- [ ] Plugin system for extensibility
- [ ] Unit and integration tests

See [RESEARCH_AND_IMPROVEMENTS.md](RESEARCH_AND_IMPROVEMENTS.md) for detailed roadmap.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Idea Inspiration**: [Thomas Roccia](https://x.com/fr0gger_) and his demo of [Perplexity of the Dark Web](https://x.com/fr0gger_/status/1908051083068645558)
- **Tools Inspiration**: [OSINT Tools for the Dark Web](https://github.com/apurvsinghgautam/dark-web-osint-tools) repository
- **LLM Prompt Inspiration**: [OSINT-Assistant](https://github.com/AXRoux/OSINT-Assistant) repository
- **Logo Design**: [Tanishq Rupaal](https://github.com/Tanq16/)

### Technologies Used

- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Streamlit](https://streamlit.io/) - Web UI framework
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Stem](https://stem.torproject.org/) - Tor control library
- [Click](https://click.palletsprojects.com/) - CLI framework
- [Tor Project](https://www.torproject.org/) - Anonymity network

---

## 📞 Support

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/apurvsinghgautam/robin/issues)
- **Discussions**: [GitHub Discussions](https://github.com/apurvsinghgautam/robin/discussions)
- **Documentation**: See [Documentation](#documentation) section

### Reporting Bugs

When reporting bugs, please include:
- Robin version
- Operating system
- Python version (if using development install)
- Steps to reproduce
- Error messages/logs
- Configuration (sanitized, no API keys)

### Feature Requests

We welcome feature requests! Please:
- Check existing issues first
- Provide detailed use case
- Explain expected behavior
- Consider implementation complexity

---

## ⭐ Star History

If you find Robin useful, please consider giving it a star on GitHub!

---

<div align="center">
   <p>Made with ❤️ by <a href="https://www.linkedin.com/in/apurvsinghgautam/">Apurv Singh Gautam</a></p>
   <p>⚠️ Use responsibly and in compliance with applicable laws</p>
</div>
