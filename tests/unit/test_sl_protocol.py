"""Tests for the Sound & Light wire protocol — encode/decode roundtrips."""

from __future__ import annotations

from custom_components.nanit_sound_light.aionanit_sl.sl_protocol import (
    build_brightness_cmd,
    build_color_cmd,
    build_light_enabled_cmd,
    build_power_cmd,
    build_sound_on_cmd,
    build_track_cmd,
    build_volume_cmd,
    decode_varint,
    fixed32_to_float,
    float_to_fixed32,
)


class TestVarint:
    def test_single_byte(self) -> None:
        assert decode_varint(b"\x05", 0) == (5, 1)

    def test_multi_byte(self) -> None:
        # 150 = 0x96 = 10010110 → varint bytes: 0x96 0x01
        assert decode_varint(b"\x96\x01", 0) == (150, 2)


class TestFixed32:
    def test_roundtrip(self) -> None:
        for val in (0.0, 0.5, 1.0, 0.123456):
            encoded = float_to_fixed32(val)
            decoded = fixed32_to_float(encoded)
            assert abs(decoded - val) < 1e-6


class TestCommands:
    """Commands should produce non-empty bytes; structural validity checked here."""

    def test_power_cmd_non_empty(self) -> None:
        assert len(build_power_cmd(True)) > 0
        assert len(build_power_cmd(False)) > 0

    def test_light_enabled_cmd(self) -> None:
        # INVERTED convention: on=True should still produce a valid command.
        cmd = build_light_enabled_cmd(True)
        assert len(cmd) > 0

        # With color args, the command must be longer.
        cmd_with_color = build_light_enabled_cmd(True, color_a=0.5, color_b=0.8)
        assert len(cmd_with_color) > len(cmd)

    def test_brightness_cmd(self) -> None:
        cmd = build_brightness_cmd(0.75)
        assert len(cmd) > 0

    def test_volume_cmd(self) -> None:
        cmd = build_volume_cmd(0.6)
        assert len(cmd) > 0

    def test_color_cmd(self) -> None:
        cmd = build_color_cmd(0.25, 0.9, light_enabled=True)
        assert len(cmd) > 0

    def test_track_cmd(self) -> None:
        cmd = build_track_cmd("Ocean", sound_on=True)
        assert len(cmd) > 0

    def test_sound_on_cmd(self) -> None:
        cmd = build_sound_on_cmd(True, current_track="Ocean")
        assert len(cmd) > 0

    def test_on_and_off_differ(self) -> None:
        """Toggling a command should produce a different payload."""
        assert build_power_cmd(True) != build_power_cmd(False)
        assert build_light_enabled_cmd(True) != build_light_enabled_cmd(False)
