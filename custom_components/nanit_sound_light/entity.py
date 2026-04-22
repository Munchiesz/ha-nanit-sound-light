"""Base entity for the Nanit Sound & Light Machine."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NanitSoundLightCoordinator
from .sanitize import sanitize_name


class NanitSoundLightEntity(CoordinatorEntity[NanitSoundLightCoordinator]):
    """Base entity for the Nanit Sound & Light Machine (standalone speaker)."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the speaker device."""
        baby = self.coordinator.baby
        return DeviceInfo(
            identifiers={(DOMAIN, f"{baby.camera_uid}_sound_light")},
            name=f"{sanitize_name(baby.name)} Sound & Light",
            manufacturer="Nanit",
            model="Sound & Light Machine",
        )

    @property
    def available(self) -> bool:
        """Return True when the coordinator has data and the device is connected."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.connected
        )
