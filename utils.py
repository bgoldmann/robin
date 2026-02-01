"""
Utility functions for Robin OSINT tool.
Includes logging, validation, retry mechanisms, and IOC extraction.
"""
import logging
import re
import json
import uuid
from typing import Dict, List, Optional, Set, Any
from functools import wraps
from time import sleep
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("robin")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with formatting
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# Get logger instance
logger = setup_logging()


def validate_query(query: str, max_length: int = 500) -> tuple:
    """
    Validate and sanitize user query.
    
    Args:
        query: User input query
        max_length: Maximum allowed query length
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or not isinstance(query, str):
        return False, "Query must be a non-empty string"
    
    if len(query.strip()) == 0:
        return False, "Query cannot be empty or whitespace only"
    
    if len(query) > max_length:
        return False, f"Query exceeds maximum length of {max_length} characters"
    
    # Check for potentially dangerous characters (basic sanitization)
    dangerous_patterns = [
        r'[<>"\']',  # HTML/script injection
        r'[;&|`$]',  # Command injection
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, query):
            logger.warning(f"Query contains potentially dangerous characters: {query[:50]}...")
            # Don't reject, just log warning
    
    return True, None


def sanitize_url(url: str) -> tuple:
    """
    Validate and sanitize URL.
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, sanitized_url or error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string"
    
    url = url.strip()
    
    # Basic URL validation
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    if not re.match(url_pattern, url):
        return False, f"Invalid URL format: {url[:50]}"
    
    return True, url


