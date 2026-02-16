"""Feature flags framework — JSON-based local flags for incremental feature rollout.

Usage:
    from pragmatic_file_declutter.core.feature_flags import flags

    if flags.is_enabled("dedup_similar"):
        # Run similar photo detection
        ...
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Default flags — all features start disabled until explicitly enabled
_DEFAULT_FLAGS: dict[str, bool] = {
    # v0.1.0 — Scan + Dedup
    "scanner": True,
    "dedup_identical": True,
    "dedup_similar": False,
    # v0.2.0 — Classification
    "classify_heuristics": False,
    "classify_clip": False,
    "classify_gemini": False,
    "classify_gpt_fallback": False,
    # v0.3.0 — Events
    "event_clustering": False,
    "event_timeline": False,
    # v0.4.0 — Search
    "clip_search": False,
    # Experimental
    "face_detection": False,
    "watch_mode": False,
}

_FLAGS_DIR = Path.home() / ".pragmatic-declutter"
_FLAGS_FILE = _FLAGS_DIR / "flags.json"


class FeatureFlags:
    """Manages feature flags with JSON persistence."""

    def __init__(self, flags_file: Path = _FLAGS_FILE) -> None:
        self._flags_file = flags_file
        self._flags: dict[str, bool] = dict(_DEFAULT_FLAGS)
        self._load()

    def _load(self) -> None:
        """Load flags from disk, merging with defaults."""
        if self._flags_file.exists():
            try:
                with open(self._flags_file, encoding="utf-8") as f:
                    saved: dict[str, Any] = json.load(f)
                # Merge: saved values override defaults, but new defaults are added
                for key, value in saved.items():
                    if key in self._flags and isinstance(value, bool):
                        self._flags[key] = value
            except (json.JSONDecodeError, OSError):
                pass  # Use defaults if file is corrupted

    def _save(self) -> None:
        """Persist current flags to disk."""
        self._flags_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._flags_file, "w", encoding="utf-8") as f:
            json.dump(self._flags, f, indent=2)

    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return self._flags.get(flag_name, False)

    def enable(self, flag_name: str) -> None:
        """Enable a feature flag."""
        if flag_name in self._flags:
            self._flags[flag_name] = True
            self._save()

    def disable(self, flag_name: str) -> None:
        """Disable a feature flag."""
        if flag_name in self._flags:
            self._flags[flag_name] = False
            self._save()

    def all_flags(self) -> dict[str, bool]:
        """Return a copy of all flags."""
        return dict(self._flags)

    def reset(self) -> None:
        """Reset all flags to defaults."""
        self._flags = dict(_DEFAULT_FLAGS)
        self._save()


# Singleton instance
flags = FeatureFlags()
