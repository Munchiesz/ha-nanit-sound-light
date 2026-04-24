"""Tests for ``_resolve_speaker_ip`` — the data-vs-options precedence helper.

The audit found that blanking the IP via the options flow silently did
nothing: the old ``or``-chained fallback treated ``""`` as falsy and
resurrected the stale ``entry.data`` value instead of switching the
integration to cloud-relay mode. These tests pin the corrected semantics.
"""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.nanit_sound_light import _resolve_speaker_ip
from custom_components.nanit_sound_light.const import CONF_SPEAKER_IP


def _entry(data_ip: str | None, options: dict | None) -> SimpleNamespace:
    return SimpleNamespace(
        data={CONF_SPEAKER_IP: data_ip} if data_ip is not None else {},
        options=options if options is not None else {},
    )


def test_returns_options_ip_when_set() -> None:
    assert _resolve_speaker_ip(_entry("10.0.0.1", {CONF_SPEAKER_IP: "192.168.1.50"})) == (
        "192.168.1.50"
    )


def test_falls_back_to_data_when_options_untouched() -> None:
    assert _resolve_speaker_ip(_entry("10.0.0.1", {})) == "10.0.0.1"


def test_returns_none_when_nothing_configured() -> None:
    assert _resolve_speaker_ip(_entry(None, {})) is None


def test_blank_options_ip_switches_to_cloud_even_if_data_has_ip() -> None:
    """The audit-fixed case: user had set an IP at setup, then blanked it
    in the options flow. The effective IP must be ``None`` so the
    integration falls back to cloud relay — previously it silently
    reverted to the stale data-only value."""
    assert _resolve_speaker_ip(_entry("10.0.0.1", {CONF_SPEAKER_IP: ""})) is None


def test_blank_options_ip_with_no_data_is_also_none() -> None:
    assert _resolve_speaker_ip(_entry(None, {CONF_SPEAKER_IP: ""})) is None
