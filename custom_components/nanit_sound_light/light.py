"""Light platform for the Nanit Sound & Light Machine — on/off (v0.1.0)."""

from __future__ import annotations

import logging
import time
from typing import Any, ClassVar

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

# After a command, ignore contradicting push echoes for this many seconds
# so the UI doesn't bounce back to the old state before the device confirms.
_COMMAND_GRACE_PERIOD: float = 15.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sound & Light lamp entity."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([NanitSoundLightLamp(coordinator)])


class NanitSoundLightLamp(NanitSoundLightEntity, LightEntity):
    """Nanit Sound & Light Machine lamp — on/off only (v0.1.0).

    Brightness, HS color, track selection, volume, and routines are
    intentionally deferred to later releases. The full wire protocol
    exists in ``aionanit_sl/`` — we just don't wire it up yet.
    """

    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_translation_key = "lamp"

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        baby = coordinator.baby
        self._attr_unique_id = f"{baby.camera_uid}_sound_light_lamp"
        self._command_is_on: bool | None = None
        self._command_ts: float = 0.0

    @property
    def is_on(self) -> bool | None:
        """Return True if the lamp is on, with command-grace override."""
        if (
            self._command_is_on is not None
            and time.monotonic() - self._command_ts < _COMMAND_GRACE_PERIOD
        ):
            return self._command_is_on

        if self.coordinator.data is None:
            return None
        state = self.coordinator.data
        if state.light_enabled is not None:
            return state.light_enabled
        if state.brightness is not None:
            return state.brightness > 0.001
        return None

    def _clear_grace(self) -> None:
        self._command_is_on = None

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the lamp."""
        self._command_is_on = True
        self._command_ts = time.monotonic()
        self.async_write_ha_state()

        try:
            await self.coordinator.sound_light.async_set_light_enabled(True)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to turn on Sound & Light lamp: %s", err)
            self._clear_grace()
            self.async_write_ha_state()
            raise

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the lamp."""
        self._command_is_on = False
        self._command_ts = time.monotonic()
        self.async_write_ha_state()

        try:
            await self.coordinator.sound_light.async_set_light_enabled(False)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to turn off Sound & Light lamp: %s", err)
            self._clear_grace()
            self.async_write_ha_state()
            raise
