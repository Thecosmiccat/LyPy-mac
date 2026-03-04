"""Background-friendly LRCLIB lyrics fetcher with cached HTTP session."""

from __future__ import annotations

import re
import threading

import requests


class LyricsFetcher:
    API_URL = "https://lrclib.net/api/get"
    SEARCH_URL = "https://lrclib.net/api/search"
    TIMEOUT = (3.0, 8.0)

    HEADERS = {
        "User-Agent": "LyPy/1.0",
    }

    def __init__(self):
        self._cache: dict[str, dict] = {}
        self._cache_lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    @staticmethod
    def _parse_lrc(lrc_text: str) -> list[dict]:
        lines = []
        pattern = re.compile(r"\[(\d{2}):(\d{2})\.(\d{2,3})\]\s*(.*)")
        for raw in (lrc_text or "").strip().splitlines():
            m = pattern.match(raw.strip())
            if not m:
                continue
            mins, secs, frac, words = m.groups()
            ms = int(frac) * 10 if len(frac) == 2 else int(frac)
            time_ms = int(mins) * 60_000 + int(secs) * 1000 + ms
            lines.append({"time_ms": max(0, time_ms), "words": words})
        return sorted(lines, key=lambda x: x["time_ms"])

    def get_lyrics(self, track_name: str, artist: str, album: str = "", duration_s: int = 0) -> dict | None:
        cache_key = f"{artist}|{track_name}".lower().strip()
        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        result = self._try_exact(track_name, artist, album, duration_s)
        if not result:
            result = self._try_search(track_name, artist)
        if not result:
            result = {"synced": False, "lines": []}

        with self._cache_lock:
            self._cache[cache_key] = result
        return result

    def _try_exact(self, track: str, artist: str, album: str, duration_s: int) -> dict | None:
        try:
            params: dict[str, str | int] = {
                "track_name": track,
                "artist_name": artist,
            }
            if album:
                params["album_name"] = album
            if duration_s > 0:
                params["duration"] = duration_s

            resp = self._session.get(self.API_URL, params=params, timeout=self.TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return self._parse_response(resp.json())
        except Exception as e:
            print(f"[LyricsFetcher] Exact lookup failed: {e}")
            return None

    def _try_search(self, track: str, artist: str) -> dict | None:
        try:
            resp = self._session.get(
                self.SEARCH_URL,
                params={"q": f"{artist} {track}"},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            results = resp.json()
            if not results:
                return None

            for item in results:
                if item.get("syncedLyrics"):
                    return self._parse_response(item)
            for item in results:
                if item.get("plainLyrics"):
                    return self._parse_response(item)
            return None
        except Exception as e:
            print(f"[LyricsFetcher] Search failed: {e}")
            return None

    def _parse_response(self, data: dict) -> dict | None:
        synced_lrc = data.get("syncedLyrics")
        if synced_lrc:
            lines = self._parse_lrc(synced_lrc)
            if lines:
                return {"synced": True, "lines": lines}

        plain = data.get("plainLyrics", "")
        if plain:
            lines = [{"time_ms": 0, "words": line} for line in plain.strip().splitlines() if line.strip()]
            return {"synced": False, "lines": lines}

        return None

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()
