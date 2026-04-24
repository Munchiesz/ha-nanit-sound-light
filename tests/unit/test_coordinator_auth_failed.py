"""Tests for the AUTH_FAILED → reauth-flow pathway.

Background loops in ``NanitSoundLight`` fire ``SoundLightEventKind.AUTH_FAILED``
when they hit a ``NanitAuthError`` they can't recover from. The coordinator
turns that into ``ConfigEntry.async_start_reauth`` so the user sees an
actionable reconfigure card instead of a silent log entry. These tests pin
that wiring — they do not spin up a real coordinator, they drive the pure
``_on_sl_event`` branch that handles the event.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.nanit_sound_light.aionanit_sl.models import (
    SoundLightEvent,
    SoundLightEventKind,
    SoundLightFullState,
)
from custom_components.nanit_sound_light.coordinator import NanitSoundLightCoordinator


def _make_coordinator(has_active_reauth: bool = False) -> NanitSoundLightCoordinator:
    """Build a coordinator by bypassing ``__init__`` — the branch we test
    is pure state reading + a call into ``config_entry.async_start_reauth``,
    so we don't need the full DataUpdateCoordinator plumbing."""
    coord = NanitSoundLightCoordinator.__new__(NanitSoundLightCoordinator)
    coord.hass = MagicMock()
    coord.sound_light = SimpleNamespace(speaker_uid="speaker-xyz", connected=False)
    coord.connected = False

    entry = MagicMock()
    entry.async_get_active_flow = MagicMock(return_value=has_active_reauth)
    entry.async_start_reauth = MagicMock()
    coord.config_entry = entry  # type: ignore[assignment]

    # async_set_updated_data is inherited from DataUpdateCoordinator, which
    # we also bypassed — stub it so the CONNECTION_CHANGE branch (unused
    # here) wouldn't crash if something falls through.
    coord.async_set_updated_data = MagicMock()  # type: ignore[method-assign]
    return coord


def test_auth_failed_event_starts_reauth_flow() -> None:
    coord = _make_coordinator(has_active_reauth=False)
    event = SoundLightEvent(
        kind=SoundLightEventKind.AUTH_FAILED,
        state=SoundLightFullState(),
    )

    coord._on_sl_event(event)

    coord.config_entry.async_start_reauth.assert_called_once_with(coord.hass)


def test_auth_failed_event_is_suppressed_while_reauth_already_running() -> None:
    """Firing AUTH_FAILED from multiple loops at once shouldn't queue up
    duplicate reauth flows."""
    coord = _make_coordinator(has_active_reauth=True)
    event = SoundLightEvent(
        kind=SoundLightEventKind.AUTH_FAILED,
        state=SoundLightFullState(),
    )

    coord._on_sl_event(event)

    coord.config_entry.async_start_reauth.assert_not_called()


def test_auth_failed_event_does_not_push_state_update() -> None:
    """AUTH_FAILED is a side-channel signal — it shouldn't dispatch the
    state snapshot to entities (there's nothing new to render)."""
    coord = _make_coordinator()
    event = SoundLightEvent(
        kind=SoundLightEventKind.AUTH_FAILED,
        state=SoundLightFullState(),
    )

    coord._on_sl_event(event)

    coord.async_set_updated_data.assert_not_called()
