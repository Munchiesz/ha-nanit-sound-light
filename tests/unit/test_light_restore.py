"""Tests for the light entity's restore-state fallback (H2).

Before v0.4.1 the light only consulted restored values when
``coordinator.data is None``. That check never fired at runtime because
the coordinator pre-seeds ``data`` with an all-``None``
``SoundLightFullState()``, so a user restarting HA while the speaker was
unreachable would see ``is_on``/``brightness`` return ``None`` (unknown)
instead of the last-known values they'd expect from ``RestoreEntity``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.nanit_sound_light.aionanit_sl.models import SoundLightFullState
from custom_components.nanit_sound_light.light import NanitSoundLightLamp


def _make_lamp(
    state: SoundLightFullState | None,
    restored_is_on: bool | None = None,
    restored_brightness: int | None = None,
) -> NanitSoundLightLamp:
    coordinator = MagicMock()
    coordinator.data = state
    coordinator.baby = SimpleNamespace(camera_uid="cam-1", name="Baby")
    coordinator.connected = False
    coordinator.last_update_success = True

    lamp = NanitSoundLightLamp.__new__(NanitSoundLightLamp)
    lamp.coordinator = coordinator  # type: ignore[attr-defined]
    lamp._command_is_on = None
    lamp._command_ts = 0.0
    lamp._restored_is_on = restored_is_on
    lamp._restored_brightness = restored_brightness
    return lamp


def test_is_on_falls_back_to_restored_when_state_fields_are_none() -> None:
    """The coordinator seeds data as ``SoundLightFullState()`` — every
    field is ``None``. Restoration should still kick in because the
    actual device state is unknown."""
    empty_state = SoundLightFullState()  # all fields None
    lamp = _make_lamp(state=empty_state, restored_is_on=True)

    assert lamp.is_on is True


def test_is_on_prefers_live_state_over_restored() -> None:
    state = SoundLightFullState(light_enabled=False)
    lamp = _make_lamp(state=state, restored_is_on=True)

    assert lamp.is_on is False


def test_brightness_falls_back_to_restored_when_field_is_none() -> None:
    empty_state = SoundLightFullState()
    lamp = _make_lamp(state=empty_state, restored_brightness=128)

    assert lamp.brightness == 128


def test_brightness_prefers_live_value() -> None:
    state = SoundLightFullState(brightness=0.5, power_on=True, light_enabled=True)
    lamp = _make_lamp(state=state, restored_brightness=200)

    # 0.5 * 255 = 127.5 → int() truncates to 127
    assert lamp.brightness == 127


def test_is_on_returns_none_with_no_data_and_no_restore() -> None:
    lamp = _make_lamp(state=None, restored_is_on=None)
    assert lamp.is_on is None
