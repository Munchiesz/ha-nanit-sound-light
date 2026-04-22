"""Coordinator for the Nanit Sound & Light Machine.

Push-based — wraps NanitSoundLight.subscribe() and forwards state updates
to HA entities. Uses a disconnect grace period so brief reconnects do not
surface as "Unavailable", and a longer "extended disconnect" window that
surfaces a repair issue when the speaker has been unreachable for several
minutes (so users see something actionable in the UI instead of just a
silent "Unavailable" entity).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
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

# How long to wait, from disconnect, before surfacing a persistent repair
# issue telling the user something is wrong. The reconnect loop keeps
# trying in the background; this timer only controls when we make noise
# about it in the UI.
_EXTENDED_DISCONNECT_SECONDS: float = 300.0  # 5 minutes


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
        self._extended_disconnect_timer: CALLBACK_TYPE | None = None
        self._extended_disconnect_issue: str = f"extended_disconnect_{entry.entry_id}"
        self._extended_disconnect_issue_active: bool = False

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
                self._cancel_extended_disconnect_timer()
                self._clear_extended_disconnect_issue()
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
                self._start_extended_disconnect_timer()

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

    @callback
    def _on_extended_disconnect(self, _now: object) -> None:
        """Longer grace expired — surface a repair issue."""
        self._extended_disconnect_timer = None
        if not self.sound_light.connected and not self._extended_disconnect_issue_active:
            _LOGGER.warning(
                "Sound & Light %s disconnected for >%.0fs — surfacing issue",
                self.sound_light.speaker_uid,
                _EXTENDED_DISCONNECT_SECONDS,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._extended_disconnect_issue,
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="extended_disconnect",
                translation_placeholders={
                    "minutes": str(int(_EXTENDED_DISCONNECT_SECONDS // 60)),
                },
            )
            self._extended_disconnect_issue_active = True

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

    def _start_extended_disconnect_timer(self) -> None:
        """Start (or restart) the longer timer that surfaces a repair issue."""
        self._cancel_extended_disconnect_timer()
        self._extended_disconnect_timer = async_call_later(
            self.hass, _EXTENDED_DISCONNECT_SECONDS, self._on_extended_disconnect
        )

    def _cancel_extended_disconnect_timer(self) -> None:
        """Cancel the extended-disconnect timer if running."""
        if self._extended_disconnect_timer is not None:
            self._extended_disconnect_timer()
            self._extended_disconnect_timer = None

    def _clear_extended_disconnect_issue(self) -> None:
        """Clear the extended-disconnect repair issue if we previously raised it."""
        if self._extended_disconnect_issue_active:
            ir.async_delete_issue(self.hass, DOMAIN, self._extended_disconnect_issue)
            self._extended_disconnect_issue_active = False

    async def async_shutdown(self) -> None:
        """Stop the Sound & Light device and unsubscribe."""
        self._cancel_availability_timer()
        self._cancel_extended_disconnect_timer()
        self._clear_extended_disconnect_issue()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self.sound_light.async_stop()
        await super().async_shutdown()
