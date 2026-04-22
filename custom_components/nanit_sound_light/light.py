"""Light platform for the Nanit Sound & Light Machine.

v0.2.0: on/off + brightness + HS color. The lamp's color model is the
device's native 2-parameter (hue + saturation-ish) representation;
``color_r``/``color_g`` in the protocol are surfaced to HA as
``hs_color[0]``/``hs_color[1]``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, ClassVar

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_HS_COLOR, LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

# Ignore contradicting push echoes for this many seconds after a command —
# the device may briefly echo the old state before confirming the new one.
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
    """Nanit Sound & Light Machine lamp — on/off, brightness, HS color."""

    _attr_supported_color_modes: ClassVar[set[ColorMode]] = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS
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

    @property
    def brightness(self) -> int | None:
        """Return brightness in HA's 0-255 scale."""
        if self.coordinator.data is None:
            return None
        dev_brightness = self.coordinator.data.brightness
        if dev_brightness is None:
            return None
        state = self.coordinator.data
        # Surface brightness=1 when the light is conceptually "on" but the
        # device reports 0.0 — avoids HA interpreting it as off.
        if state.power_on and state.light_enabled and dev_brightness < 0.004:
            return 1
        return min(255, max(0, int(dev_brightness * 255)))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return (hue, saturation) if known."""
        if self.coordinator.data is None:
            return None
        state = self.coordinator.data
        color_a = state.color_r
        color_b = state.color_g
        if color_a is None and color_b is None:
            return None
        return ((color_a or 0.0) * 360.0, (color_b or 0.0) * 100.0)

    def _clear_grace(self) -> None:
        self._command_is_on = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the lamp, optionally setting brightness and/or color."""
        self._command_is_on = True
        self._command_ts = time.monotonic()
        self.async_write_ha_state()

        try:
            await self.coordinator.sound_light.async_set_light_enabled(True)

            if ATTR_HS_COLOR in kwargs:
                hs = kwargs[ATTR_HS_COLOR]
                color_a = hs[0] / 360.0
                color_b = hs[1] / 100.0
                await self.coordinator.sound_light.async_set_color(color_a, color_b)

            if ATTR_BRIGHTNESS in kwargs:
                # Clamp to >= 0.01 so the device doesn't fully kill the light
                # when HA sends brightness=0 on turn_on (which it shouldn't,
                # but defensive).
                dev_brightness = max(0.01, kwargs[ATTR_BRIGHTNESS] / 255.0)
                await self.coordinator.sound_light.async_set_brightness(dev_brightness)
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
