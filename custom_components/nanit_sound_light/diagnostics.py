"""Diagnostics support for the Nanit Sound & Light integration.

When a user clicks **Settings → Devices & Services → Nanit Sound & Light
→ ⋮ → Download diagnostics**, Home Assistant calls
``async_get_config_entry_diagnostics`` and serializes the returned dict
to a JSON file the user can attach to bug reports.

This implementation dumps:
- The integration's config-entry metadata
- The entry's ``data`` dict (with device UIDs and IPs redacted)
- The current speaker state (brightness, color, sound, volume, etc.)
- Discovered tracks and routines
- Connection mode and recent error (if any)

Identifiers that could be used to correlate or fingerprint the user's
Nanit account (camera UID, speaker UID, LAN IPs, the main-integration
entry ID) are redacted to ``**REDACTED**`` before export.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NanitSoundLightConfigEntry
from .const import (
    CONF_CAMERA_UID,
    CONF_NANIT_ENTRY_ID,
    CONF_SPEAKER_IP,
    CONF_SPEAKER_UID,
)

_REDACT_ENTRY_KEYS: set[str] = {
    CONF_CAMERA_UID,
    CONF_NANIT_ENTRY_ID,
    CONF_SPEAKER_IP,
    CONF_SPEAKER_UID,
}

# State field names that include the camera UID — not currently in state
# but future-proofing in case we start persisting them.
_REDACT_STATE_KEYS: set[str] = {"camera_uid", "speaker_uid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: NanitSoundLightConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a Sound & Light config entry."""
    runtime = getattr(entry, "runtime_data", None)

    state_snapshot: dict[str, Any] | None = None
    connection_mode: str | None = None
    coordinator_connected: bool | None = None
    last_update_success: bool | None = None

    if runtime is not None:
        coordinator = runtime.coordinator
        if coordinator.data is not None:
            # SoundLightFullState is a frozen dataclass → use asdict for a
            # plain-JSON-able snapshot. ``tuple`` becomes list, routines'
            # nested dataclass is recursed automatically.
            state_snapshot = dataclasses.asdict(coordinator.data)
        connection_mode = runtime.sound_light.connection_mode
        coordinator_connected = coordinator.connected
        last_update_success = coordinator.last_update_success

    diagnostics: dict[str, Any] = {
        "integration_version": "0.3.0",
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": entry.state.value if hasattr(entry.state, "value") else str(entry.state),
            "disabled_by": str(entry.disabled_by) if entry.disabled_by else None,
            "source": entry.source,
            "unique_id": entry.unique_id,
            "data": async_redact_data(dict(entry.data), _REDACT_ENTRY_KEYS),
            "options": dict(entry.options) if entry.options else {},
        },
        "runtime": {
            "loaded": runtime is not None,
            "coordinator_connected": coordinator_connected,
            "last_update_success": last_update_success,
            "connection_mode": connection_mode,
            "state": (
                async_redact_data(state_snapshot, _REDACT_STATE_KEYS)
                if state_snapshot is not None
                else None
            ),
        },
    }
    return diagnostics
