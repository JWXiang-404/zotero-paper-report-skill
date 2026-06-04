"""Main orchestrator: collect items, filter, spawn subagents, track progress.

This is the heart of the batch engine. It coordinates:
1. Collection traversal (via ZoteroReader)
2. Item filtering (skip existing, check PDF)
3. Concurrent subagent spawning (via subagent.py)
4. Progress tracking (via tracker.py)
5. Terminal output (via reporter.py)
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import TYPE_CHECKING

from . import reporter
from .subagent import run_subagent

if TYPE_CHECKING:
    from .config import Config
    from .tracker import ProgressTracker
    from .zotero_reader import DryRunResult, ItemInfo, ZoteroReader


# ── orchestrator ───────────────────────────────────────────────


class BatchOrchestrator:
    """Orchestrates batch report generation across Zotero collections."""

    def __init__(
        self,
        config: "Config",
        reader: "ZoteroReader",
        tracker: "ProgressTracker",
    ):
        self.config = config
        self.reader = reader
        self.tracker = tracker
        self._sem: asyncio.Semaphore | None = None
        self._completed_count = 0
        self._total_items = 0
        self._generated_count = 0
        self._lock = asyncio.Lock()

    # ── public API ─────────────────────────────────────────────

    async def run(
        self,
        collections: list[str] | None = None,
        collection_keys: list[str] | None = None,
        all_collections: bool = False,
        preview_only: bool = False,
    ) -> dict:
        """Main entry point.

        Args:
            collections: Collection names to process.
            collection_keys: Collection keys to process.
            all_collections: Process all top-level collections.
            preview_only: Preview mode — don't actually generate reports.

        Returns:
            dict with summary stats.
        """
        start_time = time.monotonic()

        # ── Resolve target collections ──────────────────────
        resolved = self._resolve_collections(
            collections, collection_keys, all_collections
        )

        if not resolved:
            print("未找到匹配的分类。使用 --preview-only --all 查看所有可用分类。")
            return {"total": 0, "done": 0, "failed": 0, "skipped": 0}

        # ── Collect items (always recursive) ─────────────
        all_items: list[ItemInfo] = []
        for coll in resolved:
            tree = self.reader.get_collections_tree(key=coll.key)
            if not tree:
                tree = [coll]

            coll_ids = [c.collection_id for c in tree]
            items = self.reader.get_items_in_collections(coll_ids)
            for item in items:
                item.collection_name = coll.name
            all_items.extend(items)

        # Deduplicate by item key
        seen: set[str] = set()
        deduped: list[ItemInfo] = []
        for item in all_items:
            if item.key not in seen:
                seen.add(item.key)
                deduped.append(item)

        # ── Filter ─────────────────────────────────────────
        to_generate: list[ItemInfo] = []
        skipped: list[tuple[ItemInfo, str]] = []

        for item in deduped:
            if item.has_report and self.config.batch.skip_existing:
                self.tracker.mark_skipped(item.key, "existing_note")
                skipped.append((item, "existing_note"))
            elif not item.has_pdf:
                action = self.config.behavior.on_missing_pdf
                if action == "skip":
                    self.tracker.mark_skipped(item.key, "no_pdf")
                    skipped.append((item, "no_pdf"))
                elif action == "abstract":
                    # Still generate — subagent will use abstract fallback
                    to_generate.append(item)
                elif action == "ask":
                    # In non-interactive mode, treat as skip
                    self.tracker.mark_skipped(item.key, "no_pdf")
                    skipped.append((item, "no_pdf"))
            else:
                to_generate.append(item)

        # Register items in tracker
        self.tracker.register_items(
            [i.key for i in to_generate],
            {i.key: i.title for i in to_generate},
        )

        # ── Preview mode ───────────────────────────────────
        if preview_only:
            return self._do_preview(resolved, deduped, to_generate, skipped)

        # ── Print header ───────────────────────────────────
        coll_names = [c.name for c in resolved]
        reporter.print_header(
            coll_names, self.config.batch.concurrency, len(to_generate)
        )

        # ── Process ────────────────────────────────────────
        self._total_items = len(to_generate) + len(skipped)
        self._generated_count = len(to_generate)
        self._completed_count = 0
        self._sem = asyncio.Semaphore(self.config.batch.concurrency)

        # Print skipped items
        for item, reason in skipped:
            self._completed_count += 1
            reporter.print_progress_skip(
                self._completed_count, self._total_items,
                item.title, reason,
            )

        # Spawn subagents
        tasks = [self._process_one(item) for item in to_generate]
        await asyncio.gather(*tasks, return_exceptions=True)

        # ── Summary ────────────────────────────────────────
        total_duration = time.monotonic() - start_time
        reporter.print_summary(self.tracker, total_duration)

        counts = self.tracker.counts()
        return {
            "total": len(deduped),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
        }

    async def run_with_items(
        self,
        items: list,
        run_id: str = "",
    ) -> dict:
        """Run the orchestrator on a specific list of ItemInfo objects.

        Used by --resume to re-process only pending items.
        """
        start_time = time.monotonic()

        self._total_items = len(items)
        self._generated_count = len(items)
        self._completed_count = 0
        self._sem = asyncio.Semaphore(self.config.batch.concurrency)

        reporter.print_header(
            ["(resumed)"], self.config.batch.concurrency, len(items)
        )

        tasks = [self._process_one(item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.monotonic() - start_time
        reporter.print_summary(self.tracker, total_duration)

        counts = self.tracker.counts()
        return {
            "total": len(items),
            "done": counts.get("done", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
        }

    # ── internals ──────────────────────────────────────────────

    async def _process_one(self, item: ItemInfo) -> None:
        """Process a single item: spawn subagent, track result."""
        async with self._sem:
            async with self._lock:
                self._completed_count += 1
                idx = self._completed_count
                total = self._total_items

            self.tracker.mark_running(item.key)
            short = _shorten(item.title, 50)
            sys.stderr.write(
                f"  \033[0;36m[{idx}/{total}]\033[0m "
                f"\033[1;33m⏳\033[0m {short}\n"
            )
            sys.stderr.flush()

            result = await run_subagent(
                item_key=item.key,
                title=item.title,
                authors=item.authors,
                year=item.year,
                config=self.config,
            )

            async with self._lock:
                if result.success:
                    self.tracker.mark_done(
                        item.key,
                        note_key=result.note_key,
                        duration_sec=result.duration_sec,
                    )
                    reporter.print_progress_done(
                        idx, total,
                        item.title, result.duration_sec, result.note_key,
                    )
                else:
                    err_msg = result.error or "unknown error"
                    if result.log_path:
                        err_msg += f"\n        Log: {result.log_path}"
                    self.tracker.mark_failed(
                        item.key,
                        error=err_msg,
                        duration_sec=result.duration_sec,
                        retries=result.retries,
                    )
                    reporter.print_progress_failed(
                        idx, total,
                        item.title, err_msg,
                        result.duration_sec,
                    )

    def _resolve_collections(
        self,
        names: list[str] | None,
        keys: list[str] | None,
        all_colls: bool,
    ) -> list:
        """Resolve collection identifiers to CollectionInfo objects."""
        from .zotero_reader import CollectionInfo as CI

        resolved: list[CI] = []

        if all_colls:
            resolved = self.reader.get_top_level_collections()
            return resolved

        if keys:
            for key in keys:
                coll = self.reader.get_collection_by_key(key)
                if coll:
                    resolved.append(coll)
                else:
                    print(f"警告: 未找到 key={key} 的分类")

        if names:
            for name in names:
                matches = self.reader.find_collections_by_name(name)
                if matches:
                    resolved.extend(matches)
                else:
                    # Fuzzy search
                    fuzzy = self.reader.find_collections_by_name_fuzzy(name)
                    if fuzzy:
                        print(f"分类 '{name}' 未精确匹配，找到以下候选: " +
                              ", ".join(c.name for c in fuzzy[:5]))
                    else:
                        print(f"警告: 未找到名为 '{name}' 的分类")

        return resolved

    def _do_preview(
        self,
        resolved: list,
        all_items: list[ItemInfo],
        to_generate: list[ItemInfo],
        skipped: list[tuple[ItemInfo, str]],
    ) -> dict:
        """Print preview-only summary."""
        reporter.print_preview_header()

        coll_names = [c.name for c in resolved]
        print(f"  目标分类: {', '.join(coll_names)}")
        print(f"  论文总数: {len(all_items)}")
        print(f"  待生成: {len(to_generate)}")
        print(f"  跳过: {len(skipped)}")
        reporter.print_config(self._config_summary())

        reporter.print_preview_items(to_generate, "待生成", reporter.GREEN)
        existing = [item for item, r in skipped if r == "existing_note"]
        reporter.print_preview_items(existing, "已有报告，跳过", reporter.YELLOW)
        no_pdf = [item for item, r in skipped if r == "no_pdf"]
        reporter.print_preview_items(no_pdf, "无PDF，跳过", reporter.RED)

        print()
        return {
            "total": len(all_items),
            "to_generate": len(to_generate),
            "skipped": len(skipped),
        }

    def _config_summary(self) -> dict:
        return {
            "format": self.config.output.format,
            "save_local": self.config.output.save_local,
            "concurrency": self.config.batch.concurrency,
            "on_missing_pdf": self.config.behavior.on_missing_pdf,
            "subagent_timeout": f"{self.config.behavior.subagent_timeout}s",
        }


def _shorten(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
