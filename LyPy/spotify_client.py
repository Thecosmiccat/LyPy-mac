"""Cross-platform media session backends with macOS-first behavior."""

from __future__ import annotations

import asyncio
import platform
import subprocess
import threading
from datetime import datetime, timezone


class BaseMediaSession:
    def get_current_playback(self) -> dict | None:
        raise NotImplementedError

    def play_pause(self) -> None:
        return

    def skip_next(self) -> None:
        return

    def skip_previous(self) -> None:
        return

    def fetch_thumbnail(self, track_key: str, callback) -> None:
        callback(track_key, None)

    def diagnostic_message(self) -> str:
        return ""


class MacMediaSession(BaseMediaSession):
    """macOS media provider: desktop music apps only (Spotify + Apple Music)."""

    def __init__(self):
        self._last_error: str = ""

    def _run_osascript(self, script: str) -> str | None:
        try:
            proc = subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2.5,
            )
            if proc.returncode != 0:
                err = (proc.stderr or "").strip()
                if err:
                    print(f"[MediaSession] osascript error: {err}")
                    self._last_error = err
                return None
            self._last_error = ""
            return (proc.stdout or "").strip()
        except Exception:
            return None

    def _read_float(self, script: str) -> float | None:
        out = self._run_osascript(script)
        if not out:
            return None
        try:
            return float(out.strip())
        except (TypeError, ValueError):
            return None

    def _get_spotify(self) -> dict | None:
        script = (
            'tell application "Spotify" to return '
            '(player state as text) & " | " & '
            '(name of current track) & " | " & '
            '(artist of current track)'
        )
        out = self._run_osascript(script)
        if not out:
            return None
        parts = [p.strip() for p in out.split(" | ")]
        if len(parts) < 3:
            return None

        state = parts[0].strip().lower()
        track = parts[1].strip()
        artist = parts[2].strip()
        if not track:
            return None

        pos_s = self._read_float('tell application "Spotify" to return (player position)')
        dur_ms = self._read_float('tell application "Spotify" to return (duration of current track)')
        progress_ms = int((pos_s or 0.0) * 1000)
        duration_ms = int(dur_ms or 0.0)
        if duration_ms > 0:
            progress_ms = max(0, min(progress_ms, duration_ms))

        return {
            "conflict": False,
            "track_key": f"{artist} — {track}".strip(),
            "track_name": track,
            "artist": artist,
            "album": "",
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "is_playing": state == "playing",
            "source_app": "Spotify",
        }

    def _get_apple_music(self) -> dict | None:
        script = (
            'tell application "Music" to return '
            '(player state as text) & " | " & '
            '(name of current track) & " | " & '
            '(artist of current track)'
        )
        out = self._run_osascript(script)
        if not out:
            return None
        parts = [p.strip() for p in out.split(" | ")]
        if len(parts) < 3:
            return None

        state = parts[0].strip().lower()
        track = parts[1].strip()
        artist = parts[2].strip()
        if not track:
            return None

        pos_s = self._read_float('tell application "Music" to return (player position)')
        dur_s = self._read_float('tell application "Music" to return (duration of current track)')
        progress_ms = int((pos_s or 0.0) * 1000)
        duration_ms = int((dur_s or 0.0) * 1000)
        if duration_ms > 0:
            progress_ms = max(0, min(progress_ms, duration_ms))

        return {
            "conflict": False,
            "track_key": f"{artist} — {track}".strip(),
            "track_name": track,
            "artist": artist,
            "album": "",
            "duration_ms": duration_ms,
            "progress_ms": progress_ms,
            "is_playing": state == "playing",
            "source_app": "Apple Music",
        }

    @staticmethod
    def _is_supported_url(url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
        except Exception:
            return False

        host = (parsed.hostname or "").lower()
        path = (parsed.path or "").lower()

        if host == "music.youtube.com":
            return True
        if host == "open.spotify.com":
            return True
        if host.endswith("spotify.com"):
            return True
        if host.endswith("youtube.com") and path == "/watch":
            return True
        return False

    @classmethod
    def _clean_browser_title(cls, title: str) -> str:
        cleaned = (title or "").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"^[\[\(]\s*.*?\s*[\]\)]\s*", "", cleaned)

        for token in cls._TITLE_NOISE:
            cleaned = re.sub(
                rf"\s*[-|:•·—]\s*{re.escape(token)}\s*$",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                rf"^{re.escape(token)}\s*[-|:•·—]\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

        return cleaned.strip(" -|:•·—")

    @classmethod
    def _parse_track_artist_from_browser(cls, title: str, url: str) -> tuple[str, str]:
        parsed = urlparse(url) if url else None
        host = (parsed.hostname or "").lower() if parsed else ""

        cleaned = cls._clean_browser_title(title)
        if not cleaned:
            return "", ""

        spotify_re = re.compile(
            r"^(?P<track>.+?)\s*-\s*(?:song\s+and\s+lyrics\s+by|canci[oó]n\s+y\s+letra\s+de|chanson\s+et\s+paroles\s+de)\s+(?P<artist>.+)$",
            re.IGNORECASE,
        )
        m = spotify_re.match(cleaned)
        if m:
            return m.group("track").strip(), m.group("artist").strip()

        parts = [p.strip() for p in re.split(r"\s*[—\-|•·|:]\s*", cleaned) if p.strip()]

        if host == "music.youtube.com":
            if len(parts) >= 2:
                return parts[0], parts[1]
            return cleaned, ""

        if host.endswith("spotify.com"):
            if len(parts) >= 2:
                return parts[0], parts[1]
            return cleaned, ""

        if host.endswith("youtube.com"):
            if len(parts) >= 2 and len(parts[1].split()) <= 6:
                return parts[0], parts[1]
            return cleaned, ""

        if len(parts) >= 2:
            return parts[0], parts[1]

        return cleaned, ""

    def _get_browser_candidates(self, browser: str, front_app: str) -> list[BrowserCandidate]:
        if browser == "Safari":
            script = f"""
            if application "{browser}" is running then
                tell application "{browser}"
                    set outLines to {{}}
                    repeat with w in windows
                        repeat with t in tabs of w
                            try
                                set tabTitle to (name of t) as text
                            on error
                                set tabTitle to ""
                            end try
                            try
                                set tabUrl to (URL of t) as text
                            on error
                                set tabUrl to ""
                            end try
                            if tabUrl is not "" then
                                set end of outLines to tabTitle & "||" & tabUrl
                            end if
                        end repeat
                    end repeat
                    set AppleScript's text item delimiters to linefeed
                    set outText to outLines as string
                    set AppleScript's text item delimiters to ""
                    return outText
                end tell
            end if
            return ""
            """
            out = self._run_osascript(script)
            if not out:
                return []

            candidates = []
            for line in out.splitlines():
                parts = line.split("||", 1)
                title = (parts[0] if parts else "").strip()
                url = (parts[1] if len(parts) > 1 else "").strip()
                if not self._is_supported_url(url):
                    continue
                candidates.append(
                    BrowserCandidate(browser, title, url, None, browser == front_app)
                )
            return candidates

        script = f"""
        if application "{browser}" is running then
            tell application "{browser}"
                set outLines to {{}}
                repeat with w in windows
                    repeat with t in tabs of w
                        set tabTitle to ""
                        set tabUrl to ""
                        set tabAudible to ""
                        try
                            set tabTitle to (title of t) as text
                        end try
                        try
                            set tabUrl to (URL of t) as text
                        end try
                        try
                            set tabAudible to (audible of t) as text
                        end try
                        if tabUrl is not "" then
                            set end of outLines to tabTitle & "||" & tabUrl & "||" & tabAudible
                        end if
                    end repeat
                end repeat
                set AppleScript's text item delimiters to linefeed
                set outText to outLines as string
                set AppleScript's text item delimiters to ""
                return outText
            end tell
        end if
        return ""
        """
        out = self._run_osascript(script)
        if not out:
            return []

        candidates = []
        for line in out.splitlines():
            parts = line.split("||")
            title = (parts[0] if parts else "").strip()
            url = (parts[1] if len(parts) > 1 else "").strip()
            audible_raw = (parts[2] if len(parts) > 2 else "").strip().lower()
            audible = True if audible_raw == "true" else False if audible_raw == "false" else None
            if not self._is_supported_url(url):
                continue
            candidates.append(
                BrowserCandidate(browser, title, url, audible, browser == front_app)
            )
        return candidates

    def _get_browser_playback(self) -> dict | None:
        front_app = self._frontmost_app()
        candidates: list[BrowserCandidate] = []
        for browser in self.BROWSERS:
            browser_candidates = self._get_browser_candidates(browser, front_app)
            for c in browser_candidates:
                if c.url or c.title:
                    candidates.append(c)

        if not candidates:
            self._browser_track_key = None
            return None

        def score(c: BrowserCandidate) -> int:
            host = (urlparse(c.url).hostname or "").lower() if c.url else ""
            s = 0
            if c.focused:
                s += 30
            if c.audible is True:
                s += 25
            if host in {"music.youtube.com", "open.spotify.com"}:
                s += 20
            if host.endswith("spotify.com") or host.endswith("youtube.com"):
                s += 10
            if not c.title:
                s -= 8
            return s

        candidate = sorted(candidates, key=score, reverse=True)[0]
        track_name, artist = self._parse_track_artist_from_browser(candidate.title, candidate.url)
        if not track_name:
            track_name = self._clean_browser_title(candidate.title) or "Unknown Track"

        now = time.monotonic()
        track_key = f"{artist} — {track_name}".strip()

        # Browsers do not reliably expose true timestamps; carry forward smoothly.
        is_playing = candidate.audible is True or (candidate.audible is None) or candidate.focused
        if track_key != self._browser_track_key:
            self._browser_track_key = track_key
            self._browser_progress_ms = 0
            self._browser_duration_ms = 0
            self._browser_last_ts = now
        elif is_playing:
            delta_ms = int((now - self._browser_last_ts) * 1000)
            if 0 <= delta_ms <= 5000:
                self._browser_progress_ms += delta_ms

        self._browser_last_ts = now

        return {
            "conflict": False,
            "track_key": track_key,
            "track_name": track_name,
            "artist": artist,
            "album": "",
            "duration_ms": self._browser_duration_ms,
            "progress_ms": max(0, self._browser_progress_ms),
            "is_playing": is_playing,
            "source_app": candidate.browser,
            "source_url": candidate.url,
        }

    def get_current_playback(self) -> dict | None:
        spotify = self._get_spotify()
        if spotify:
            return spotify

        music = self._get_apple_music()
        if music:
            return music

        return None

    def diagnostic_message(self) -> str:
        # Common mac automation denial signal.
        if "-1743" in self._last_error or "Not authorized to send Apple events" in self._last_error:
            return "Grant Automation permission to control Spotify/Music in System Settings."
        if self._last_error:
            return "AppleScript access failed. Check macOS Privacy & Security permissions."
        return "No music app playback detected. Start playback in Spotify or Apple Music."

    def _control_apple_script(self, action: str) -> None:
        spotify_actions = {
            "play_pause": "playpause",
            "next": "next track",
            "previous": "previous track",
        }
        music_actions = {
            "play_pause": "playpause",
            "next": "next track",
            "previous": "previous track",
        }
        if action not in spotify_actions:
            return

        script = f"""
        if application "Spotify" is running then
            tell application "Spotify" to {spotify_actions[action]}
            return
        end if
        if application "Music" is running then
            tell application "Music" to {music_actions[action]}
        end if
        """
        self._run_osascript(script)

    def play_pause(self) -> None:
        self._control_apple_script("play_pause")

    def skip_next(self) -> None:
        self._control_apple_script("next")

    def skip_previous(self) -> None:
        self._control_apple_script("previous")


class WindowsMediaSession(BaseMediaSession):
    """Windows media reader using WMTC with lazy winrt import."""

    def __init__(self):
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
        )
        from winrt.windows.storage.streams import DataReader

        self._MediaManager = MediaManager
        self._PlaybackStatus = PlaybackStatus
        self._DataReader = DataReader

        self._loop = asyncio.new_event_loop()
        self._manager = None
        self._thumb_cache: dict[str, bytes | None] = {}

    @staticmethod
    def _app_display_name(app_id: str) -> str:
        app = (app_id or "").lower()
        if "spotify" in app:
            return "Spotify"
        if "youtube" in app or "ytmusic" in app:
            return "YouTube Music"
        if "applemusic" in app or "apple music" in app or "itunes" in app:
            return "Apple Music"
        if "amazon music" in app or "amazonmusic" in app or "amzn" in app:
            return "Amazon Music"
        if "tidal" in app:
            return "Tidal"
        if "deezer" in app:
            return "Deezer"
        if "yandex" in app or "yandexmusic" in app:
            return "Yandex Music"
        if "msedge" in app:
            return "Microsoft Edge"
        if "chrome" in app:
            return "Google Chrome"
        if "firefox" in app:
            return "Mozilla Firefox"
        return app_id or "Unknown"

    async def _ensure_manager(self):
        if self._manager is None:
            self._manager = await self._MediaManager.request_async()
        return self._manager

    async def _read_thumbnail(self, info) -> bytes | None:
        try:
            thumb_ref = info.thumbnail
            if thumb_ref is None:
                return None
            stream = await thumb_ref.open_read_async()
            size = stream.size
            if size == 0 or size > 10_000_000:
                return None
            reader = self._DataReader(stream.get_input_stream_at(0))
            await reader.load_async(size)
            buf = bytearray(size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception:
            return None

    async def _get_playback(self) -> dict | None:
        manager = await self._ensure_manager()
        sessions = list(manager.get_sessions())
        playing_sessions = []
        playing_apps = []
        for s in sessions:
            try:
                pb_info = s.get_playback_info()
                if pb_info.playback_status == self._PlaybackStatus.PLAYING:
                    playing_sessions.append(s)
                    playing_apps.append(self._app_display_name(s.source_app_user_model_id))
            except Exception:
                continue

        if len(playing_sessions) > 1:
            unique_apps = list(dict.fromkeys(playing_apps))
            return {"conflict": True, "playing_apps": unique_apps}

        session = manager.get_current_session()
        if not session and len(playing_sessions) == 1:
            session = playing_sessions[0]
        if not session:
            return None

        try:
            info = await session.try_get_media_properties_async()
        except Exception:
            return None

        timeline = session.get_timeline_properties()
        playback_info = session.get_playback_info()

        title = info.title or ""
        artist = info.artist or ""
        source_app = self._app_display_name(session.source_app_user_model_id)
        if not title:
            return None

        track_key = f"{artist} — {title}".strip()
        raw_pos_ms = int(timeline.position.total_seconds() * 1000)
        duration_ms = int(timeline.end_time.total_seconds() * 1000)
        is_playing = playback_info.playback_status == self._PlaybackStatus.PLAYING

        progress_ms = raw_pos_ms
        try:
            last_updated = timeline.last_updated_time
            if last_updated and is_playing:
                now = datetime.now(timezone.utc)
                elapsed_s = now.timestamp() - last_updated.timestamp() if hasattr(last_updated, "timestamp") else 0
                if 0 < elapsed_s < 300:
                    progress_ms = raw_pos_ms + int(elapsed_s * 1000)
                    progress_ms = min(progress_ms, duration_ms if duration_ms > 0 else progress_ms)
        except Exception:
            pass

        return {
            "conflict": False,
            "track_key": track_key,
            "track_name": title,
            "artist": artist,
            "album": info.album_title or "",
            "duration_ms": duration_ms,
            "progress_ms": max(0, progress_ms),
            "is_playing": is_playing,
            "source_app": source_app,
        }

    async def _send_control(self, action: str) -> None:
        manager = await self._ensure_manager()
        session = manager.get_current_session()
        if not session:
            return
        if action == "play_pause":
            await session.try_toggle_play_pause_async()
        elif action == "next":
            await session.try_skip_next_async()
        elif action == "previous":
            await session.try_skip_previous_async()

    def get_current_playback(self) -> dict | None:
        try:
            return self._loop.run_until_complete(self._get_playback())
        except Exception:
            return None

    def play_pause(self) -> None:
        try:
            self._loop.run_until_complete(self._send_control("play_pause"))
        except Exception:
            return

    def skip_next(self) -> None:
        try:
            self._loop.run_until_complete(self._send_control("next"))
        except Exception:
            return

    def skip_previous(self) -> None:
        try:
            self._loop.run_until_complete(self._send_control("previous"))
        except Exception:
            return

    def fetch_thumbnail(self, track_key: str, callback) -> None:
        if track_key in self._thumb_cache:
            callback(track_key, self._thumb_cache[track_key])
            return

        def _worker():
            loop = asyncio.new_event_loop()
            try:
                manager = loop.run_until_complete(self._MediaManager.request_async())
                session = manager.get_current_session()
                if not session:
                    callback(track_key, None)
                    return
                info = loop.run_until_complete(session.try_get_media_properties_async())
                result = loop.run_until_complete(self._read_thumbnail(info))
                self._thumb_cache[track_key] = result
                if len(self._thumb_cache) > 20:
                    oldest = next(iter(self._thumb_cache))
                    del self._thumb_cache[oldest]
                callback(track_key, result)
            except Exception:
                callback(track_key, None)
            finally:
                loop.close()

        threading.Thread(target=_worker, daemon=True).start()


class NullMediaSession(BaseMediaSession):
    """Fallback backend for unsupported environments."""

    def get_current_playback(self) -> dict | None:
        return None


def create_media_session() -> BaseMediaSession:
    system = platform.system().lower()
    if system == "darwin":
        return MacMediaSession()
    if system == "windows":
        try:
            return WindowsMediaSession()
        except Exception as exc:
            print(f"[MediaSession] Windows backend unavailable: {exc}")
            return NullMediaSession()
    return NullMediaSession()
