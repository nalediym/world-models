"""URL hashing, command redaction, and privacy filtering for collected events.

All functions are deterministic (same input -> same output) so deduplication
on ``(timestamp, source, title)`` still works after filtering.
"""

from __future__ import annotations

import hashlib
import re
from copy import copy
from urllib.parse import urlparse

from life_world_model.types import RawEvent

# ---------------------------------------------------------------------------
# Sensitive domain registry
# ---------------------------------------------------------------------------

SENSITIVE_DOMAINS: set[str] = {
    # Email
    "mail.google.com",
    "outlook.live.com",
    "outlook.office365.com",
    "mail.yahoo.com",
    "mail.proton.me",
    "protonmail.com",
    # Messaging
    "messages.google.com",
    "web.whatsapp.com",
    "web.telegram.org",
    "discord.com",
    "signal.org",
    "messenger.com",
    # Banking / finance
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "paypal.com",
    "venmo.com",
    "mint.com",
    "capitalone.com",
    "usbank.com",
    "schwab.com",
    "fidelity.com",
    # Health
    "myfitnesspal.com",
    "patient.info",
    "mychart.com",
    "webmd.com",
    "zocdoc.com",
    # Dating
    "tinder.com",
    "bumble.com",
    "hinge.co",
    # Adult
    "pornhub.com",
    "xvideos.com",
}

# Words in page/window titles that indicate *activity type* and are safe to
# keep in the clear.  Everything else gets hashed.
_ACTIVITY_KEYWORDS: set[str] = {
    # Development
    "pull", "request", "merge", "commit", "branch", "issue", "pipeline",
    "build", "deploy", "test", "debug", "review", "diff", "ci", "cd",
    # Browsing categories
    "inbox", "compose", "search", "results", "settings", "dashboard",
    "profile", "home", "feed", "explore", "notifications",
    # Productivity
    "calendar", "meeting", "document", "spreadsheet", "presentation",
    "slide", "sheet", "doc", "note", "task", "project", "board",
    # Reference / learning
    "stack", "overflow", "documentation", "docs", "tutorial", "guide",
    "wikipedia", "article", "blog", "post", "video", "playlist",
    # Communication
    "chat", "message", "channel", "thread", "call", "zoom", "slack",
    # Finance
    "invoice", "payment", "order", "checkout", "cart",
    # Shell
    "terminal", "shell", "console",
}

# Patterns that look like secrets in shell arguments.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),          # OpenAI-style keys
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),             # GitHub PAT
    re.compile(r"ghs_[A-Za-z0-9]{20,}"),             # GitHub App token
    re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"),        # GitLab PAT
    re.compile(r"xox[bpras]-[A-Za-z0-9\-]{10,}"),    # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                  # AWS access key
    re.compile(r"AIza[A-Za-z0-9_\-]{35}"),            # Google API key
    re.compile(r"bearer\s+\S{20,}", re.IGNORECASE),   # Bearer tokens
]

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_HOME_PATH_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._\-]+")


def _truncated_hash(value: str, length: int = 8) -> str:
    """Return a deterministic truncated SHA-256 hex digest."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def hash_url(url: str) -> str:
    """Hash a URL while preserving the domain for analysis.

    Returns ``'domain.com/h:abc123'`` where *abc123* is a truncated hash of
    the full URL.  This allows pattern analysis on domains while protecting
    specific pages visited.
    """
    parsed = urlparse(url)
    domain = parsed.netloc or "unknown"
    path_hash = _truncated_hash(url)
    return f"{domain}/h:{path_hash}"


def hash_url_paranoid(url: str) -> str:
    """Hash the entire URL including domain.

    Returns ``'h:<hash>'`` — only the activity category can be inferred from
    surrounding context.
    """
    return f"h:{_truncated_hash(url, length=12)}"


def redact_shell_command(command: str) -> str:
    """Redact potentially sensitive parts of a shell command.

    Preserves the command name (first token) but hashes arguments that might
    contain file paths with usernames, API keys/tokens, email addresses, or
    IP addresses.
    """
    parts = command.split()
    if not parts:
        return command

    cmd_name = parts[0]
    if len(parts) == 1:
        return cmd_name

    redacted_args: list[str] = []
    for arg in parts[1:]:
        redacted = arg

        # Check secret patterns first (highest priority).
        for pattern in _SECRET_PATTERNS:
            if pattern.search(redacted):
                redacted = f"[REDACTED:h:{_truncated_hash(arg)}]"
                break

        if redacted != f"[REDACTED:h:{_truncated_hash(arg)}]":
            # Email addresses
            redacted = _EMAIL_RE.sub(
                lambda m: f"[email:h:{_truncated_hash(m.group(0))}]",
                redacted,
            )
            # IP addresses
            redacted = _IP_RE.sub(
                lambda m: f"[ip:h:{_truncated_hash(m.group(0))}]",
                redacted,
            )
            # Home directory paths with usernames
            redacted = _HOME_PATH_RE.sub(
                lambda m: f"/Users/[user:h:{_truncated_hash(m.group(0))}]",
                redacted,
            )

        redacted_args.append(redacted)

    return " ".join([cmd_name] + redacted_args)


def hash_title(title: str) -> str:
    """Hash page/window titles while preserving key activity words.

    Keeps words that indicate activity type (e.g. ``'Pull Request'``,
    ``'inbox'``, ``'Stack Overflow'``) but hashes specific content words.
    """
    words = title.split()
    result: list[str] = []
    for word in words:
        # Strip punctuation for keyword matching but preserve it in output.
        cleaned = re.sub(r"[^\w]", "", word).lower()
        if cleaned in _ACTIVITY_KEYWORDS:
            result.append(word)
        else:
            result.append(f"[h:{_truncated_hash(word)}]")
    return " ".join(result)


def hash_title_paranoid(title: str) -> str:
    """Hash the entire title.  Returns ``'h:<hash>'``."""
    return f"h:{_truncated_hash(title, length=12)}"


def is_sensitive_url(url: str) -> bool:
    """Return ``True`` if *url* points to a likely sensitive domain.

    Checks against ``SENSITIVE_DOMAINS`` and also recognises URL patterns
    that indicate private content (login pages, account settings, etc.).
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Exact match
    if domain in SENSITIVE_DOMAINS:
        return True

    # Subdomain match: e.g. ``online.chase.com`` should match ``chase.com``
    for sensitive in SENSITIVE_DOMAINS:
        if domain.endswith("." + sensitive):
            return True

    # Path-based heuristics
    path_lower = (parsed.path or "").lower()
    sensitive_paths = {
        "/login", "/signin", "/sign-in", "/auth",
        "/account", "/settings/security", "/billing",
        "/password", "/2fa", "/mfa",
    }
    for sp in sensitive_paths:
        if path_lower.startswith(sp):
            return True

    return False


