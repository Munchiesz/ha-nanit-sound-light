"""The Nanit Sound & Light integration.

This integration piggybacks on the main Nanit integration's config entry
for authentication. On startup it looks up the referenced nanit entry,
builds a read-only token provider over it, opens a WebSocket to the
Sound & Light Machine, and exposes a single ``light`` entity for on/off
control.

If the main Nanit integration is removed, this one raises a repair issue
and goes into setup_retry so it recovers automatically once the user
re-installs and re-authenticates Nanit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

import aiohttp
from aionanit import NanitAuthError, NanitConnectionError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aionanit_sl import NanitSoundLight
from .const import (
    CONF_CAMERA_NAME,
    CONF_CAMERA_UID,
    CONF_NANIT_ENTRY_ID,
    CONF_SPEAKER_IP,
    CONF_SPEAKER_UID,
    DOMAIN,
)
from .coordinator import NanitSoundLightCoordinator
from .models import Baby
from .token_provider import NanitPiggybackTokenProvider

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class NanitSoundLightRuntimeData:
    """Runtime data attached to each config entry."""

    sound_light: NanitSoundLight
    coordinator: NanitSoundLightCoordinator


type NanitSoundLightConfigEntry = ConfigEntry[NanitSoundLightRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
) -> bool:
    """Set up the Sound & Light integration from a config entry."""
    nanit_entry_id = entry.data[CONF_NANIT_ENTRY_ID]
    camera_uid = entry.data[CONF_CAMERA_UID]
    camera_name = entry.data[CONF_CAMERA_NAME]
    speaker_uid = entry.data[CONF_SPEAKER_UID]
    speaker_ip = entry.data.get(CONF_SPEAKER_IP) or None

    # Surface a repair issue + defer setup if the main Nanit integration is gone.
    nanit_entry = hass.config_entries.async_get_entry(nanit_entry_id)
    if nanit_entry is None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"nanit_entry_missing_{entry.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="nanit_entry_missing",
        )
        raise ConfigEntryNotReady(
            f"Main Nanit integration entry {nanit_entry_id} is missing. "
            "Install/configure Nanit, then reload this entry."
        )

    ir.async_delete_issue(hass, DOMAIN, f"nanit_entry_missing_{entry.entry_id}")

    session = async_get_clientsession(hass)
    token_provider = NanitPiggybackTokenProvider(
        hass,
        nanit_entry_id,
        issue_id=f"nanit_entry_missing_{entry.entry_id}",
    )

    sound_light = NanitSoundLight(
        speaker_uid=speaker_uid,
        token_manager=cast(object, token_provider),  # type: ignore[arg-type]
        rest_client=cast(object, None),  # type: ignore[arg-type]  # unused by sound_light.py
        session=session,
        device_ip=speaker_ip,
    )

    baby = Baby(name=camera_name, camera_uid=camera_uid)

    coordinator = NanitSoundLightCoordinator(hass, entry, sound_light, baby)

    try:
        await coordinator.async_setup()
    except NanitAuthError as err:
        # Clean up partially-started tasks/websocket before handing control
        # back to HA — otherwise we leak on every failed auth attempt.
        await sound_light.async_stop()
        raise ConfigEntryAuthFailed(str(err)) from err
    except (NanitConnectionError, aiohttp.ClientError) as err:
        await sound_light.async_stop()
        raise ConfigEntryNotReady(f"Sound & Light setup failed: {err}") from err

    entry.runtime_data = NanitSoundLightRuntimeData(
        sound_light=sound_light,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
) -> bool:
    """Unload a config entry.

    ``runtime_data`` is only populated when setup ran to completion. On
    failed-setup paths (auth failure, missing nanit entry, etc.) HA still
    calls this to tear the entry down — guard the access so we don't
    raise ``AttributeError`` and leave the entry stuck in a bad state.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None:
            await runtime.coordinator.async_shutdown()
    return unload_ok
