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
from homeassistant.helpers.restore_state import RestoreEntity

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


class NanitSoundLightVolume(NanitSoundLightEntity, NumberEntity, RestoreEntity):
    """Volume slider (0-100%) for the Sound & Light Machine.

    ``RestoreEntity`` lets the slider come back with the last known
    percentage after HA restart, instead of showing ``unknown`` until the
    next push from the speaker.
    """

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
        self._restored_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last-known volume across HA restarts."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._restored_value = float(last.state)
            except (TypeError, ValueError):
                self._restored_value = None

    @property
    def native_value(self) -> float | None:
        """Return current volume in HA's 0-100 scale.

        Round-trip is stable: we use banker's rounding (`round()`), so when
        the user sets 56 we write 0.56, and the device echoes 0.56 which
        rounds back to 56 — no UI bounce. Because we immediately write back
        the rounded-derived value, there's no float drift.
        """
        state = self.coordinator.data
        if state is None or state.volume is None:
            return self._restored_value
        return round(state.volume * 100)

    async def async_set_native_value(self, value: float) -> None:
        """Set volume (0-100% → device 0.0-1.0)."""
        device_value = max(0.0, min(1.0, value / 100.0))
        try:
            await self.coordinator.sound_light.async_set_volume(device_value)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to set volume on %s: %s", self.entity_id, err)
            raise
