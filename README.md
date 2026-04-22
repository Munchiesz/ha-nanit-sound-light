# Nanit Sound & Light

A Home Assistant integration for the **Nanit Sound & Light Machine lamp** — a companion to the main [Nanit integration](https://github.com/wealthystudent/ha-nanit).

This integration exposes the Sound & Light Machine as a separate HA light entity. It is deliberately narrow: it does one thing (lamp control) and depends on the main Nanit integration for authentication.

## Requirements

- Home Assistant **2025.12** or newer
- The [Nanit integration](https://github.com/wealthystudent/ha-nanit) installed and configured first — this addon reads auth tokens from its config entry.
- A Nanit account with a paired Sound & Light Machine (Nanit Lite).
- The speaker's local IP (set a DHCP reservation on your router).

## Installation (HACS)

1. HACS → ⋮ (top right) → **Custom repositories** → add `https://github.com/Munchiesz/ha-nanit-sound-light` with category **Integration**.
2. Find **Nanit Sound & Light** in HACS → **Download** → restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Nanit Sound & Light.**
4. Pick your speaker from the discovered list, enter its local IP, submit.
5. A `light.<name>_sound_light_lamp` entity appears with on/off control.

## Scope (v0.1.0)

This release ships **lamp on/off only**. Planned for later releases:

- Brightness
- HS color
- Sound track selection
- Volume
- Routines
- Power and timer controls

Open an [issue](https://github.com/Munchiesz/ha-nanit-sound-light/issues) if you need a specific feature prioritized.

## How authentication works

This integration does not hold your Nanit credentials directly. On each API call it reads the current access/refresh tokens from the **main Nanit integration's config entry** and uses them to talk to the Nanit cloud. When the main integration refreshes its tokens, this one picks up the new values automatically.

If the main Nanit integration is removed or broken, this one will fail with a repair issue. Re-authenticate the main Nanit integration and this one will recover on next reload.

## License

[MIT](LICENSE)
