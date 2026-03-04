#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Error: scripts/build_mac.sh is for macOS only."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Error: .venv not found. Run scripts/install_mac.sh first."
  exit 1
fi

source .venv/bin/activate
export COPYFILE_DISABLE=1

if ! python -m PyInstaller --version >/dev/null 2>&1; then
  python -m pip install pyinstaller
fi

mkdir -p app/build app/dist
find app/build -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
find app/dist -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true

# Remove mac metadata artifacts that can break bundle signing/validation.
find . -name '.DS_Store' -delete || true
if command -v xattr >/dev/null 2>&1; then
  xattr -cr LyPy app 2>/dev/null || true
fi

pyinstaller --noconfirm --distpath app/dist --workpath app/build app/LyPy.spec

APP_PATH="app/dist/LyPy.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Error: Build completed but $APP_PATH was not created."
  exit 1
fi

if command -v xattr >/dev/null 2>&1; then
  xattr -cr "$APP_PATH" 2>/dev/null || true
fi

echo "Build complete: $APP_PATH"
