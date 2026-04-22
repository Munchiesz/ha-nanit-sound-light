"""Local data models for the Nanit Sound & Light integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Baby:
    """Minimal camera info needed by the Sound & Light addon.

    Replaces a dependency on ``aionanit.models.Baby`` so the coordinator
    and entity code aren't coupled to aionanit's full API surface.
    """

    name: str
    camera_uid: str