def create_session_with_retry(
    max_retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: tuple = (500, 502, 503, 504),
    timeout: tuple = (10, 30)
) -> requests.Session:
    """
    Create a requests session with retry strategy.
    
    Args:
        max_retries: Maximum number of retries
        backoff_factor: Backoff factor for exponential backoff
        status_forcelist: HTTP status codes to retry on
        timeout: Connection and read timeout tuple
        
    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
        raise_on_status=False
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    session.timeout = timeout
    
    return session


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Base delay multiplier
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {wait_time:.2f}s..."
                        )
                        sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {str(e)}")
                        raise
            if last_exception:
                raise last_exception
        return wrapper
    return decorator


# IOC (Indicators of Compromise) Extraction Patterns
IOC_PATTERNS = {
    'ipv4': re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
    'ipv6': re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'),
    'domain': re.compile(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'),
    'onion': re.compile(r'\b[a-z2-7]{16,56}\.onion\b'),
    'email': re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'),
    'url': re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'),
    'md5': re.compile(r'\b[a-fA-F0-9]{32}\b'),
    'sha1': re.compile(r'\b[a-fA-F0-9]{40}\b'),
    'sha256': re.compile(r'\b[a-fA-F0-9]{64}\b'),
    'bitcoin': re.compile(r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'),
    'ethereum': re.compile(r'\b0x[a-fA-F0-9]{40}\b'),
    'phone': re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
}


def extract_iocs(text: str, ioc_types: Optional[List[str]] = None) -> Dict[str, Set[str]]:
    """
    Extract Indicators of Compromise (IOCs) from text.
    
    Args:
        text: Text to analyze
        ioc_types: List of IOC types to extract (None = all types)
        
    Returns:
        Dictionary mapping IOC types to sets of extracted values
    """
    if ioc_types is None:
        ioc_types = list(IOC_PATTERNS.keys())
    
    iocs: Dict[str, Set[str]] = {}
    
    for ioc_type in ioc_types:
        if ioc_type in IOC_PATTERNS:
            matches = IOC_PATTERNS[ioc_type].findall(text)
            if matches:
                iocs[ioc_type] = set(matches)
                logger.debug(f"Extracted {len(iocs[ioc_type])} {ioc_type} IOCs")
    
    return iocs


def format_iocs_for_export(iocs: Dict[str, Set[str]], format: str = "json") -> str:
    """
    Format IOCs for export in various formats.
    
    Args:
        iocs: Dictionary of IOCs
        format: Export format (json, csv, stix, misp)
        
    Returns:
        Formatted string representation
    """
    if format.lower() == "json":
        # Convert sets to lists for JSON serialization
        iocs_serializable = {k: list(v) for k, v in iocs.items()}
        return json.dumps(iocs_serializable, indent=2)
    
    elif format.lower() == "csv":
        lines = ["IOC Type,Value"]
        for ioc_type, values in iocs.items():
            for value in values:
                lines.append(f"{ioc_type},{value}")
        return "\n".join(lines)
    
    elif format.lower() == "text":
        lines = []
        for ioc_type, values in sorted(iocs.items()):
            lines.append(f"\n{ioc_type.upper()}:")
            for value in sorted(values):
                lines.append(f"  - {value}")
        return "\n".join(lines)
    
    elif format.lower() == "stix":
        return _format_iocs_stix(iocs)
    
    elif format.lower() == "misp":
        return _format_iocs_misp(iocs)
    
    else:
        return json.dumps({k: list(v) for k, v in iocs.items()}, indent=2)


# Map Robin IOC types to STIX 2.x observable types
_STIX_TYPE_MAP = {
    "ipv4": "ipv4-addr",
    "ipv6": "ipv6-addr",
    "domain": "domain-name",
    "onion": "domain-name",
    "email": "email-addr",
    "url": "url",
    "md5": "file",
    "sha1": "file",
    "sha256": "file",
}


def _format_iocs_stix(iocs: Dict[str, Set[str]]) -> str:
    """Format IOCs as STIX 2.x bundle."""
    objects_list: List[Dict] = []
    for ioc_type, values in iocs.items():
        stix_type = _STIX_TYPE_MAP.get(ioc_type)
        if not stix_type:
            stix_type = "x-observable-custom"
        for v in values:
            oid = f"{stix_type.replace('-', '')}--{uuid.uuid4()}"
            obj = {"type": stix_type, "id": oid, "spec_version": "2.1"}
            if stix_type in ("ipv4-addr", "ipv6-addr", "domain-name", "url", "email-addr"):
                obj["value"] = v
            elif stix_type == "file":
                hash_map = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256"}
                hash_key = hash_map.get(ioc_type, ioc_type.upper())
                obj["hashes"] = {hash_key: v}
            else:
                obj["value"] = v
            objects_list.append(obj)
    bundle = {"type": "bundle", "id": f"bundle--{uuid.uuid4()}", "objects": objects_list}
    return json.dumps(bundle, indent=2)


# Map Robin IOC types to MISP attribute types
_MISP_TYPE_MAP = {
    "ipv4": "ip-dst",
    "ipv6": "ip-dst",
    "domain": "domain",
    "onion": "domain",
    "email": "email-src",
    "url": "url",
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
    "bitcoin": "btc",
    "ethereum": "eth",
    "phone": "phone-number",
}


def _format_iocs_misp(iocs: Dict[str, Set[str]]) -> str:
    """Format IOCs as MISP-compatible JSON (Event with Attributes)."""
    attributes = []
    for ioc_type, values in iocs.items():
        misp_type = _MISP_TYPE_MAP.get(ioc_type, "comment")
        for v in values:
            attributes.append({"type": misp_type, "value": str(v), "to_ids": True})
    event = {
        "Event": {
            "info": "Robin OSINT Export",
            "Attribute": attributes,
        }
    }
    return json.dumps(event, indent=2)


def merge_iocs(*ioc_dicts: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """
    Merge multiple IOC dictionaries.
    
    Args:
        *ioc_dicts: Variable number of IOC dictionaries
        
    Returns:
        Merged IOC dictionary
    """
    merged: Dict[str, Set[str]] = {}
    for ioc_dict in ioc_dicts:
        for ioc_type, values in ioc_dict.items():
            if ioc_type not in merged:
                merged[ioc_type] = set()
            merged[ioc_type].update(values)
    return merged


def log_tor_circuit_rotation(rotation_count: int, exit_node: Optional[str] = None):
    """
    Log Tor circuit rotation event.
    
    Args:
        rotation_count: Number of rotations performed
        exit_node: Exit node nickname (optional)
    """
    msg = f"[TOR] Circuit rotated (rotation #{rotation_count})"
    if exit_node:
        msg += f" - Exit node: {exit_node}"
    logger.info(msg)


def log_tor_exit_node(exit_node_info: Dict[str, any]):
    """
    Log Tor exit node information.
    
    Args:
        exit_node_info: Dictionary with exit node details
    """
    nickname = exit_node_info.get("nickname", "Unknown")
    address = exit_node_info.get("address", "Unknown")
    country = exit_node_info.get("country", "Unknown")
    logger.debug(f"[TOR] Using exit node: {nickname} ({address}, {country})")


def log_tor_metrics(port: int, metrics: Dict[str, any]):
    """
    Log Tor instance metrics.
    
    Args:
        port: Tor port number
        metrics: Dictionary with metrics (requests, successes, failures, etc.)
    """
    requests = metrics.get("requests", 0)
    successes = metrics.get("successes", 0)
    failures = metrics.get("failures", 0)
    success_rate = (successes / requests * 100) if requests > 0 else 0
    logger.debug(
        f"[TOR] Port {port} metrics: {requests} requests, "
        f"{successes} successes, {failures} failures ({success_rate:.1f}% success rate)"
    )


def _markdown_to_reportlab_flowables(text: str) -> list:
    """Convert markdown-like text to ReportLab flowables."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Spacer, Preformatted, ListFlowable, ListItem
    from reportlab.lib.enums import TA_LEFT

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Code", fontName="Courier", fontSize=9, leftIndent=20, rightIndent=20, backColor="#f4f4f4", spaceAfter=6))
    flowables = []
    in_list = False
    list_items = []

    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped:
            if list_items:
                flowables.append(ListFlowable(list_items))
                list_items = []
                in_list = False
            flowables.append(Spacer(1, 6))
            continue

        if stripped.startswith("### "):
            if list_items:
                flowables.append(ListFlowable(list_items))
                list_items = []
            flowables.append(Paragraph(stripped[4:].replace("&", "&amp;").replace("<", "&lt;"), styles["Heading3"]))
            flowables.append(Spacer(1, 4))
        elif stripped.startswith("## "):
            if list_items:
                flowables.append(ListFlowable(list_items))
                list_items = []
            flowables.append(Paragraph(stripped[3:].replace("&", "&amp;").replace("<", "&lt;"), styles["Heading2"]))
            flowables.append(Spacer(1, 6))
        elif stripped.startswith("# "):
            if list_items:
                flowables.append(ListFlowable(list_items))
                list_items = []
            flowables.append(Paragraph(stripped[2:].replace("&", "&amp;").replace("<", "&lt;"), styles["Heading1"]))
            flowables.append(Spacer(1, 8))
        elif stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s", stripped):
            item_text = re.sub(r"^\d+\.\s", "", stripped) if re.match(r"^\d+\.\s", stripped) else stripped[2:]
            item_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item_text.replace("&", "&amp;").replace("<", "&lt;"))
            list_items.append(ListItem(Paragraph(item_text, styles["Normal"])))
            in_list = True
        elif stripped.startswith("  - ") or stripped.startswith("  * ") or (in_list and re.match(r"^\s{2,}", stripped)):
            item_text = re.sub(r"^\s*[-*]\s*", "", stripped).replace("&", "&amp;").replace("<", "&lt;")
            list_items.append(ListItem(Paragraph(item_text, styles["Normal"])))
        else:
            if list_items:
                flowables.append(ListFlowable(list_items))
                list_items = []
                in_list = False
            line_clean = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", stripped.replace("&", "&amp;").replace("<", "&lt;"))
            flowables.append(Paragraph(line_clean, styles["Normal"]))
            flowables.append(Spacer(1, 2))

    if list_items:
        flowables.append(ListFlowable(list_items))
    return flowables


