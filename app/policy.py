"""Organization policy (Business): a machine-wide file an administrator controls.

Location: %PROGRAMDATA%/AxwordVoice/policy.json, or the path in VOICE_CONTROL_POLICY.
Keys: `cloud_enabled` (false blocks every module that talks to the internet) and
`disabled_modules` (ids that users cannot enable). A missing file means no restrictions; an unreadable one keeps cloud modules off.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.logging_setup import get_logger

log = get_logger("policy")


class Policy(BaseModel):
    cloud_enabled: bool = True
    disabled_modules: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


def policy_file() -> Path:
    # A user-level environment variable would let any user point the policy elsewhere, so the
    # shipped (frozen) application ignores it.
    override = None if getattr(sys, "frozen", False) else os.environ.get("VOICE_CONTROL_POLICY")
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
        # The local core keeps working, but an administrator's file that cannot be read must not
        # silently re-enable cloud modules.
        log.warning("Invalid policy file %s, cloud modules stay off: %s", target, exc)
        return Policy(cloud_enabled=False)
