"""Tests for speaker-UID extraction helper."""

from __future__ import annotations

from custom_components.nanit_sound_light.config_flow import _extract_speaker_uid


def test_shape_1_canonical() -> None:
    baby = {"speaker": {"speaker": {"uid": "sp-123"}}}
    assert _extract_speaker_uid(baby) == "sp-123"


def test_shape_2_flat_speaker_dict() -> None:
    baby = {"speaker": {"uid": "sp-456"}}
    assert _extract_speaker_uid(baby) == "sp-456"


def test_shape_3_speakers_list() -> None:
    baby = {"speakers": [{"uid": "sp-789"}]}
    assert _extract_speaker_uid(baby) == "sp-789"


def test_shape_4_flat_string() -> None:
    baby = {"speaker_uid": "sp-000"}
    assert _extract_speaker_uid(baby) == "sp-000"


def test_no_speaker_returns_none() -> None:
    assert _extract_speaker_uid({"name": "David"}) is None


def test_empty_speakers_list_returns_none() -> None:
    assert _extract_speaker_uid({"speakers": []}) is None


def test_non_string_uid_returns_none() -> None:
    # Guard against the API handing us a numeric UID.
    assert _extract_speaker_uid({"speaker": {"uid": 42}}) is None
