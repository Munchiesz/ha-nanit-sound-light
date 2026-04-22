"""Input sanitization — strip XSS vectors from API-provided names.

Text from the Nanit API (baby/speaker names) is rendered in Home Assistant
UI surfaces (entity names, issue placeholders, diagnostics). HTML tags
need to be stripped before display to prevent stored XSS.
"""

from __future__ import annotations

import html
import re

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_name(value: str) -> str:
    """Strip HTML tags and escape entities from an API-provided name.

    Order matters: unescape first so pre-encoded tags like ``&lt;script&gt;``
    become visible to the tag stripper, THEN strip tags, THEN escape any
    remaining entities for safe display.
    """
    cleaned = html.unescape(value)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = html.escape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()
