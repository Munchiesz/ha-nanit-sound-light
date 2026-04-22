"""Tests for the grace-period state machine on Sound & Light switches.

Covers the v0.2.2 fix: when the device pushes a state that matches the
commanded value, the optimistic-state grace should clear *early* so that
subsequent contradicting pushes aren't masked for the full 15 s window.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.nanit_sound_light.switch import (
    _COMMAND_GRACE_PERIOD,
    NanitSoundLightSoundSwitch,
)


def _make_switch(sound_on: bool | None = None) -> NanitSoundLightSoundSwitch:
    """Build a NanitSoundLightSoundSwitch with a stubbed coordinator."""
    coordinator = MagicMock()
    coordinator.data = SimpleNamespace(sound_on=sound_on)
    coordinator.baby = SimpleNamespace(camera_uid="cam-123", name="David")
    coordinator.connected = True
    coordinator.last_update_success = True

    switch = NanitSoundLightSoundSwitch.__new__(NanitSoundLightSoundSwitch)
    # Bypass CoordinatorEntity.__init__ — it needs a real hass. We only test
    # pure state-machine logic, so attach the fields by hand.
    switch.coordinator = coordinator  # type: ignore[attr-defined]
    switch._command_is_on = None
    switch._command_ts = 0.0
    return switch


def test_is_on_reads_coordinator_when_no_command_pending() -> None:
    """Without a pending command, is_on just reads the latest push state."""
    sw = _make_switch(sound_on=True)
    assert sw.is_on is True

    sw.coordinator.data = SimpleNamespace(sound_on=False)
    assert sw.is_on is False


def test_is_on_returns_none_when_coordinator_empty() -> None:
    """No pending command + no data → None (unknown)."""
    sw = _make_switch(sound_on=None)
    sw.coordinator.data = None
    assert sw.is_on is None


def test_grace_returns_optimistic_value_during_window() -> None:
    """Optimistic value is returned for the full grace period when the
    coordinator still disagrees with the command (stale-echo defence)."""
    sw = _make_switch(sound_on=False)  # device still reporting OFF
    sw._command_is_on = True  # we just commanded ON
    sw._command_ts = time.monotonic()

    assert sw.is_on is True  # optimistic wins during grace


def test_grace_expires_after_window() -> None:
    """Once the grace window has elapsed, the coordinator value wins."""
    sw = _make_switch(sound_on=False)
    sw._command_is_on = True
    sw._command_ts = time.monotonic() - (_COMMAND_GRACE_PERIOD + 1)

    assert sw.is_on is False  # coordinator value, grace expired


def test_handle_coordinator_update_clears_grace_on_match() -> None:
    """When the device pushes a value matching the command, grace clears
    early so subsequent contradicting pushes bubble through."""
    sw = _make_switch(sound_on=True)  # device confirmed our ON command
    sw._command_is_on = True
    sw._command_ts = time.monotonic()

    # Stub async_write_ha_state → no-op for this pure-logic test
    sw.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    sw._handle_coordinator_update()

    assert sw._command_is_on is None  # grace cleared


def test_handle_coordinator_update_keeps_grace_on_mismatch() -> None:
    """Stale-echo case: device push contradicts the command. Grace stays."""
    sw = _make_switch(sound_on=False)  # device still reports old state
    sw._command_is_on = True
    sw._command_ts = time.monotonic()

    sw.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    sw._handle_coordinator_update()

    assert sw._command_is_on is True  # grace preserved


def test_handle_coordinator_update_noop_when_no_command() -> None:
    """No pending command → the handler shouldn't touch state."""
    sw = _make_switch(sound_on=True)
    sw._command_is_on = None

    sw.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    sw._handle_coordinator_update()

    assert sw._command_is_on is None  # still None, unchanged


def test_contradicting_push_after_grace_clear_bubbles_through() -> None:
    """The key end-to-end scenario v0.2.2 fixes:

    1. User turns ON. _command_is_on=True, optimistic.
    2. Device confirms ON. Grace clears (handle_coordinator_update).
    3. Device rolls back and pushes OFF shortly after.
    4. is_on should return False — the rollback is authoritative because
       grace is already cleared.

    Without the fix, step 2 wouldn't clear grace, and step 4's OFF push
    would be masked for the full remaining grace window.
    """
    sw = _make_switch(sound_on=True)
    sw._command_is_on = True
    sw._command_ts = time.monotonic()
    sw.async_write_ha_state = MagicMock()  # type: ignore[method-assign]

    # Step 2 — device confirms.
    sw._handle_coordinator_update()
    assert sw._command_is_on is None

    # Step 3 — device rolls back.
    sw.coordinator.data = SimpleNamespace(sound_on=False)

    # Step 4 — UI should now reflect the rollback, not the original command.
    assert sw.is_on is False
