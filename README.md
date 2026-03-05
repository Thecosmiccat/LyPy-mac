# LyPy (macOS) by thecosmiccat

![LyPy screenshot](demo.png)

LyPy is a macOS-first desktop lyrics overlay for Spotify and Apple Music desktop apps.

## Works With

- Spotify desktop app (macOS)
- Apple Music app (macOS)

Browser playback is currently disabled.

## Users (No Python Required)

If you downloaded `LyPy-mac.zip` from Releases:

1. Unzip `LyPy-mac.zip`
2. Open `LyPy.app`


```

That is all normal users need.

## macOS Permissions (Required)

LyPy uses AppleScript to read now-playing info.

1. Open LyPy once.
2. Go to `System Settings -> Privacy & Security -> Automation`.
3. Under `LyPy`, enable access to:
   - Spotify
   - Music

If permissions are stuck:

```bash
tccutil reset AppleEvents com.lypy.app
open app/dist/LyPy.app
```

## Troubleshooting

- `No music app playback detected`:
  - Ensure Spotify or Apple Music desktop app is playing.
  - Confirm Automation permissions above are enabled for LyPy.

## Developers (Python Required)

### Prerequisites

- macOS 12+
- Python 3.10, 3.11, or 3.12 ([Download Python](https://www.python.org/downloads/macos/))
- Xcode Command Line Tools (`xcode-select --install`)

### Install Build Environment

```bash
cd /path/to/LyPy-Mac
bash scripts/install_mac.sh
```

### Build App Bundle

```bash
cd /path/to/LyPy-Mac
bash scripts/build_mac.sh
```

Expected output:
- `app/dist/LyPy.app`

### Run From Source

```bash
cd /path/to/LyPy-Mac
source .venv/bin/activate
python LyPy/main.py
```

## Project Layout

- `LyPy/`: application code
- `scripts/install_mac.sh`: mac setup
- `scripts/build_mac.sh`: mac bundle build
- `app/LyPy.spec`: PyInstaller spec
