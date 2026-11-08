"""Module registry: what exists, which edition includes it, whether it uses the cloud.

A module's id equals the `name` of the pipeline router it provides, so switching a
module off simply excludes that router. `profile` is the core and cannot be disabled.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

from app import paths, policy

Edition = Literal["free", "pro", "business"]
_RANK = {"free": 0, "pro": 1, "business": 2}


@dataclass(frozen=True)
class Manifest:
    id: str
    name: str
    kind: Literal["router", "executor"]
    edition: Edition = "free"
    requires_cloud: bool = False
    core: bool = False


BUILTIN: tuple[Manifest, ...] = (
    Manifest("profile", "Komendy z profili", "router", core=True),
    Manifest("alias", "Zapamiętane poprawki", "router"),
    Manifest("dictation", "Dyktowanie", "router"),
    Manifest("mouse", "Mysz głosem", "router"),
)


def current_edition() -> Edition:
    """Placeholder: reads an UNSIGNED license.json such as {"edition": "pro"}.

    This only selects features; it is not copy protection. Replace it with signed
    verification before selling paid editions.
    """
    try:
        data = json.loads((paths.CONFIG_DIR / "license.json").read_text(encoding="utf-8-sig"))
        edition = data.get("edition")
        return edition if isinstance(edition, str) and edition in _RANK else "free"
    except (OSError, ValueError, AttributeError):
        return "free"


def status(disabled_by_user: list[str], edition: Edition | None = None) -> list[dict]:
    """Every module with `enabled` (will run) and, when it will not, the reason."""
    edition = edition or current_edition()
    rules = policy.load()
    result = []
    for manifest in BUILTIN:
        reason = None
        if not manifest.core:
            if _RANK[edition] < _RANK[manifest.edition]:
                reason = "edition"
            elif manifest.id in rules.disabled_modules:
                reason = "policy"
            elif manifest.requires_cloud and not rules.cloud_enabled:
                reason = "policy-cloud"
            elif manifest.id in disabled_by_user:
                reason = "user"
        result.append({**asdict(manifest), "enabled": reason is None, "reason": reason})
    return result


def inactive_ids(disabled_by_user: list[str]) -> frozenset[str]:
    return frozenset(item["id"] for item in status(disabled_by_user) if not item["enabled"])
