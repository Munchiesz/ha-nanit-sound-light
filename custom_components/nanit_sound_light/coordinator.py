"""Coordinator for the Nanit Sound & Light Machine.

Push-based — wraps NanitSoundLight.subscribe() and forwards state updates
to HA entities. Uses a disconnect grace period so brief reconnects do not
surface as "Unavailable".
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aionanit_sl import (
    NanitSoundLight,
    SoundLightEvent,
    SoundLightEventKind,
    SoundLightFullState,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from . import NanitSoundLightConfigEntry
    from .models import Baby

_LOGGER = logging.getLogger(__name__)

# How long to wait before marking entities unavailable after a disconnect.
# If the WebSocket reconnects within this window, entities never go unavailable.
_AVAILABILITY_GRACE_SECONDS: float = 30.0


class NanitSoundLightCoordinator(DataUpdateCoordinator[SoundLightFullState]):
    """Push-based coordinator for the Nanit Sound & Light Machine.

    Wraps NanitSoundLight.subscribe() — receives state updates from the
    speaker via WebSocket (local if IP is set, cloud relay as fallback).
    """

    config_entry: NanitSoundLightConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NanitSoundLightConfigEntry,
        sound_light: NanitSoundLight,
        baby: Baby,
    ) -> None:
        """Initialize the Sound & Light coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{sound_light.speaker_uid}",
        )
        self.sound_light = sound_light
        self.baby = baby
        self.connected: bool = False
        self._unsubscribe: Callable[[], None] | None = None
        self._availability_timer: CALLBACK_TYPE | None = None

    async def async_setup(self) -> None:
        """Start the Sound & Light device and subscribe to push events."""
        self._unsubscribe = self.sound_light.subscribe(self._on_sl_event)
        await self.sound_light.async_start()
        self.connected = self.sound_light.connected
        self.async_set_updated_data(self.sound_light.state)

    @callback
    def _on_sl_event(self, event: SoundLightEvent) -> None:
        """Handle a push event from NanitSoundLight.subscribe()."""
        if event.kind == SoundLightEventKind.CONNECTION_CHANGE:
            transport_connected = self.sound_light.connected
            if transport_connected:
                self._cancel_availability_timer()
                if not self.connected:
                    _LOGGER.info(
                        "Sound & Light %s reconnected",
                        self.sound_light.speaker_uid,
                    )
                self.connected = True
            elif self.connected:
                _LOGGER.debug(
                    "Sound & Light %s disconnected (grace period %.0fs)",
                    self.sound_light.speaker_uid,
                    _AVAILABILITY_GRACE_SECONDS,
                )
                self._start_availability_timer()

        self.async_set_updated_data(event.state)

    @callback
    def _on_availability_timeout(self, _now: object) -> None:
        """Grace period expired — mark entities unavailable."""
        self._availability_timer = None
        if not self.sound_light.connected:
            _LOGGER.warning(
                "Sound & Light %s still disconnected after %.0fs grace period",
                self.sound_light.speaker_uid,
                _AVAILABILITY_GRACE_SECONDS,
            )
            self.connected = False
            self.async_update_listeners()

    def _start_availability_timer(self) -> None:
        """Start (or restart) the grace period timer."""
        self._cancel_availability_timer()
        self._availability_timer = async_call_later(
            self.hass, _AVAILABILITY_GRACE_SECONDS, self._on_availability_timeout
        )

    def _cancel_availability_timer(self) -> None:
        """Cancel the grace period timer if running."""
        if self._availability_timer is not None:
            self._availability_timer()
            self._availability_timer = None

    async def async_shutdown(self) -> None:
        """Stop the Sound & Light device and unsubscribe."""
        self._cancel_availability_timer()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self.sound_light.async_stop()
        await super().async_shutdown()
