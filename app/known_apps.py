"""Programs behind the shipped profiles, so older profile files without `apps` still switch and show icons."""

from __future__ import annotations

from app.profiles import Profile

KNOWN_APPS: dict[str, tuple[str, ...]] = {
    "league-of-legends": ("league of legends.exe",),
    "league-of-legends-wasd": ("league of legends.exe",),
    "counter-strike-2": ("cs2.exe",),
    "apex-legends": ("r5apex.exe",),
    "helldivers-2": ("helldivers2.exe",),
    "deep-rock-galactic": ("fsd-win64-shipping.exe",),
    "warframe": ("warframe.x64.exe",),
    "stardew-valley": ("stardew valley.exe",),
    "terraria": ("terraria.exe",),
    "factorio": ("factorio.exe",),
    "portal-2": ("portal2.exe",),
    "team-fortress-2": ("tf_win64.exe", "hl2.exe"),
    "skyrim": ("skyrimse.exe", "tesv.exe"),
    "euro-truck-simulator-2": ("eurotrucks2.exe",),
    "american-truck-simulator": ("amtrucks.exe",),
    "google-chrome": ("chrome.exe",),
    "mozilla-firefox": ("firefox.exe",),
    "windows-explorer": ("explorer.exe",),
    "visual-studio-code": ("code.exe",),
    "vlc": ("vlc.exe",),
    "blender": ("blender.exe",),
    "spotify": ("spotify.exe",),
}


def known_apps(profile: Profile) -> tuple[str, ...]:
    base = profile.id.removesuffix("-en")
    return KNOWN_APPS.get(base, ())


def apps_for(profile: Profile) -> tuple[str, ...]:
    """Explicit `apps` of the profile, else the built-in mapping for shipped profiles."""
    return tuple(name.lower() for name in profile.apps) or known_apps(profile)
