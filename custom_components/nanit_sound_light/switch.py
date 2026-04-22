"""Switch platform for the Nanit Sound & Light Machine.

Exposes two switches:
  - ``switch.<name>_sound_light_sound``  — play/pause the sound track
  - ``switch.<name>_sound_light_power``  — device-level on/off (standby)

Both use an optimistic-state + command-grace pattern so the UI doesn't
bounce back to the old state on the device's stale echo.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

_COMMAND_GRACE_PERIOD: float = 15.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sound & Light switches."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            NanitSoundLightSoundSwitch(coordinator),
            NanitSoundLightPowerSwitch(coordinator),
        ]
    )


class _BaseSLSwitch(NanitSoundLightEntity, SwitchEntity):
    """Shared logic for Sound & Light switches (optimistic + grace period)."""

    _state_attr: str = ""  # subclass sets: "sound_on" or "power_on"

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._command_is_on: bool | None = None
        self._command_ts: float = 0.0

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on, with command-grace override."""
        if (
            self._command_is_on is not None
            and time.monotonic() - self._command_ts < _COMMAND_GRACE_PERIOD
        ):
            return self._command_is_on
        if self.coordinator.data is None:
            return None
        value = getattr(self.coordinator.data, self._state_attr, None)
        return bool(value) if value is not None else None

    def _clear_grace(self) -> None:
        self._command_is_on = None

    async def _async_apply(self, on: bool) -> None:
        """Subclass hook — call the underlying sound_light command."""
        raise NotImplementedError

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on."""
        self._command_is_on = True
        self._command_ts = time.monotonic()
        self.async_write_ha_state()
        try:
            await self._async_apply(True)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to turn on %s: %s", self.entity_id, err)
            self._clear_grace()
            self.async_write_ha_state()
            raise

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off."""
        self._command_is_on = False
        self._command_ts = time.monotonic()
        self.async_write_ha_state()
        try:
            await self._async_apply(False)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to turn off %s: %s", self.entity_id, err)
            self._clear_grace()
            self.async_write_ha_state()
            raise


class NanitSoundLightSoundSwitch(_BaseSLSwitch):
    """Play/pause the sound track on the Sound & Light Machine."""

    _attr_translation_key = "sound"
    _state_attr = "sound_on"

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_sound"

    async def _async_apply(self, on: bool) -> None:
        await self.coordinator.sound_light.async_set_sound_on(on)


class NanitSoundLightPowerSwitch(_BaseSLSwitch):
    """Whole-device standby switch for the Sound & Light Machine.

    Turning this off puts the device in standby — the lamp and sound both
    go off and become unresponsive until power is turned back on.
    """

    _attr_translation_key = "power"
    _state_attr = "power_on"

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_power"

    async def _async_apply(self, on: bool) -> None:
        await self.coordinator.sound_light.async_set_power(on)
