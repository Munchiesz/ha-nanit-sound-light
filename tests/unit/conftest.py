"""Shared pytest fixtures and module-path setup.

Local test runs don't require a full Home Assistant install. When
``homeassistant`` isn't importable, we stub the submodules our package
touches with ``MagicMock`` so leaf-unit tests (sanitize, sl_protocol,
token_provider, config-flow helpers) can run in isolation.

CI runs with ``pytest-homeassistant-custom-component`` which supplies
real HA modules; this stub path is inactive in that environment.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Make the project root importable so ``custom_components.nanit_sound_light``
# resolves without installing the package.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import homeassistant  # noqa: F401
except ModuleNotFoundError:
    for _name in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.diagnostics",
        "homeassistant.components.light",
        "homeassistant.components.light.const",
        "homeassistant.components.number",
        "homeassistant.components.select",
        "homeassistant.components.sensor",
        "homeassistant.components.switch",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.exceptions",
        "homeassistant.helpers",
        "homeassistant.helpers.aiohttp_client",
        "homeassistant.helpers.config_validation",
        "homeassistant.helpers.device_registry",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.event",
        "homeassistant.helpers.issue_registry",
        "homeassistant.helpers.update_coordinator",
    ):
        sys.modules.setdefault(_name, MagicMock())
    # Concrete values for constants our code actually reads — without these
    # MagicMock returns a mock object, not the real string key HA stores.
    sys.modules["homeassistant.const"].CONF_ACCESS_TOKEN = "access_token"
    sys.modules["homeassistant.const"].CONF_EMAIL = "email"
    sys.modules["homeassistant.const"].CONF_PASSWORD = "password"

    # Replace HA base classes that we subclass with real plain classes so
    # multi-inheritance works at class-creation time — MagicMock as a base
    # produces metaclass conflicts when combined with other MagicMock bases.

    class _SubscriptableBase:
        """Base supporting ``Class[T]`` used in HA's generic entity classes.

        Includes a no-op ``_handle_coordinator_update`` so that subclasses
        which call ``super()._handle_coordinator_update()`` don't raise
        in tests.
        """

        def __class_getitem__(cls, _item: object) -> type:
            return cls

        def _handle_coordinator_update(self) -> None:
            """No-op: real CoordinatorEntity writes HA state; we don't need to."""

    _real_classes = {
        ("homeassistant.helpers.update_coordinator", "CoordinatorEntity"): _SubscriptableBase,
        ("homeassistant.helpers.update_coordinator", "DataUpdateCoordinator"): _SubscriptableBase,
        ("homeassistant.components.switch", "SwitchEntity"): type("SwitchEntity", (), {}),
        ("homeassistant.components.select", "SelectEntity"): type("SelectEntity", (), {}),
        ("homeassistant.components.number", "NumberEntity"): type("NumberEntity", (), {}),
        ("homeassistant.components.sensor", "SensorEntity"): type("SensorEntity", (), {}),
        ("homeassistant.components.light", "LightEntity"): type("LightEntity", (), {}),
    }
    for (module_name, cls_name), cls in _real_classes.items():
        setattr(sys.modules[module_name], cls_name, cls)

    # Real Exception subclass so `pytest.raises(HomeAssistantError)` works.
    class _HomeAssistantError(Exception):
        pass

    sys.modules["homeassistant.exceptions"].HomeAssistantError = _HomeAssistantError

    # Entity category used by diagnostic sensors.
    class _EntityCategory:
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    sys.modules["homeassistant.const"].EntityCategory = _EntityCategory

    # Minimal async_redact_data that walks dicts and replaces matching keys
    # with "**REDACTED**" — mirrors HA's semantics for the subset of shapes
    # our diagnostics emit (nested dicts + lists of primitives).
    _REDACTED_VALUE = "**REDACTED**"

    def _stub_redact_data(data: object, to_redact: object) -> object:
        keys_to_redact = set(to_redact) if to_redact is not None else set()
        if isinstance(data, dict):
            return {
                k: (
                    _REDACTED_VALUE if k in keys_to_redact else _stub_redact_data(v, keys_to_redact)
                )
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [_stub_redact_data(v, keys_to_redact) for v in data]
        return data

    sys.modules["homeassistant.components.diagnostics"].async_redact_data = _stub_redact_data

    # Enum-style attribute containers that our `_attr_*` class vars reference.
    class _NumberMode:
        SLIDER = "slider"

    class _ColorMode:
        ONOFF = "onoff"
        HS = "hs"
        BRIGHTNESS = "brightness"

    class _SensorDeviceClass:
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ENUM = "enum"

    class _SensorStateClass:
        MEASUREMENT = "measurement"

    sys.modules["homeassistant.components.number"].NumberMode = _NumberMode
    sys.modules["homeassistant.components.light.const"].ColorMode = _ColorMode
    sys.modules["homeassistant.components.sensor"].SensorDeviceClass = _SensorDeviceClass
    sys.modules["homeassistant.components.sensor"].SensorStateClass = _SensorStateClass
    sys.modules["homeassistant.components.light"].ATTR_BRIGHTNESS = "brightness"
    sys.modules["homeassistant.components.light"].ATTR_HS_COLOR = "hs_color"
