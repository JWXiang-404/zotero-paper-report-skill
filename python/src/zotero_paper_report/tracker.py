"""Progress tracking with JSON persistence for resume support.

Each batch run gets a unique run_id. Progress is saved incrementally
so that interrupted runs can be resumed without re-processing completed items.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── data classes ───────────────────────────────────────────────


@dataclass
class ItemStatus:
    title: str
    status: str = "pending"   # pending | running | done | failed | skipped
    note_key: str | None = None
    error: str | None = None
    reason: str | None = None   # "existing_note" | "no_pdf" | ...
    duration_sec: float | None = None
    retries: int = 0
    timestamp: str | None = None


# ── tracker ────────────────────────────────────────────────────


class ProgressTracker:
    """Persistent progress tracker with JSON backing."""

    def __init__(
        self,
        run_id: str,
        output_dir: Path | str | None = None,
        config_snapshot: dict[str, Any] | None = None,
        target_collections: list[str] | None = None,
    ):
        self.run_id = run_id
        self.output_dir = Path(output_dir or ProgressTracker._default_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config_snapshot = config_snapshot or {}
        self.target_collections = target_collections or []
        self.total_items = 0
        self.items: dict[str, ItemStatus] = {}

    @staticmethod
    def _default_dir() -> Path:
        return Path.home() / ".claude" / "zotero-paper-report"

    @property
    def file_path(self) -> Path:
        return self.output_dir / f"{self.run_id}.json"

    # ── item status management ─────────────────────────────────

    def register_items(self, item_keys: list[str], titles: dict[str, str]) -> None:
        """Register items to track. Call once before processing."""
        for key in item_keys:
            if key not in self.items:
                self.items[key] = ItemStatus(
                    title=titles.get(key, key),
                    status="pending",
                )
        self.total_items = len(self.items)
        self.save()

    def is_done(self, item_key: str) -> bool:
        """Check if an item has already been completed."""
        return item_key in self.items and self.items[item_key].status == "done"

    def is_skipped(self, item_key: str) -> bool:
        """Check if an item has been skipped."""
        return item_key in self.items and self.items[item_key].status == "skipped"

    def mark_running(self, item_key: str) -> None:
        if item_key in self.items:
            self.items[item_key].status = "running"
            self.items[item_key].timestamp = _now()

    def mark_done(
        self,
        item_key: str,
        note_key: str | None = None,
        duration_sec: float | None = None,
    ) -> None:
        if item_key in self.items:
            s = self.items[item_key]
            s.status = "done"
            s.note_key = note_key
            s.duration_sec = duration_sec
            s.timestamp = _now()
        self.save()

    def mark_failed(
        self,
        item_key: str,
        error: str,
        duration_sec: float | None = None,
        retries: int = 0,
    ) -> None:
        if item_key in self.items:
            s = self.items[item_key]
            s.status = "failed"
            s.error = error
            s.duration_sec = duration_sec
            s.retries = retries
            s.timestamp = _now()
        self.save()

    def mark_skipped(self, item_key: str, reason: str) -> None:
        if item_key in self.items:
            s = self.items[item_key]
            s.status = "skipped"
            s.reason = reason
            s.timestamp = _now()
        # Also mark existing items that weren't pre-registered
        elif reason == "existing_note":
            self.items[item_key] = ItemStatus(
                title=item_key,
                status="skipped",
                reason=reason,
                timestamp=_now(),
            )
        self.save()

    # ── aggregation ────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        """Return {status: count} for all items."""
        counts: dict[str, int] = {}
        for s in self.items.values():
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    def failed_items(self) -> list[tuple[str, ItemStatus]]:
        """Return (key, status) for all failed items."""
        return [(k, v) for k, v in self.items.items() if v.status == "failed"]

    def skipped_items(self) -> list[tuple[str, ItemStatus]]:
        """Return (key, status) for all skipped items."""
        return [(k, v) for k, v in self.items.items() if v.status == "skipped"]

    # ── persistence ────────────────────────────────────────────

    def save(self) -> None:
        """Write current progress to JSON file."""
        data: dict[str, Any] = {
            "run_id": self.run_id,
            "config": self.config_snapshot,
            "target_collections": self.target_collections,
            "total_items": self.total_items,
            "items": {
                k: {
                    "title": v.title,
                    "status": v.status,
                    "note_key": v.note_key,
                    "error": v.error,
                    "reason": v.reason,
                    "duration_sec": v.duration_sec,
                    "retries": v.retries,
                    "timestamp": v.timestamp,
                }
                for k, v in self.items.items()
            },
        }

        # Atomic write: write to temp file, then rename
        tmp_path = self.file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.file_path)

    @classmethod
    def load(cls, run_id_or_path: str) -> ProgressTracker:
        """Load a tracker from a saved JSON file.

        Args:
            run_id_or_path: Either a run_id (looked up in default dir)
                           or a full path to a JSON file.
        """
        path = Path(run_id_or_path)
        if not path.exists():
            # Assume it's a run_id
            path = cls._default_dir() / f"{run_id_or_path}.json"

        if not path.exists():
            raise FileNotFoundError(f"Progress file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tracker = cls(
            run_id=data["run_id"],
            output_dir=path.parent,
            config_snapshot=data.get("config", {}),
            target_collections=data.get("target_collections", []),
        )
        tracker.total_items = data.get("total_items", 0)

        for key, item_data in data.get("items", {}).items():
            tracker.items[key] = ItemStatus(
                title=item_data.get("title", key),
                status=item_data.get("status", "pending"),
                note_key=item_data.get("note_key"),
                error=item_data.get("error"),
                reason=item_data.get("reason"),
                duration_sec=item_data.get("duration_sec"),
                retries=item_data.get("retries", 0),
                timestamp=item_data.get("timestamp"),
            )

        return tracker


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
