"""Sensor platform for the Nanit Sound & Light Machine.

Exposes:
  - ``sensor.<name>_sound_light_temperature`` — °C (primary)
  - ``sensor.<name>_sound_light_humidity``    — % (primary)
  - ``sensor.<name>_sound_light_connection_mode`` — local/cloud/unavailable (diagnostic)
"""

from __future__ import annotations

from typing import ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0

# Possible values reported by ``NanitSoundLight.connection_mode``. Kept here
# so the enum sensor's options stay in sync with the protocol implementation.
_CONNECTION_MODES: list[str] = ["local", "cloud", "unavailable"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up speaker sensors (temperature, humidity, connection mode)."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            NanitSoundLightTemperature(coordinator),
            NanitSoundLightHumidity(coordinator),
            NanitSoundLightConnectionMode(coordinator),
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


class NanitSoundLightConnectionMode(NanitSoundLightEntity, SensorEntity):
    """Transport the coordinator is currently using to reach the speaker.

    One of ``"local"`` (direct WebSocket to the speaker on the LAN),
    ``"cloud"`` (relay via ``remote.nanit.com``), or ``"unavailable"``
    (no active connection). Diagnostic category — useful when
    troubleshooting laggy commands or missing temperature/humidity
    readings.
    """

    _attr_translation_key = "connection_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options: ClassVar[list[str]] = _CONNECTION_MODES

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_connection_mode"

    @property
    def available(self) -> bool:
        """Always available once the integration is loaded.

        The whole point of this sensor is to *report* the connection
        state — including the ``"unavailable"`` mode — so it can't
        itself be unavailable while the underlying coordinator exists.
        """
        return True

    @property
    def native_value(self) -> str:
        """Return the current transport mode."""
        return self.coordinator.sound_light.connection_mode
