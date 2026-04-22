# Nanit Sound & Light

A Home Assistant integration for the **Nanit Sound & Light Machine** — a companion to the main [Nanit integration](https://github.com/wealthystudent/ha-nanit).

This integration exposes the Sound & Light Machine speaker/lamp device as a set of HA entities (light, switches, volume, track, sensors). It never holds your Nanit credentials directly — authentication is piggybacked off the main Nanit integration's config entry.

## Requirements

- Home Assistant **2025.12** or newer
- The [Nanit integration](https://github.com/wealthystudent/ha-nanit) installed and configured first — this addon reads auth tokens from its config entry.
- A Nanit account with a paired Sound & Light Machine (Nanit Lite).
- The speaker's local IP (set a DHCP reservation on your router) — optional; cloud-relay fallback works without it, but temperature/humidity sensors only populate in LAN mode.

## Installation (HACS)

1. HACS → ⋮ (top right) → **Custom repositories** → add `https://github.com/Munchiesz/ha-nanit-sound-light` with category **Integration**.
2. Find **Nanit Sound & Light** in HACS → **Download** → **restart Home Assistant** (required — HA scans `custom_components/` only at startup).
3. **Settings → Devices & Services → Add Integration → Nanit Sound & Light.**
4. Pick your speaker from the discovered list, enter its local IP (optional), submit.
5. Entities appear under a **"<Baby Name> Sound & Light"** device.

### Updating

After every HACS update, **restart Home Assistant**. The integration's files are reloaded only on startup; without a restart you'll still be running the old code.

## Entities

| Entity | Purpose |
|---|---|
| `light.*_sound_light_lamp` | On/off + brightness + HS color |
| `switch.*_sound_light_sound` | Play / pause the current sound track |
| `switch.*_sound_light_power` | Whole-device standby |
| `number.*_sound_light_volume` | Volume slider (0–100%) |
| `select.*_sound_light_track` | Pick the active sound track (options advertised by the device) |
| `sensor.*_sound_light_temperature` | Ambient temperature (°C) — LAN mode only |
| `sensor.*_sound_light_humidity` | Ambient humidity (%RH) — LAN mode only |
| `sensor.*_sound_light_connection_mode` | Transport currently in use: `local` / `cloud` / `unavailable` (diagnostic) |

## How authentication works

On each API call, this integration reads the current access token from the **main Nanit integration's config entry** via `hass.config_entries.async_get_entry(…)`. It never refreshes tokens itself — when the main integration refreshes, we pick up the new value automatically on the next call.

If the main Nanit integration is removed or its tokens expire:

- The integration surfaces a **Repair** item in HA's UI with a clickable reauth flow.
- The reauth flow tells you to re-authenticate the main Nanit integration; once you do, click Submit and this integration reloads cleanly.

## Configuration

- **Initial speaker IP** — entered during setup. Leave blank to use cloud relay only.
- **Change speaker IP later** — Settings → Devices & Services → Nanit Sound & Light → **Configure**. Edit the IP; the integration reloads automatically.

## Routine-based automation example

The device advertises a small set of built-in routines (Bedtime, Wakeup, Soft Light, etc.) via its state push. The firmware doesn't accept a "run routine" command, but you can replay one from HA by issuing the individual calls the routine represents. Example — a "Bedtime" scene trigger:

```yaml
# In configuration.yaml or a UI automation
automation:
  - alias: "Nursery bedtime"
    trigger:
      - platform: time
        at: "19:30:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.david_sound_light_lamp
        data:
          brightness_pct: 30
          hs_color: [25, 80]          # warm orange
      - service: select.select_option
        target:
          entity_id: select.david_sound_light_track
        data:
          option: "Ocean"
      - service: number.set_value
        target:
          entity_id: number.david_sound_light_volume
        data:
          value: 40
      - service: switch.turn_on
        target:
          entity_id: switch.david_sound_light_sound
```

The list of available track names is shown in the `select.*_sound_light_track` entity — match the spelling exactly.

## Diagnostics

Having trouble? **Settings → Devices & Services → Nanit Sound & Light → ⋮ → Download diagnostics.** The resulting JSON includes the current state snapshot, connection mode, and config-entry data with sensitive fields (camera UID, speaker UID, LAN IPs) redacted. Safe to attach to bug reports.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Entities stuck at `unknown` right after restart | RestoreEntity populates last-known light state on startup; sensor values populate after the first device push. Usually resolves within a few seconds. |
| `sensor.*_connection_mode` shows `unavailable` for more than 5 minutes | A repair issue is surfaced automatically. Check the speaker's power, Wi-Fi, and LAN IP. Edit the IP via **Configure** or clear it to fall back to cloud relay. |
| Temperature / humidity unavailable | Those readings only come in via the local WebSocket. Ensure the speaker IP is set correctly and that HA can reach it on port 442. |
| Track selector only shows "— no tracks reported —" | The device hasn't sent a state push yet. Give it a moment; persists if the speaker is offline or stuck in cloud-relay mode. |
| Integration broke after the main Nanit integration was updated | Re-authenticate the main Nanit integration. This one auto-recovers on the next reload once tokens are valid. |

## Contributing

### Translations policy

`custom_components/nanit_sound_light/strings.json` is the source-of-truth for user-facing strings. `translations/en.json` must be kept **byte-for-byte identical** — Home Assistant uses `translations/en.json` at runtime for English users and only falls back to `strings.json` when a translation is missing. Drift between them means English users silently see stale copy.

When editing strings, update **both** files.

### Testing

The unit test suite uses a lightweight `conftest.py` that stubs the subset of Home Assistant's API surface that the integration subclasses from. This lets tests run in milliseconds without installing the full HA package locally.

Future contributors wanting richer integration tests can add `pytest-homeassistant-custom-component` as a dev dependency. The current stubs and future HA-backed tests can coexist cleanly — the conftest's HA import is a best-effort `try/except` that only applies the stubs when HA isn't installed.

### Intentionally deferred recommendations

The following improvements have been evaluated and consciously not shipped:

- **Move `aionanit_sl/` into its own PyPI package.** Would eliminate duplication between this and the main Nanit fork, but adds a separate release/maintenance surface. The duplication is bounded (the subpackage is stable) and we don't currently have a second consumer that would benefit.
- **Full `pytest-homeassistant-custom-component` test harness.** See Testing section above — the stub approach works for unit-level tests and keeps CI fast. Worth revisiting if/when we add integration tests that exercise the config-entry lifecycle end-to-end.
- **Non-English translations.** Requires community translators for each supported language; not a self-serve change. Happy to accept PRs that add new translation files.

## License

[MIT](LICENSE)
