"""Update compatibility endpoint for the profile-based application.

The former League of Legends release channel is intentionally disconnected:
those installers do not contain the profile engine and must never replace it.
"""

from __future__ import annotations

from typing import Any

from app import version


def cached_result() -> dict:
    return check()


def check(force: bool = False) -> dict:
    return {
        "current": version.get_version(),
        "latest": None,
        "available": False,
        "url": None,
        "notes": None,
        "reason": "release_channel_not_configured",
    }


def install(on_exit: Any | None = None) -> dict:
    return {"started": False, "reason": "release_channel_not_configured"}
