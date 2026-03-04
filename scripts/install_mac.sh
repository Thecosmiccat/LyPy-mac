#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Error: scripts/install_mac.sh is for macOS only."
  exit 1
fi

pick_python() {
  local candidates=(python3.12 python3.11 python3.10)
  local cmd
  for cmd in "${candidates[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  return 1
}

PYTHON_CMD="$(pick_python || true)"
if [[ -z "$PYTHON_CMD" ]]; then
  cat <<'EOF'
Error: Python 3.12, 3.11, or 3.10 was not found.
Install Python first: https://www.python.org/downloads/macos/
EOF
  exit 1
fi

echo "Using $PYTHON_CMD"
"$PYTHON_CMD" -m venv .venv

source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r LyPy/requirements.txt

# Remove macOS metadata attributes that can break Qt/plugin loading/signing.
if command -v xattr >/dev/null 2>&1; then
  xattr -cr .venv LyPy app 2>/dev/null || true
fi

# Quick Qt bootstrap sanity check.
python - <<'PY'
import os
from PyQt5.QtCore import QLibraryInfo

plugins = QLibraryInfo.location(QLibraryInfo.PluginsPath)
platforms = os.path.join(plugins, "platforms")
cocoa = os.path.join(platforms, "libqcocoa.dylib")

if not plugins or not os.path.isdir(platforms) or not os.path.isfile(cocoa):
    raise SystemExit(
        "Qt sanity check failed: Cocoa platform plugin not found at expected path."
    )

print(f"Qt sanity check OK: {cocoa}")
PY

echo "Install complete. Activate with: source .venv/bin/activate"
