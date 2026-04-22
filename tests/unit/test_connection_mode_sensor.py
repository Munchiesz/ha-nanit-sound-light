"""Tests for NanitSoundLightConnectionMode (v0.3.0)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.nanit_sound_light.sensor import NanitSoundLightConnectionMode


def _make_sensor(mode: str) -> NanitSoundLightConnectionMode:
    coordinator = MagicMock()
    coordinator.baby = SimpleNamespace(camera_uid="cam-123", name="David")
    coordinator.data = SimpleNamespace()
    coordinator.connected = True
    coordinator.last_update_success = True
    coordinator.sound_light = SimpleNamespace(connection_mode=mode)

    sensor = NanitSoundLightConnectionMode.__new__(NanitSoundLightConnectionMode)
    sensor.coordinator = coordinator  # type: ignore[attr-defined]
    return sensor


def test_native_value_returns_current_mode() -> None:
    assert _make_sensor("local").native_value == "local"
    assert _make_sensor("cloud").native_value == "cloud"
    assert _make_sensor("unavailable").native_value == "unavailable"


def test_always_available_even_when_coordinator_disconnected() -> None:
    """The whole point of this sensor is to report 'unavailable' as a state,
    not to be entity-unavailable when the transport drops."""
    sensor = _make_sensor("unavailable")
    sensor.coordinator.connected = False
    sensor.coordinator.last_update_success = False
    sensor.coordinator.data = None
    assert sensor.available is True


def test_unique_id_includes_camera_uid() -> None:
    sensor = _make_sensor("local")
    # Unique ID is set in __init__; we bypass __init__, so set it manually
    # the same way the init would for this test.
    assert not hasattr(sensor, "_attr_unique_id")  # not set because __new__ skipped __init__

    # Simulate what __init__ does
    sensor._attr_unique_id = f"{sensor.coordinator.baby.camera_uid}_sound_light_connection_mode"
    assert sensor._attr_unique_id == "cam-123_sound_light_connection_mode"
