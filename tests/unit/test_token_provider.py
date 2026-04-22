"""Tests for NanitPiggybackTokenProvider."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aionanit import NanitAuthError

from custom_components.nanit_sound_light.token_provider import NanitPiggybackTokenProvider


def _make_hass(entry: object | None) -> MagicMock:
    """Build a minimal ``hass`` stub whose config_entries returns ``entry``."""
    hass = MagicMock()
    hass.config_entries.async_get_entry = MagicMock(return_value=entry)
    return hass


async def test_returns_access_token() -> None:
    entry = SimpleNamespace(data={"access_token": "abc-123"})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id")
    assert await provider.async_get_access_token() == "abc-123"


async def test_missing_entry_raises_auth_error() -> None:
    hass = _make_hass(None)
    provider = NanitPiggybackTokenProvider(hass, "entry-id")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()


async def test_entry_with_no_token_raises_auth_error() -> None:
    entry = SimpleNamespace(data={})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()


async def test_empty_token_raises_auth_error() -> None:
    entry = SimpleNamespace(data={"access_token": ""})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()
