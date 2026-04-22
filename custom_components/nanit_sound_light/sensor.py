"""Sensor platform for the Nanit Sound & Light Machine.

Exposes the speaker's environmental sensors:
  - ``sensor.<name>_sound_light_temperature`` — °C
  - ``sensor.<name>_sound_light_humidity``    — %
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up temperature and humidity sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            NanitSoundLightTemperature(coordinator),
            NanitSoundLightHumidity(coordinator),
        ]
    )


class NanitSoundLightTemperature(NanitSoundLightEntity, SensorEntity):
    """Ambient temperature reported by the speaker, in °C."""

    _attr_translation_key = "temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature in °C."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.temperature_c


class NanitSoundLightHumidity(NanitSoundLightEntity, SensorEntity):
    """Ambient humidity reported by the speaker, in %RH."""

    _attr_translation_key = "humidity"
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_humidity"

    @property
    def native_value(self) -> float | None:
        """Return the current relative humidity in %."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.humidity_pct