def generate_pdf_report(
    markdown_content: str,
    output_path: str,
    iocs: Optional[Dict[str, Set[str]]] = None,
) -> bool:
    """
    Generate a PDF report from markdown content and optional IOCs.
    Uses ReportLab (pure Python, no system deps like cairo).
    
    Args:
        markdown_content: Markdown-formatted summary/report text.
        output_path: Path for the output PDF file.
        iocs: Optional IOC dictionary to append to the report.
        
    Returns:
        True if PDF was generated successfully, False otherwise.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate
    except ImportError as e:
        logger.error(f"PDF generation requires reportlab: {e}")
        return False

    full_content = markdown_content
    if iocs:
        full_content += "\n\n## Extracted Indicators of Compromise (IOCs)\n\n"
        full_content += format_iocs_for_export(iocs, format="text")

    try:
        doc = SimpleDocTemplate(output_path, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        flowables = _markdown_to_reportlab_flowables(full_content)
        doc.build(flowables)
        logger.info(f"PDF report saved to {output_path}")
        return True
    except Exception as e:
        logger.error(f"PDF generation error: {e}", exc_info=True)
        return False


def generate_pdf_bytes(
    markdown_content: str,
    iocs: Optional[Dict[str, Set[str]]] = None,
) -> Optional[bytes]:
    """
    Generate PDF as bytes from markdown content and optional IOCs.
    Used for in-memory export (e.g., Streamlit download).
    
    Returns:
        PDF bytes if successful, None otherwise.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate
        from io import BytesIO
    except ImportError:
        return None

    full_content = markdown_content
    if iocs:
        full_content += "\n\n## Extracted Indicators of Compromise (IOCs)\n\n"
        full_content += format_iocs_for_export(iocs, format="text")

    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        flowables = _markdown_to_reportlab_flowables(full_content)
        doc.build(flowables)
        return buffer.getvalue()
    except Exception:
        return None

