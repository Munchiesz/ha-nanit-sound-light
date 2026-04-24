"""Config flow + options flow + reauth flow for Nanit Sound & Light.

Initial setup (``async_step_user``):
  1. pick which main Nanit integration entry to piggyback on
  2. pick which Sound & Light Machine to control
  3. enter the speaker's LAN IP (optional)

Options flow:
  Edit the speaker IP at any time. Updates trigger a full integration
  reload via the update-listener registered in ``__init__.py``.

Reauth flow:
  Fired when our piggybacked token reads fail. Since we don't own the
  credentials, reauth is simply a prompt pointing the user to the main
  Nanit integration's own reauth flow; once they've done that, we
  confirm by re-reading the token here and reload the entry.
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from aionanit import NanitAuthError
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CAMERA_NAME,
    CONF_CAMERA_UID,
    CONF_NANIT_ENTRY_ID,
    CONF_SPEAKER_IP,
    CONF_SPEAKER_UID,
    DOMAIN,
    NANIT_DOMAIN,
)
from .sanitize import sanitize_name
from .token_provider import NanitPiggybackTokenProvider

_LOGGER = logging.getLogger(__name__)

_NANIT_API_BASE_URL = "https://api.nanit.com"


def _extract_speaker_uid(baby: dict[str, Any]) -> str | None:
    """Pull a speaker UID out of a /babies entry.

    Nanit has used at least four shapes for the linked speaker; this walks
    them in order of likelihood. Matches the helper in the main Nanit
    integration's ``hub.py``.
    """
    speaker_wrap = baby.get("speaker")
    if isinstance(speaker_wrap, dict):
        inner = speaker_wrap.get("speaker")
        if isinstance(inner, dict):
            uid = inner.get("uid")
            if isinstance(uid, str) and uid:
                return uid
        uid = speaker_wrap.get("uid")
        if isinstance(uid, str) and uid:
            return uid

    speakers_list = baby.get("speakers")
    if isinstance(speakers_list, list) and speakers_list:
        first = speakers_list[0]
        if isinstance(first, dict):
            uid = first.get("uid")
            if isinstance(uid, str) and uid:
                return uid

    flat = baby.get("speaker_uid")
    if isinstance(flat, str) and flat:
        return flat

    return None


class NanitSoundLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nanit Sound & Light."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._nanit_entry_id: str = ""
        self._speakers: list[dict[str, str]] = []  # [{speaker_uid, camera_uid, camera_name}]
        self._selected: dict[str, str] = {}
        self._reauth_entry: ConfigEntry | None = None

    # ------------------------------------------------------------------
    # Initial user flow
    # ------------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick which main Nanit integration entry to piggyback on."""
        nanit_entries = [
            e for e in self.hass.config_entries.async_entries(NANIT_DOMAIN) if e.disabled_by is None
        ]

        if not nanit_entries:
            return self.async_abort(reason="nanit_not_installed")

        if len(nanit_entries) == 1:
            self._nanit_entry_id = nanit_entries[0].entry_id
            return await self.async_step_speaker()

        if user_input is not None:
            self._nanit_entry_id = user_input[CONF_NANIT_ENTRY_ID]
            return await self.async_step_speaker()

        options = {e.entry_id: (e.title or e.entry_id) for e in nanit_entries}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NANIT_ENTRY_ID): vol.In(options),
                }
            ),
        )

    async def async_step_speaker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which Sound & Light Machine to control."""
        if not self._speakers:
            try:
                self._speakers = await self._async_discover_speakers()
            except NanitAuthError as err:
                _LOGGER.warning("Speaker discovery auth failure: %s", err)
                return self.async_abort(reason="nanit_needs_reauth")
            except aiohttp.ClientError as err:
                _LOGGER.warning("Speaker discovery network failure: %s", err)
                return self.async_show_form(
                    step_id="speaker",
                    data_schema=vol.Schema({}),
                    errors={"base": "discovery_failed"},
                )

        if not self._speakers:
            return self.async_abort(reason="no_speakers_on_account")

        if len(self._speakers) == 1:
            self._selected = self._speakers[0]
            await self.async_set_unique_id(self._selected["speaker_uid"])
            self._abort_if_unique_id_configured()
            return await self.async_step_speaker_ip()

        if user_input is not None:
            speaker_uid = user_input[CONF_SPEAKER_UID]
            self._selected = next(
                (s for s in self._speakers if s["speaker_uid"] == speaker_uid),
                {},
            )
            if not self._selected:
                # The user picked an entry that vanished between the
                # dropdown render and submit — surface a distinct reason
                # from the "Nanit account has no speakers" abort so the
                # error message in the UI is actionable.
                return self.async_abort(reason="speaker_selection_failed")
            await self.async_set_unique_id(self._selected["speaker_uid"])
            self._abort_if_unique_id_configured()
            return await self.async_step_speaker_ip()

        options = {
            s["speaker_uid"]: f"{sanitize_name(s['camera_name'])} ({s['speaker_uid'][:8]}…)"
            for s in self._speakers
        }
        return self.async_show_form(
            step_id="speaker",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SPEAKER_UID): vol.In(options),
                }
            ),
        )

    async def async_step_speaker_ip(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the local IP of the Sound & Light Machine."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input.get(CONF_SPEAKER_IP, "").strip()
            if raw:
                try:
                    ipaddress.ip_address(raw)
                except ValueError:
                    errors[CONF_SPEAKER_IP] = "invalid_ip"
            if not errors:
                title = f"{sanitize_name(self._selected['camera_name'])} Sound & Light"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_NANIT_ENTRY_ID: self._nanit_entry_id,
                        CONF_CAMERA_UID: self._selected["camera_uid"],
                        CONF_CAMERA_NAME: self._selected["camera_name"],
                        CONF_SPEAKER_UID: self._selected["speaker_uid"],
                        CONF_SPEAKER_IP: raw,
                    },
                )

        return self.async_show_form(
            step_id="speaker_ip",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SPEAKER_IP, default=""): cv.string,
                }
            ),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Reauth flow
    # ------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauth — triggered when our piggybacked token reads fail."""
        # Defensive: HA normally populates ``context["entry_id"]`` when it
        # initiates a reauth flow, but third-party code paths (discovery,
        # tests) can miss it. Abort cleanly with a dedicated reason instead
        # of raising ``KeyError``.
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="reauth_missing_entry")
        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is None:
            return self.async_abort(reason="reauth_missing_entry")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth by re-reading the token from the main Nanit entry.

        We don't hold credentials ourselves — the user's job is to re-auth
        the main Nanit integration. Once they click Submit here, we verify
        that the main integration now has a valid access_token and reload.
        """
        assert self._reauth_entry is not None

        errors: dict[str, str] = {}

        if user_input is not None:
            nanit_entry_id = self._reauth_entry.data.get(CONF_NANIT_ENTRY_ID)
            if not isinstance(nanit_entry_id, str) or not nanit_entry_id:
                # The config entry is missing the piggyback pointer (e.g.
                # corrupted state) — there's nothing to reauth against.
                return self.async_abort(reason="reauth_missing_entry")
            provider = NanitPiggybackTokenProvider(
                self.hass,
                nanit_entry_id,
                issue_id=f"nanit_entry_missing_{self._reauth_entry.entry_id}",
            )
            try:
                await provider.async_get_access_token()
            except NanitAuthError:
                errors["base"] = "nanit_still_broken"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"main_integration_name": "Nanit"},
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> NanitSoundLightOptionsFlow:
        """Get the options flow for this handler."""
        return NanitSoundLightOptionsFlow()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _async_discover_speakers(self) -> list[dict[str, str]]:
        """Fetch /babies and extract paired speakers.

        Returns a list of ``{speaker_uid, camera_uid, camera_name}`` dicts.
        Raises NanitAuthError if the piggybacked tokens are invalid,
        aiohttp.ClientError on network failure.
        """
        provider = NanitPiggybackTokenProvider(
            self.hass,
            self._nanit_entry_id,
            # The config flow is transient — no config entry exists yet for
            # this speaker. Skip the repair-issue path so we don't leave
            # stray issues in the registry if the user cancels setup.
            issue_id=None,
        )
        access_token = await provider.async_get_access_token()

        session = async_get_clientsession(self.hass)
        headers = {"Authorization": access_token, "nanit-api-version": "1"}
        async with session.get(
            f"{_NANIT_API_BASE_URL}/babies",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 401:
                raise NanitAuthError(
                    "Access token rejected by /babies. The main Nanit "
                    "integration may need re-authentication."
                )
            resp.raise_for_status()
            body = await resp.json(content_type=None)

        result: list[dict[str, str]] = []
        for baby in body.get("babies") or []:
            camera_uid = baby.get("camera_uid")
            if not isinstance(camera_uid, str) or not camera_uid:
                continue
            speaker_uid = _extract_speaker_uid(baby)
            if not speaker_uid:
                continue
            camera_name = baby.get("name") or camera_uid
            result.append(
                {
                    "speaker_uid": speaker_uid,
                    "camera_uid": camera_uid,
                    "camera_name": str(camera_name),
                }
            )
        return result


class NanitSoundLightOptionsFlow(OptionsFlow):
    """Options flow — edit the speaker IP after initial setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Single-step form to edit the speaker IP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input.get(CONF_SPEAKER_IP, "").strip()
            if raw:
                try:
                    ipaddress.ip_address(raw)
                except ValueError:
                    errors[CONF_SPEAKER_IP] = "invalid_ip"
            if not errors:
                # Save to options — the update listener in __init__.py
                # reloads the entry so NanitSoundLight picks up the new IP.
                return self.async_create_entry(
                    title="",
                    data={CONF_SPEAKER_IP: raw},
                )

        # Prefill with the current effective value: options overrides data.
        current = self.config_entry.options.get(
            CONF_SPEAKER_IP,
            self.config_entry.data.get(CONF_SPEAKER_IP, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SPEAKER_IP, default=current): cv.string,
                }
            ),
            errors=errors,
        )
