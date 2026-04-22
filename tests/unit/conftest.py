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
        "homeassistant.components.light",
        "homeassistant.components.light.const",
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
