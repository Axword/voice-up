"""Icons of the programs behind profiles, extracted once from the installed .exe and cached as PNG.

Windows only. The program is found through its registered "App Paths" entry or, failing that,
a running process of the same name. Nothing is read or sent anywhere else.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from app import paths
from app.logging_setup import get_logger

log = get_logger("icons")

_EXE = re.compile(r"[\w .\-]{1,100}\.exe", re.IGNORECASE)
_MISS_TTL = 300.0
_misses: dict[str, float] = {}
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_script_lock = threading.Lock()

_SCRIPT = r"""
param([string]$exe, [string]$out)
$path = $null
foreach ($root in 'HKLM:', 'HKCU:') {
  $key = "$root\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$exe"
  if (Test-Path -LiteralPath $key) { $path = (Get-ItemProperty -LiteralPath $key).'(default)'; if ($path) { break } }
}
if (-not $path) {
  $proc = Get-Process -Name ($exe -replace '\.exe$', '') -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($proc) { $path = $proc.Path }
}
if ($path) { $path = $path.Trim('"') }
if (-not $path -or -not (Test-Path -LiteralPath $path)) { exit 3 }
Add-Type -AssemblyName System.Drawing
$icon = [System.Drawing.Icon]::ExtractAssociatedIcon($path)
$icon.ToBitmap().Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
"""


def valid_exe(name: str) -> bool:
    return bool(_EXE.fullmatch(name))


def _cache_file(exe: str) -> Path:
    return paths.CACHE_DIR / "icons" / (re.sub(r"[^\w.\-]", "_", exe.lower()) + ".png")


def icon_for(exes: tuple[str, ...]) -> Path | None:
    """PNG of the first program that can be found, or None."""
    if sys.platform != "win32":
        return None
    for exe in exes:
        if not valid_exe(exe):
            continue
        target = _cache_file(exe.lower())
        if target.is_file():
            return target
        with _exe_lock(exe.lower()):
            # Another thread may have finished the same extraction while this one waited.
            if target.is_file():
                return target
            if time.monotonic() - _misses.get(exe.lower(), -_MISS_TTL) < _MISS_TTL:
                continue
            if _extract(exe, target):
                return target
            _misses[exe.lower()] = time.monotonic()
    return None


def _exe_lock(exe: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(exe, threading.Lock())


def _script_path() -> Path:
    """The PowerShell script, written once per process (concurrent writers raced on it before)."""
    target = paths.CACHE_DIR / "icons" / "extract.ps1"
    with _script_lock:
        if not target.is_file() or target.read_text(encoding="utf-8") != _SCRIPT:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(_SCRIPT)
            Path(name).replace(target)
    return target


def _extract(exe: str, target: Path) -> bool:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        script = _script_path()
        handle, name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        os.close(handle)
        partial = Path(name)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(script), exe, str(partial)],
            capture_output=True, timeout=20, creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        if result.returncode == 0 and partial.is_file():
            partial.replace(target)
            return True
        partial.unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Icon extraction for %s failed: %s", exe, exc)
    return False
