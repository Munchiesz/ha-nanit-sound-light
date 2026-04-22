"""Tests for NanitSoundLightTrack option validation (v0.2.2)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.nanit_sound_light.select import NanitSoundLightTrack


def _make_track(
    available: tuple[str, ...] | None, current: str | None = None
) -> NanitSoundLightTrack:
    coordinator = MagicMock()
    coordinator.data = SimpleNamespace(available_tracks=available, current_track=current)
    coordinator.baby = SimpleNamespace(camera_uid="cam-123", name="David")
    coordinator.connected = True
    coordinator.last_update_success = True
    coordinator.sound_light = MagicMock()
    coordinator.sound_light.async_set_track = AsyncMock()

    track = NanitSoundLightTrack.__new__(NanitSoundLightTrack)
    track.coordinator = coordinator  # type: ignore[attr-defined]
    return track


async def test_valid_track_forwards_to_device() -> None:
    track = _make_track(("Ocean", "Heartbeat"))
    await track.async_select_option("Ocean")
    track.coordinator.sound_light.async_set_track.assert_awaited_once_with("Ocean")


async def test_invalid_track_raises_without_calling_device() -> None:
    track = _make_track(("Ocean", "Heartbeat"))
    with pytest.raises(HomeAssistantError, match="not available"):
        await track.async_select_option("Unknown Song")
    track.coordinator.sound_light.async_set_track.assert_not_called()


async def test_empty_options_rejects_any_selection() -> None:
    """When the device hasn't advertised any tracks, every selection is rejected."""
    track = _make_track(available=None)
    # ``options`` now returns the placeholder "— no tracks reported —"; selecting
    # anything else surfaces the "No tracks are currently available" error, and
    # selecting the placeholder itself surfaces the "Wait for state" error.
    with pytest.raises(HomeAssistantError, match="No tracks are currently available"):
        await track.async_select_option("Ocean")
    track.coordinator.sound_light.async_set_track.assert_not_called()


async def test_placeholder_selection_is_rejected_with_clear_message() -> None:
    track = _make_track(available=None)
    with pytest.raises(HomeAssistantError, match="Wait for the device"):
        await track.async_select_option("— no tracks reported —")
    track.coordinator.sound_light.async_set_track.assert_not_called()
