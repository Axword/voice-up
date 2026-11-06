"""Organization policy (Business): a machine-wide file an administrator controls.

Location: %PROGRAMDATA%/AxwordVoice/policy.json, or the path in VOICE_CONTROL_POLICY.
Keys: `cloud_enabled` (false blocks every module that talks to the internet) and
`disabled_modules` (ids that users cannot enable). A missing or invalid file means no restrictions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.logging_setup import get_logger

log = get_logger("policy")


class Policy(BaseModel):
    cloud_enabled: bool = True
    disabled_modules: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


def policy_file() -> Path:
    override = os.environ.get("VOICE_CONTROL_POLICY")
    if override:
        return Path(override)
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "AxwordVoice" / "policy.json"


def load() -> Policy:
    target = policy_file()
    try:
        if not target.is_file():
            return Policy()
        return Policy.model_validate(json.loads(target.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, ValidationError) as exc:
        # An unreadable policy must not lock users out of the local core.
        log.warning("Ignoring invalid policy file %s: %s", target, exc)
        return Policy()
