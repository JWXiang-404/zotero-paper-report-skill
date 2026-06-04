"""Configuration management: dataclass, YAML loading, CLI override, env vars.

Priority: CLI flags > environment variables > config.yaml > built-in defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── config dataclasses ──────────────────────────────────────────


@dataclass
class OutputConfig:
    format: str = "html"       # "html" | "markdown"
    save_local: bool = True    # also save to PDF directory


@dataclass
class BatchConfig:
    concurrency: int = 3       # max parallel Claude Code subprocesses
    skip_existing: bool = True # skip items with existing "文献报告" note


@dataclass
class BehaviorConfig:
    on_missing_pdf: str = "skip"     # "skip" | "abstract" | "ask"
    on_subagent_error: str = "skip"  # "skip" | "retry"
    max_retries: int = 1
    subagent_timeout: int = 600      # seconds


@dataclass
class ZoteroConfig:
    db_path: str | None = None       # auto-detect if None
    storage_path: str | None = None  # auto-detect if None


@dataclass
class Config:
    output: OutputConfig = field(default_factory=OutputConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    zotero: ZoteroConfig = field(default_factory=ZoteroConfig)

    # ── factory methods ────────────────────────────────────────

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load config from YAML file. Missing keys keep defaults."""
        if not path.exists():
            return cls.default()

        with open(path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        return cls._from_dict(raw)

    @classmethod
    def default(cls) -> "Config":
        return cls()

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> "Config":
        """Build Config from nested dict, keeping defaults for missing keys."""
        return cls(
            output=OutputConfig(
                format=cls._get_nested(raw, "output", "format", default="html"),
                save_local=cls._get_nested(raw, "output", "save_local", default=True),
            ),
            batch=BatchConfig(
                concurrency=cls._get_nested(raw, "batch", "concurrency", default=3),
                skip_existing=cls._get_nested(raw, "batch", "skip_existing", default=True),
            ),
            behavior=BehaviorConfig(
                on_missing_pdf=cls._get_nested(raw, "behavior", "on_missing_pdf", default="skip"),
                on_subagent_error=cls._get_nested(raw, "behavior", "on_subagent_error", default="skip"),
                max_retries=cls._get_nested(raw, "behavior", "max_retries", default=1),
                subagent_timeout=cls._get_nested(raw, "behavior", "subagent_timeout", default=600),
            ),
            zotero=ZoteroConfig(
                db_path=raw.get("zotero", {}).get("db_path"),
                storage_path=raw.get("zotero", {}).get("storage_path"),
            ),
        )

    @staticmethod
    def _get_nested(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
        for k in keys:
            if not isinstance(d, dict):
                return default
            d = d.get(k, {})  # type: ignore[assignment]
        return d if d != {} else default

    # ── path resolution ────────────────────────────────────────

    def resolve_paths(self) -> None:
        """Auto-detect Zotero paths if not explicitly configured."""
        home = Path.home()

        if not self.zotero.db_path:
            candidates = [
                home / "Zotero" / "zotero.sqlite",
                home / ".zotero" / "zotero.sqlite",
                home / "Library" / "Application Support" / "Zotero" / "zotero.sqlite",
            ]
            for c in candidates:
                if c.exists():
                    self.zotero.db_path = str(c)
                    break
            else:
                self.zotero.db_path = str(candidates[0])  # best-effort

        if not self.zotero.storage_path:
            db = Path(self.zotero.db_path)
            storage = db.parent / "storage"
            if storage.is_dir():
                self.zotero.storage_path = str(storage)

    # ── CLI override ───────────────────────────────────────────

    def apply_cli_overrides(
        self,
        *,
        format: str | None = None,
        save_local: bool | None = None,
        concurrency: int | None = None,
        skip_existing: bool | None = None,
        on_missing_pdf: str | None = None,
    ) -> None:
        """Apply CLI flag overrides. Only non-None values override."""
        if format is not None:
            self.output.format = format
        if save_local is not None:
            self.output.save_local = save_local
        if concurrency is not None:
            self.batch.concurrency = concurrency
        if skip_existing is not None:
            self.batch.skip_existing = skip_existing
        if on_missing_pdf is not None:
            self.behavior.on_missing_pdf = on_missing_pdf

    # ── env var override ───────────────────────────────────────

    def apply_env_overrides(self) -> None:
        """Apply ZOTERO_BATCH_* environment variables."""
        mapping = {
            "ZOTERO_BATCH_FORMAT": ("output", "format"),
            "ZOTERO_BATCH_SAVE_LOCAL": ("output", "save_local"),
            "ZOTERO_BATCH_CONCURRENCY": ("batch", "concurrency"),
            "ZOTERO_BATCH_SKIP_EXISTING": ("batch", "skip_existing"),
            "ZOTERO_BATCH_ON_MISSING_PDF": ("behavior", "on_missing_pdf"),
            "ZOTERO_BATCH_TIMEOUT": ("behavior", "subagent_timeout"),
        }
        for env_var, (section, attr) in mapping.items():
            val = os.environ.get(env_var)
            if val is None:
                continue
            section_obj = getattr(self, section)
            current_type = type(getattr(section_obj, attr))
            if current_type is bool:
                setattr(section_obj, attr, val.lower() in ("1", "true", "yes"))
            elif current_type is int:
                setattr(section_obj, attr, int(val))
            else:
                setattr(section_obj, attr, val)
