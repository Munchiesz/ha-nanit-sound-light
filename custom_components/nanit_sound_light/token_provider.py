"""Read-only token provider that piggybacks on the main Nanit integration.

This addon never refreshes tokens itself — it delegates all auth refresh
logic to the main Nanit integration and reads the current access token
from that integration's config entry on each call. When the main
integration refreshes, this provider picks up the new token automatically.
"""

from __future__ import annotations

import logging

from aionanit import NanitAuthError
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NanitPiggybackTokenProvider:
    """Duck-typed TokenManager that reads tokens from a sibling config entry.

    ``NanitSoundLight`` only calls ``async_get_access_token()`` on its
    token_manager; implementing just that method is sufficient.
    """

    def __init__(self, hass: HomeAssistant, nanit_entry_id: str) -> None:
        """Initialize the provider."""
        self._hass = hass
        self._nanit_entry_id = nanit_entry_id

    async def async_get_access_token(self) -> str:
        """Return the current access token from the main Nanit integration."""
        entry = self._hass.config_entries.async_get_entry(self._nanit_entry_id)
        if entry is None:
            raise NanitAuthError(
                f"Main Nanit integration entry {self._nanit_entry_id} is gone. "
                "Re-install or reconfigure the Nanit integration."
            )
        token = entry.data.get(CONF_ACCESS_TOKEN)
        if not token:
            raise NanitAuthError(
                "Main Nanit integration has no access token. Re-authenticate the Nanit integration."
            )
        return str(token)
