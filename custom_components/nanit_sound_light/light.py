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
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import NanitSoundLightConfigEntry
from .aionanit_sl.exceptions import NanitTransportError
from .coordinator import NanitSoundLightCoordinator
from .entity import NanitSoundLightEntity

PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)

# Ignore contradicting push echoes for this many seconds after a command —
# the device may briefly echo the old state before confirming the new one.
_COMMAND_GRACE_PERIOD: float = 15.0

# Device brightness is a 0.0-1.0 float. Values below this threshold are
# treated as "effectively off" when deciding the HA on/off state and when
# deciding whether to surface a minimum brightness of 1 in the 0-255 scale.
# Picked above a single HA brightness step (1/255 ≈ 0.0039) so rounding
# error at the wire-format boundary never flips the on/off decision.
_LIGHT_ON_BRIGHTNESS_EPSILON: float = 0.004


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sound & Light lamp entity."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([NanitSoundLightLamp(coordinator)])


class NanitSoundLightLamp(NanitSoundLightEntity, LightEntity, RestoreEntity):
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
        # Restored values from the last HA shutdown. Used until the
        # coordinator has received its first push state from the device,
        # at which point the push takes over.
        self._restored_is_on: bool | None = None
        self._restored_brightness: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last-known state so the entity doesn't blink to unknown on HA restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            self._restored_is_on = last.state == STATE_ON
            brightness = last.attributes.get(ATTR_BRIGHTNESS)
            if isinstance(brightness, int | float):
                self._restored_brightness = int(brightness)

    @property
    def is_on(self) -> bool | None:
        """Return True if the lamp is on, with command-grace override."""
        if (
            self._command_is_on is not None
            and time.monotonic() - self._command_ts < _COMMAND_GRACE_PERIOD
        ):
            return self._command_is_on

        # Fall back to the restored value whenever we don't yet have a real
        # reading from the device. The coordinator seeds ``data`` with an
        # all-``None`` default snapshot before the first push lands, so the
        # prior ``data is None`` check never fired after startup-while-offline
        # — we'd end up reporting ``None`` (unknown) even when HA had a
        # perfectly good restored value in hand.
        state = self.coordinator.data
        if state is None or state.light_enabled is None:
            if state is not None and state.brightness is not None:
                return state.brightness > _LIGHT_ON_BRIGHTNESS_EPSILON
            return self._restored_is_on
        return state.light_enabled

    def _handle_coordinator_update(self) -> None:
        """Clear grace early when the device push confirms our command.

        Without this, ``is_on`` would echo the optimistic value for the
        full 15 s window even if the device has already authoritatively
        reported a contradicting state. Clearing grace the moment the
        device pushes the commanded value lets a *subsequent*
        contradicting push bubble through instead of being masked.
        """
        if self._command_is_on is not None and self.coordinator.data is not None:
            observed = self.coordinator.data.light_enabled
            if observed is not None and bool(observed) == self._command_is_on:
                self._command_is_on = None
        super()._handle_coordinator_update()

    @property
    def brightness(self) -> int | None:
        """Return brightness in HA's 0-255 scale."""
        # Same rationale as ``is_on``: prefer restored values whenever the
        # coordinator's snapshot doesn't carry a real brightness yet.
        state = self.coordinator.data
        if state is None or state.brightness is None:
            return self._restored_brightness
        dev_brightness = state.brightness
        # Surface brightness=1 when the light is conceptually "on" but the
        # device reports ~0.0 — avoids HA interpreting it as off.
        if state.power_on and state.light_enabled and dev_brightness < _LIGHT_ON_BRIGHTNESS_EPSILON:
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
