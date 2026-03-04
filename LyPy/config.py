"""Configuration management with OS-specific settings storage."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

APP_NAME = "LyPy"

DEFAULT_CONFIG = {
    "window_width": 500,
    "window_height": 700,
    "window_opacity": 1.0,
    "always_on_top": True,
    "frameless": True,
    "font_size": 28,
    "font_family": "SF Pro Text, Helvetica Neue, Helvetica, Arial, sans-serif",
    "bg_saturation": 80,
    "line_spacing": 3,
    "polling_interval_ms": 350,
    "scroll_animation_ms": 400,
}


def _legacy_local_settings_path() -> Path:
    return Path(__file__).resolve().parent / "settings.json"


def _settings_dir() -> Path:
    system = platform.system().lower()
    home = Path.home()

    if system == "darwin":
        return home / "Library" / "Application Support" / APP_NAME

    if system == "windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME

    return home / ".config" / APP_NAME


def settings_path() -> Path:
    return _settings_dir() / "settings.json"


def _migrate_legacy_if_needed(target: Path) -> None:
    legacy = _legacy_local_settings_path()
    if target.exists() or not legacy.exists():
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        return


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    cfg_path = settings_path()

    _migrate_legacy_if_needed(cfg_path)

    if cfg_path.exists():
        try:
            saved = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                config.update(saved)
        except (OSError, json.JSONDecodeError):
            pass

    # Migrate legacy Windows-first font stack to a mac-safe default.
    if "Segoe UI" in str(config.get("font_family", "")):
        config["font_family"] = DEFAULT_CONFIG["font_family"]
    return config


def save_config(config: dict) -> None:
    cfg_path = settings_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
