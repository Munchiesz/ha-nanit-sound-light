"""Tests for sanitize_name."""

from __future__ import annotations

from custom_components.nanit_sound_light.sanitize import sanitize_name


def test_plain_name_untouched() -> None:
    assert sanitize_name("David") == "David"


def test_strips_html_tags() -> None:
    assert sanitize_name("<script>alert(1)</script>David") == "alert(1)David"


def test_unescapes_before_stripping() -> None:
    assert sanitize_name("&lt;b&gt;David&lt;/b&gt;") == "David"


def test_collapses_whitespace() -> None:
    assert sanitize_name("  David   Rose  ") == "David Rose"


def test_escapes_residual_entities() -> None:
    # Ampersand in a real name should be HTML-escaped for safe display.
    assert sanitize_name("A & B") == "A &amp; B"
