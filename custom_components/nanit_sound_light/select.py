"""Select platform for the Nanit Sound & Light Machine.

Exposes:
  - ``select.<name>_sound_light_track`` — choose the currently playing sound
    track from the list the device advertises (Ocean, Heartbeat, etc.).
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

# Shown in the dropdown when the device hasn't (yet) advertised any tracks —
# otherwise HA renders an empty dropdown which is confusing. Selecting this
# placeholder is rejected with a clear error message.
_NO_TRACKS_PLACEHOLDER: str = "— no tracks reported —"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sound & Light track selector."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([NanitSoundLightTrack(coordinator)])


class NanitSoundLightTrack(NanitSoundLightEntity, SelectEntity, RestoreEntity):
    """Track selector — options come from ``available_tracks`` on state.

    ``RestoreEntity`` surfaces the last-known track name across HA
    restarts, including the period before the cloud relay pushes a state
    frame (cloud mode doesn't replay initial state on connect).
    """

    _attr_translation_key = "track"

    def __init__(self, coordinator: NanitSoundLightCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.baby.camera_uid}_sound_light_track"
        self._restored_track: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last-known track name across HA restarts."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (
            None,
            "unknown",
            "unavailable",
            _NO_TRACKS_PLACEHOLDER,
        ):
            self._restored_track = last.state

    @property
    def options(self) -> list[str]:
        """Return the list of tracks the device advertises.

        When the device hasn't yet sent a state push with
        ``available_tracks`` (e.g. just after setup in cloud-relay mode),
        we surface a placeholder so the dropdown isn't empty. Selecting
        the placeholder is rejected in ``async_select_option``.
        """
        if self.coordinator.data is None or not self.coordinator.data.available_tracks:
            return [_NO_TRACKS_PLACEHOLDER]
        return list(self.coordinator.data.available_tracks)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected track."""
        state = self.coordinator.data
        if state is None or state.current_track is None:
            return self._restored_track
        return state.current_track

    async def async_select_option(self, option: str) -> None:
        """Change the active track.

        Validates against ``self.options`` before firing — HA's SelectEntity
        doesn't guard against service calls that bypass the dropdown with an
        invalid value, and the device's firmware behavior on unknown track
        names is unspecified.
        """
        if option == _NO_TRACKS_PLACEHOLDER:
            raise HomeAssistantError(
                "No tracks have been reported by the speaker yet. "
                "Wait for the device to push its state, then try again."
            )
        if self.coordinator.data is None or not self.coordinator.data.available_tracks:
            raise HomeAssistantError("No tracks are currently available from the speaker.")
        if option not in self.coordinator.data.available_tracks:
            raise HomeAssistantError(
                f"Track {option!r} is not available on this device. "
                f"Available tracks: {', '.join(self.coordinator.data.available_tracks)}"
            )
        try:
            await self.coordinator.sound_light.async_set_track(option)
        except NanitTransportError as err:
            _LOGGER.warning("Failed to set track on %s: %s", self.entity_id, err)
            raise
