"""Number platform for the Nanit Sound & Light Machine.

Exposes:
  - ``number.<name>_sound_light_volume`` — sound track volume (0-100%).
"""

from __future__ import annotations

import logging
from typing import ClassVar

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sound & Light volume slider."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([NanitSoundLightVolume(coordinator)])


class NanitSoundLightVolume(NanitSoundLightEntity, NumberEntity):
    """Volume slider (0-100%) for the Sound & Light Machine."""

    _attr_translation_key = "volume"
    _attr_native_min_value: ClassVar[float] = 0
    _attr_native_max_value: ClassVar[float] = 100
    _attr_native_step: ClassVar[float] = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_volume"

    @property
    def native_value(self) -> float | None:
        """Return current volume in HA's 0-100 scale."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.volume
        if value is None:
            return None
        return round(value * 100)

    async def async_set_native_value(self, value: float) -> None:
        """Set volume (0-100% → device 0.0-1.0)."""
        device_value = max(0.0, min(1.0, value / 100.0))
        try:
            await self.coordinator.sound_light.async_set_volume(device_value)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to set volume on %s: %s", self.entity_id, err)
            raise