# ---------------------------------------------------------------------------
# Privacy filter (applied between collection and storage)
# ---------------------------------------------------------------------------

_ACTIVITY_CATEGORIES: dict[str, str] = {
    "github.com": "development",
    "gitlab.com": "development",
    "stackoverflow.com": "development",
    "docs.python.org": "development",
    "developer.apple.com": "development",
    "google.com": "search",
    "duckduckgo.com": "search",
    "youtube.com": "media",
    "netflix.com": "media",
    "spotify.com": "media",
    "twitter.com": "social",
    "x.com": "social",
    "reddit.com": "social",
    "linkedin.com": "social",
    "facebook.com": "social",
    "instagram.com": "social",
    "notion.so": "productivity",
    "figma.com": "productivity",
    "docs.google.com": "productivity",
    "sheets.google.com": "productivity",
    "slides.google.com": "productivity",
}


def _categorize_domain(domain: str | None) -> str:
    """Return a broad activity category for a domain, or ``'other'``."""
    if not domain:
        return "other"
    domain_lower = domain.lower()
    for key, category in _ACTIVITY_CATEGORIES.items():
        if domain_lower == key or domain_lower.endswith("." + key):
            return category
    return "other"


def apply_privacy_filter(events: list[RawEvent], mode: str) -> list[RawEvent]:
    """Apply privacy filtering to collected events based on *mode*.

    Modes:

    ``"standard"``
        Pass-through — no modifications.
    ``"enhanced"``
        Hash URLs (preserve domain), redact shell arguments, hash sensitive
        titles, fully hash sensitive URLs.
    ``"paranoid"``
        Hash everything including domains; only keep activity category.

    This function returns **new** ``RawEvent`` instances; the originals are
    never mutated.
    """
    if mode == "standard":
        return events

    if mode not in ("enhanced", "paranoid"):
        raise ValueError(f"Unknown privacy mode: {mode!r}")

    filtered: list[RawEvent] = []
    for event in events:
        e = copy(event)

        if mode == "enhanced":
            _apply_enhanced(e)
        elif mode == "paranoid":
            _apply_paranoid(e)

        filtered.append(e)

    return filtered


def _apply_enhanced(event: RawEvent) -> None:
    """Mutate *event* in place with enhanced-mode redaction."""
    # URLs
    if event.url:
        if is_sensitive_url(event.url):
            event.url = hash_url_paranoid(event.url)
            # Also hash the title for sensitive pages
            if event.title:
                event.title = hash_title_paranoid(event.title)
        else:
            event.url = hash_url(event.url)

    # Shell commands — redact arguments
    if event.source == "shell" and event.title:
        event.title = redact_shell_command(event.title)

    # Titles (non-shell, non-sensitive): keep activity keywords
    if event.source != "shell" and event.title and event.url:
        # Only hash if not already hashed by sensitive URL handling above
        if not event.title.startswith("h:"):
            event.title = hash_title(event.title)

    # Domain stays visible in enhanced mode


def _apply_paranoid(event: RawEvent) -> None:
    """Mutate *event* in place with paranoid-mode redaction."""
    # Categorize before hashing
    category = _categorize_domain(event.domain)

    # Hash everything
    if event.url:
        event.url = hash_url_paranoid(event.url)
    if event.title:
        event.title = hash_title_paranoid(event.title)
    if event.domain:
        event.domain = f"[{category}]"

    # Metadata may contain sensitive info
    if event.metadata:
        event.metadata = {"category": category}
