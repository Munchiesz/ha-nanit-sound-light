"""Tests for NanitPiggybackTokenProvider.

Covers both the token-reading path and the repair-issue lifecycle
(create on first failure, clear on recovery, idempotent within a state).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")
    assert await provider.async_get_access_token() == "abc-123"


async def test_missing_entry_raises_auth_error() -> None:
    hass = _make_hass(None)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()


async def test_entry_with_no_token_raises_auth_error() -> None:
    entry = SimpleNamespace(data={})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()


async def test_empty_token_raises_auth_error() -> None:
    entry = SimpleNamespace(data={"access_token": ""})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")
    with pytest.raises(NanitAuthError):
        await provider.async_get_access_token()


async def test_surface_issue_on_first_failure_only() -> None:
    """Repair issue is created exactly once, not on every failing call."""
    hass = _make_hass(None)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")

    with patch("custom_components.nanit_sound_light.token_provider.ir") as mock_ir:
        with pytest.raises(NanitAuthError):
            await provider.async_get_access_token()
        with pytest.raises(NanitAuthError):
            await provider.async_get_access_token()
        with pytest.raises(NanitAuthError):
            await provider.async_get_access_token()

        assert mock_ir.async_create_issue.call_count == 1
        assert mock_ir.async_delete_issue.call_count == 0


async def test_clear_issue_on_recovery() -> None:
    """Repair issue is cleared when a failing provider starts working."""
    hass = _make_hass(None)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")

    with patch("custom_components.nanit_sound_light.token_provider.ir") as mock_ir:
        # First call fails — issue created.
        with pytest.raises(NanitAuthError):
            await provider.async_get_access_token()
        assert mock_ir.async_create_issue.call_count == 1

        # Now the nanit entry reappears with a valid token.
        hass.config_entries.async_get_entry.return_value = SimpleNamespace(
            data={"access_token": "new-token"}
        )
        token = await provider.async_get_access_token()
        assert token == "new-token"
        assert mock_ir.async_delete_issue.call_count == 1

        # Another successful call shouldn't re-delete.
        await provider.async_get_access_token()
        assert mock_ir.async_delete_issue.call_count == 1


async def test_no_issue_created_when_happy_path() -> None:
    """If the provider never fails, it never touches the issue registry."""
    entry = SimpleNamespace(data={"access_token": "tok"})
    hass = _make_hass(entry)
    provider = NanitPiggybackTokenProvider(hass, "entry-id", issue_id="issue-key")

    with patch("custom_components.nanit_sound_light.token_provider.ir") as mock_ir:
        await provider.async_get_access_token()
        await provider.async_get_access_token()
        assert mock_ir.async_create_issue.call_count == 0
        assert mock_ir.async_delete_issue.call_count == 0
