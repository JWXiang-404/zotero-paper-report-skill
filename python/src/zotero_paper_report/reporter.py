"""Terminal output formatting: real-time progress and final summary."""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import ProgressTracker


# ── ANSI helpers ────────────────────────────────────────────────

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
GRAY = "\033[0;37m"
BOLD = "\033[1m"
NC = "\033[0m"  # No Color

CHECK = "✓"
CROSS = "✗"
SKIP = "⏭"
HOURGLASS = "⏳"


# ── progress output ────────────────────────────────────────────


def print_header(
    collections: list[str],
    concurrency: int,
    total: int,
) -> None:
    """Print the batch run header."""
    coll_str = ", ".join(collections)
    print()
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════{NC}")
    print(f"{BOLD}  📚 zotero-paper-report{NC}")
    print(f"  目标分类: {coll_str} (含子分类)")
    print(f"  总论文数: {total}")
    print(f"  并发度: {concurrency}")
    print(f"{BOLD}{CYAN}──────────────────────────────────────────────{NC}")


def print_progress_done(
    index: int,
    total: int,
    title: str,
    duration_sec: float,
    note_key: str | None = None,
) -> None:
    """Print a success line for one completed item."""
    note_str = f", note: {note_key}" if note_key else ""
    # Truncate long titles
    short_title = _shorten(title, 55)
    print(
        f"  {GREEN}[{index}/{total}] {CHECK}{NC} {short_title} "
        f"{GRAY}({duration_sec:.0f}s{note_str}){NC}"
    )
    sys.stdout.flush()


def print_progress_failed(
    index: int,
    total: int,
    title: str,
    error: str,
    duration_sec: float | None = None,
) -> None:
    """Print a failure line for one item."""
    short_title = _shorten(title, 50)
    err_short = _shorten(error, 60)
    dur_str = f" ({duration_sec:.0f}s)" if duration_sec else ""
    print(
        f"  {RED}[{index}/{total}] {CROSS}{NC} {short_title} "
        f"{RED}— {err_short}{dur_str}{NC}"
    )
    sys.stdout.flush()


def print_progress_skip(
    index: int,
    total: int,
    title: str,
    reason: str,
) -> None:
    """Print a skip line for one item."""
    short_title = _shorten(title, 50)
    reason_map = {
        "existing_note": "已有报告，跳过",
        "no_pdf": "无PDF，已跳过",
    }
    reason_text = reason_map.get(reason, reason)
    print(
        f"  {YELLOW}[{index}/{total}] {SKIP}{NC} {short_title} "
        f"{GRAY}— {reason_text}{NC}"
    )
    sys.stdout.flush()


def print_progress_running(count: int) -> None:
    """Print a running indicator line."""
    print(f"  {CYAN}{HOURGLASS} 正在生成 {count} 篇...{NC}", end="\r")
    sys.stdout.flush()


# ── summary output ──────────────────────────────────────────────


def print_summary(
    tracker: "ProgressTracker",
    total_duration_sec: float,
) -> None:
    """Print the final summary table after the batch completes."""
    counts = tracker.counts()
    done = counts.get("done", 0)
    failed = counts.get("failed", 0)
    skipped = counts.get("skipped", 0)
    total = tracker.total_items

    dur_min = total_duration_sec / 60

    print()
    print(f"{BOLD}{GREEN}╔══════════════════════════════════════════════╗{NC}")
    print(f"{BOLD}{GREEN}║  📊 批量文献报告生成完成                      ║{NC}")
    print(f"{BOLD}{GREEN}╠══════════════════════════════════════════════╣{NC}")

    if tracker.target_collections:
        print(
            f"{BOLD}{GREEN}║{NC}  目标分类: {', '.join(tracker.target_collections[:3])}"
        )

    print(f"{BOLD}{GREEN}║{NC}  总论文数: {total}")
    print(f"{BOLD}{GREEN}║{NC}  ✅ 成功生成: {done}")
    print(f"{BOLD}{GREEN}║{NC}  ❌ 失败: {failed}")
    print(f"{BOLD}{GREEN}║{NC}  ⏭  跳过: {skipped}")
    print(f"{BOLD}{GREEN}║{NC}  总耗时: {dur_min:.0f} 分钟")

    # Failed items
    failures = tracker.failed_items()
    if failures:
        print(f"{BOLD}{GREEN}╠══════════════════════════════════════════════╣{NC}")
        print(f"{BOLD}{GREEN}║{NC}  失败列表:")
        for key, status in failures:
            err = _shorten(status.error or "unknown", 45)
            print(f"{BOLD}{GREEN}║{NC}  · {_shorten(status.title, 40)} — {err}")

    # Resume hint
    if failures:
        print(f"{BOLD}{GREEN}╠══════════════════════════════════════════════╣{NC}")
        print(
            f"{BOLD}{GREEN}║{NC}  重试失败项: zotero-paper-report --resume {tracker.run_id}"
        )

    print(f"{BOLD}{GREEN}╚══════════════════════════════════════════════╝{NC}")
    print()


def print_preview_header() -> None:
    """Print header for preview-only mode."""
    print()
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════{NC}")
    print(f"{BOLD}  🔍 PREVIEW — 预览模式（不实际生成）{NC}")
    print(f"{BOLD}{CYAN}──────────────────────────────────────────────{NC}")


def print_preview_items(
    items: list,
    label: str,
    color: str = GRAY,
    max_show: int = 10,
) -> None:
    """Print a list of items with a label (for preview-only mode)."""
    if not items:
        return

    print(f"\n  {label} ({len(items)} 篇):")
    for i, item in enumerate(items[:max_show]):
        title = _shorten(getattr(item, "title", str(item)), 60)
        print(f"    {color}{i + 1}.{NC} {title}")
    if len(items) > max_show:
        print(f"    {GRAY}... 还有 {len(items) - max_show} 篇{NC}")


def print_config(config_summary: dict) -> None:
    """Print current configuration values."""
    print(f"\n  {BOLD}当前配置:{NC}")
    for key, value in config_summary.items():
        print(f"    {GRAY}{key}:{NC} {value}")


# ── helpers ─────────────────────────────────────────────────────


def _shorten(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ... if truncated."""
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
