"""Read-only token provider that piggybacks on the main Nanit integration.

This addon never refreshes tokens itself — it delegates all auth refresh
logic to the main Nanit integration and reads the current access token
from that integration's config entry on each call. When the main
integration refreshes, this provider picks up the new token automatically.

If the piggybacked entry goes missing or its token is cleared *after*
setup (e.g. the user removes the main Nanit integration while Sound &
Light is running), the provider surfaces a repair issue on the first
failed call so the user sees a fixable UI hint instead of silent
warnings in the log.
"""

from __future__ import annotations

import logging

from aionanit import NanitAuthError
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NanitPiggybackTokenProvider:
    """Duck-typed TokenManager that reads tokens from a sibling config entry.

    ``NanitSoundLight`` only calls ``async_get_access_token()`` on its
    token_manager; implementing just that method is sufficient.

    Keeps an internal flag so the repair issue is created once on the
    first failure (not on every hot-path call) and cleared once on
    recovery (not on every successful call).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        nanit_entry_id: str,
        *,
        issue_id: str,
    ) -> None:
        """Initialize the provider.

        Args:
            hass: Home Assistant instance.
            nanit_entry_id: Config entry ID of the main Nanit integration
                to read tokens from.
            issue_id: Key used when creating/clearing the repair issue.
                Usually derived from the Sound & Light config entry ID
                so each entry has its own issue.
        """
        self._hass = hass
        self._nanit_entry_id = nanit_entry_id
        self._issue_id = issue_id
        self._issue_active: bool = False

    async def async_get_access_token(self) -> str:
        """Return the current access token from the main Nanit integration.

        Raises:
            NanitAuthError: If the main Nanit entry is missing or has no
                stored access token. A repair issue is also surfaced so
                the user has a clickable hint in the UI.
        """
        entry = self._hass.config_entries.async_get_entry(self._nanit_entry_id)
        if entry is None:
            self._surface_issue()
            raise NanitAuthError(
                f"Main Nanit integration entry {self._nanit_entry_id} is gone. "
                "Re-install or reconfigure the Nanit integration."
            )
        token = entry.data.get(CONF_ACCESS_TOKEN)
        if not token:
            self._surface_issue()
            raise NanitAuthError(
                "Main Nanit integration has no access token. Re-authenticate the Nanit integration."
            )

        self._clear_issue()
        return str(token)

    def _surface_issue(self) -> None:
        """Create the repair issue if not already active."""
        if self._issue_active:
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            self._issue_id,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="nanit_entry_missing",
        )
        self._issue_active = True

    def _clear_issue(self) -> None:
        """Delete the repair issue if we previously created it."""
        if not self._issue_active:
            return
        ir.async_delete_issue(self._hass, DOMAIN, self._issue_id)
        self._issue_active = False
