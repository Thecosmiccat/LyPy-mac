"""LyPy main entry point."""

from __future__ import annotations

import os
import platform
import sys


def _harden_qt_startup() -> None:
    """Prepare Qt environment before importing QApplication."""
    from PyQt5 import QtCore

    if platform.system().lower() == "darwin":
        os.environ["QT_QPA_PLATFORM"] = "cocoa"

        # Inherited plugin overrides can break platform plugin resolution.
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            if key in os.environ:
                os.environ.pop(key)

    # Prefer Qt's own plugin path first; fall back to PyQt wheel layout.
    plugins_dir = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)
    if not plugins_dir:
        pyqt_dir = os.path.dirname(QtCore.__file__)
        plugins_dir = os.path.join(pyqt_dir, "Qt5", "plugins")

    if os.path.isdir(plugins_dir):
        platform_dir = os.path.join(plugins_dir, "platforms")
        if os.path.isdir(platform_dir):
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = platform_dir
        os.environ["QT_PLUGIN_PATH"] = plugins_dir

        # Keep any existing defaults while making PyQt plugin path explicit.
        existing = QtCore.QCoreApplication.libraryPaths()
        merged = [plugins_dir] + [p for p in existing if p != plugins_dir]
        QtCore.QCoreApplication.setLibraryPaths(merged)


_harden_qt_startup()

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from config import load_config
from lyrics_fetcher import LyricsFetcher
from lyrics_window import LyricsWindow
from spotify_client import create_media_session


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LyPy Lyrics")

    app.setStyle("Fusion")
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, Qt.black)
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    app.setPalette(dark_palette)

    config = load_config()

    media = create_media_session()
    lyrics = LyricsFetcher()

    window = LyricsWindow(config, media, lyrics)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
