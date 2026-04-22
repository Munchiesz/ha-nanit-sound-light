"""Tests for the diagnostics redaction (v0.3.0)."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.nanit_sound_light.aionanit_sl.models import SoundLightFullState
from custom_components.nanit_sound_light.diagnostics import (
    _REDACT_ENTRY_KEYS,
    async_get_config_entry_diagnostics,
)


def _make_entry(runtime: object | None) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "sl-entry-123"
    entry.title = "David Sound & Light"
    entry.state = SimpleNamespace(value="loaded")
    entry.disabled_by = None
    entry.source = "user"
    entry.unique_id = "speaker-uid-999"
    entry.data = {
        "nanit_entry_id": "nanit-entry-abc",
        "camera_uid": "cam-xyz",
        "camera_name": "David",
        "speaker_uid": "speaker-uid-999",
        "speaker_ip": "192.168.1.42",
    }
    entry.options = {}
    entry.runtime_data = runtime
    return entry


async def test_diagnostics_redacts_sensitive_entry_keys() -> None:
    entry = _make_entry(runtime=None)
    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    data = result["entry"]["data"]
    for key in _REDACT_ENTRY_KEYS:
        assert data[key] == "**REDACTED**", f"{key} was not redacted"

    # Non-sensitive fields remain readable.
    assert data["camera_name"] == "David"


async def test_diagnostics_handles_missing_runtime() -> None:
    """If setup failed and runtime is None, diagnostics should still
    return a usable dump rather than crashing."""
    entry = _make_entry(runtime=None)
    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["runtime"]["loaded"] is False
    assert result["runtime"]["state"] is None
    assert result["runtime"]["connection_mode"] is None


async def test_diagnostics_includes_runtime_state_snapshot() -> None:
    state = SoundLightFullState(
        brightness=0.6,
        light_enabled=True,
        color_r=0.25,
        color_g=0.9,
        volume=0.5,
        sound_on=False,
        power_on=True,
        available_tracks=("Ocean", "Heartbeat"),
        temperature_c=22.1,
        humidity_pct=45.0,
    )
    coordinator = MagicMock()
    coordinator.data = state
    coordinator.connected = True
    coordinator.last_update_success = True

    runtime = SimpleNamespace(
        coordinator=coordinator,
        sound_light=SimpleNamespace(connection_mode="local"),
    )
    entry = _make_entry(runtime=runtime)

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    runtime_block = result["runtime"]
    assert runtime_block["loaded"] is True
    assert runtime_block["coordinator_connected"] is True
    assert runtime_block["connection_mode"] == "local"
    snapshot = runtime_block["state"]
    assert snapshot["brightness"] == pytest.approx(0.6)
    assert snapshot["light_enabled"] is True
    # ``dataclasses.asdict`` preserves tuple field values — HA's diagnostics
    # framework later serializes to JSON which emits arrays, but in-memory
    # the snapshot is still a tuple. We just need the values intact.
    assert tuple(snapshot["available_tracks"]) == ("Ocean", "Heartbeat")
    assert snapshot["temperature_c"] == pytest.approx(22.1)


async def test_diagnostics_state_snapshot_matches_asdict() -> None:
    """Defensive: the redaction helper should not strip any of the state
    field names we expect to keep (all SL state is public-ish)."""
    state = SoundLightFullState(brightness=0.5)
    coordinator = MagicMock()
    coordinator.data = state
    coordinator.connected = True
    coordinator.last_update_success = True

    runtime = SimpleNamespace(
        coordinator=coordinator,
        sound_light=SimpleNamespace(connection_mode="cloud"),
    )
    entry = _make_entry(runtime=runtime)

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)
    snapshot_keys = set(result["runtime"]["state"].keys())
    expected_keys = set(dataclasses.asdict(state).keys())
    assert snapshot_keys == expected_keys
