# LyPy App README (macOS-first)

This directory contains the LyPy app runtime.

## Current Playback Scope (macOS)

- Spotify desktop app
- Apple Music app
- Browser playback is disabled

## Quick Start

From repository root:

```bash
bash scripts/install_mac.sh
bash scripts/build_mac.sh
open app/dist/LyPy.app
```

## Required Permissions

`System Settings -> Privacy & Security -> Automation -> LyPy`

Enable:
- Spotify
- Music

## Developer Run

```bash
source .venv/bin/activate
python LyPy/main.py
```

## Notes

- Playback polling and lyric fetching run off the Qt main thread.
- Settings path uses OS-appropriate writable directories.
