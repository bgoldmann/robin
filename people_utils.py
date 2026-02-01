"""
People OSINT utilities for Robin.
Person input validation (name, email, username, phone).
"""
import re
from typing import List, Optional, Tuple

from utils import logger

# Max lengths (sanitization)
MAX_NAME_LEN = 200
MAX_EMAIL_LEN = 254
MAX_USERNAME_LEN = 100
MAX_PHONE_LEN = 30
MAX_ITEMS = 20  # max emails/usernames/phones per list

# Email: RFC 5322 simplified
EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# Phone: international-ish (digits, +, spaces, dashes, parens)
PHONE_RE = re.compile(
    r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]*$"
)

# Username: alphanumeric, underscore, dot; 1–100 chars
USERNAME_RE = re.compile(
    r"^[a-zA-Z0-9_.]{1,100}$"
)

# Dangerous chars (reuse query spirit)
DANGEROUS_PATTERNS = [
    re.compile(r"[<>\"']"),
    re.compile(r"[;&|`$]"),
]


def _normalize_list(value: Optional[str], max_items: int = MAX_ITEMS) -> List[str]:
    """Split comma/newline-separated string into stripped non-empty list, capped."""
    if not value or not isinstance(value, str):
        return []
    items = [
        x.strip()
        for x in re.split(r"[\s,]+", value.strip())
        if x.strip()
    ]
    return list(dict.fromkeys(items))[:max_items]


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    if not email or len(email) > MAX_EMAIL_LEN:
        return False, "Invalid or too long email"
    if not EMAIL_RE.match(email):
        return False, "Invalid email format"
    for p in DANGEROUS_PATTERNS:
        if p.search(email):
            return False, "Email contains disallowed characters"
    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    if not phone or len(phone) > MAX_PHONE_LEN:
        return False, "Invalid or too long phone"
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return False, "Phone number too short"
    if not PHONE_RE.match(phone):
        return False, "Invalid phone format"
    for p in DANGEROUS_PATTERNS:
        if p.search(phone):
            return False, "Phone contains disallowed characters"
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    if not username or len(username) > MAX_USERNAME_LEN:
        return False, "Invalid or too long username"
    if not USERNAME_RE.match(username):
        return False, "Username must be alphanumeric, underscore, or dot (1-100 chars)"
    for p in DANGEROUS_PATTERNS:
        if p.search(username):
            return False, "Username contains disallowed characters"
    return True, None


def validate_name(name: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not name or not isinstance(name, str):
        return True, None  # optional field
    name = name.strip()
    if len(name) > MAX_NAME_LEN:
        return False, f"Name exceeds maximum length of {MAX_NAME_LEN}"
    for p in DANGEROUS_PATTERNS:
        if p.search(name):
            return False, "Name contains disallowed characters"
    return True, None


def validate_person_input(
    name: Optional[str] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    phone: Optional[str] = None,
    emails: Optional[List[str]] = None,
    usernames: Optional[List[str]] = None,
    phones: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate person search input. At least one identifier must be provided.
    Returns (is_valid, error_message).
    """
    # Normalize: single values + comma-separated into lists
    email_list = list(emails or [])
    if email:
        email_list = [email] + email_list
    username_list = list(usernames or [])
    if username:
        username_list = [username] + username_list
    phone_list = list(phones or [])
    if phone:
        phone_list = [phone] + phone_list

    has_any = bool(
        (name and name.strip())
        or email_list
        or username_list
        or phone_list
    )
    if not has_any:
        return False, "At least one of name, email, username, or phone is required"

    ok, err = validate_name(name)
    if not ok:
        return False, err

    for e in email_list:
        ok, err = validate_email(e)
        if not ok:
            return False, f"Email '{e[:30]}...': {err}" if len(e) > 30 else f"Email '{e}': {err}"

    for u in username_list:
        ok, err = validate_username(u)
        if not ok:
            return False, f"Username '{u}': {err}"

    for p in phone_list:
        ok, err = validate_phone(p)
        if not ok:
            return False, f"Phone '{p}': {err}"

    return True, None


def normalize_person_input(
    name: Optional[str] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    """
    Normalize person input into a single dict with lists for emails, usernames, phones.
    Does not validate; call validate_person_input first.
    """
    emails = _normalize_list(email) if email else []
    usernames = _normalize_list(username) if username else []
    phones = _normalize_list(phone) if phone else []
    if email and email.strip() and email.strip() not in emails:
        emails = [email.strip()] + [e for e in emails if e != email.strip()]
    if username and username.strip() and username.strip() not in usernames:
        usernames = [username.strip()] + [u for u in usernames if u != username.strip()]
    if phone and phone.strip() and phone.strip() not in phones:
        phones = [phone.strip()] + [p for p in phones if p != phone.strip()]
    return {
        "name": (name or "").strip() or None,
        "emails": emails,
        "usernames": usernames,
        "phones": phones,
    }
