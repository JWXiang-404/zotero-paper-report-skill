"""CLI for zotero-paper-report — batch literature report generation from Zotero.

Usage:
    zotero-paper-report --collection "编译优化"
    zotero-paper-report --collection "编译优化" --concurrency 5
    zotero-paper-report --all --preview-only
    zotero-paper-report --resume <run_id>
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import Config, OutputConfig, BatchConfig, BehaviorConfig, ZoteroConfig
from .orchestrator import BatchOrchestrator
from .tracker import ProgressTracker
from .zotero_reader import ZoteroReader


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Handle --resume early (loads its own config from progress file)
    if args.resume:
        _resume(args.resume)
        return

    # Load config
    config = _load_config(args)

    # Connect to Zotero
    reader = ZoteroReader(config.zotero.db_path)

    # Create tracker
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tracker = ProgressTracker(
        run_id=run_id,
        config_snapshot={
            "format": config.output.format,
            "save_local": config.output.save_local,
            "concurrency": config.batch.concurrency,
            "skip_existing": config.batch.skip_existing,
            "on_missing_pdf": config.behavior.on_missing_pdf,
        },
    )

    # Run orchestrator
    orchestrator = BatchOrchestrator(config, reader, tracker)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                orchestrator.run(
                    collections=args.collection,
                    collection_keys=args.collection_key,
                    all_collections=args.all,
                    preview_only=args.preview_only,
                )
            )
            # Drain pending callbacks so subprocess transports clean up
            loop.run_until_complete(asyncio.sleep(0.1))
        finally:
            loop.close()
    except KeyboardInterrupt:
        print("\n\n⚠️  批量生成已中断。")
        print(f"   恢复命令: zotero-paper-report --resume {run_id}")
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ 错误: {exc}")
        sys.exit(1)

    # Non-zero exit if any failures (for CI/scripts)
    if result.get("failed", 0) > 0:
        sys.exit(2)


# ── argument parser ────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zotero-paper-report",
        description="批量生成 Zotero 文献报告，支持分类遍历、并发控制和断点续传。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  zotero-paper-report --collection "编译优化"                 单分类生成
  zotero-paper-report --collection "编译优化" --concurrency 5  指定并发度为5
  zotero-paper-report --all --preview-only                    预览所有论文
  zotero-paper-report --resume 20260604-143022                恢复中断的任务
  zotero-paper-report --config ./my-config.yaml --collection "AI"  使用自定义配置
        """,
    )

    # Target selection (mutually exclusive-ish — at least one needed unless --resume)
    target = p.add_argument_group("目标选择 (至少指定一个)")
    target.add_argument(
        "--collection", "-c",
        action="append",
        help="按分类名选择（可重复指定，如 -c A -c B）",
    )
    target.add_argument(
        "--collection-key", "-k",
        action="append",
        help="按分类 key 选择（可重复指定）",
    )
    target.add_argument(
        "--all", "-a",
        action="store_true",
        help="处理所有顶级分类",
    )

    # Behavior flags
    behavior = p.add_argument_group("行为选项")
    behavior.add_argument(
        "--concurrency", "-j",
        type=int,
        help="最大并发 Claude Code 子进程数 (默认: 3)",
    )
    behavior.add_argument(
        "--format", "-f",
        choices=["html", "markdown"],
        help="输出格式 (默认: html)",
    )
    behavior.add_argument(
        "--no-save-local",
        action="store_true",
        help="不保存本地文件，仅写入 Zotero 笔记",
    )
    behavior.add_argument(
        "--on-missing-pdf",
        choices=["skip", "abstract", "ask"],
        help="无 PDF 时的处理策略 (默认: skip)",
    )
    behavior.add_argument(
        "--preview-only", "-P",
        action="store_true",
        help="预览模式：列出论文但不实际生成",
    )

    # Config / resume
    mgmt = p.add_argument_group("配置与恢复")
    mgmt.add_argument(
        "--config",
        type=Path,
        help="自定义 YAML 配置文件路径",
    )
    mgmt.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="从指定的 run_id 恢复中断的任务",
    )

    return p


# ── config loading ─────────────────────────────────────────────


def _load_config(args: argparse.Namespace) -> Config:
    """Load config from YAML (if present), then apply CLI overrides."""
    config_path = args.config

    if config_path:
        config = Config.from_yaml(config_path)
    else:
        # Try default locations (package dir → CWD → ~/.claude/)
        import zotero_paper_report
        pkg_config = (
            Path(zotero_paper_report.__file__).resolve().parent.parent.parent
            / "config.yaml"
        )
        candidates = [
            pkg_config,
            Path("python/config.yaml"),
            Path.home() / ".claude" / "zotero_paper_report_config.yaml",
        ]
        loaded = False
        for candidate in candidates:
            if candidate.exists():
                config = Config.from_yaml(candidate)
                loaded = True
                break
        if not loaded:
            config = Config.default()

    # Resolve auto-detect paths
    config.resolve_paths()

    # CLI overrides
    config.apply_cli_overrides(
        format=args.format,
        save_local=None if not args.no_save_local else False,
        concurrency=args.concurrency,
        skip_existing=None,  # no CLI flag for this yet
        on_missing_pdf=args.on_missing_pdf,
    )

    # Env overrides (lowest priority among overrides, but after defaults)
    config.apply_env_overrides()

    # Re-apply CLI overrides to ensure they beat env vars
    if args.format:
        config.output.format = args.format
    if args.no_save_local:
        config.output.save_local = False
    if args.concurrency is not None:
        config.batch.concurrency = args.concurrency
    if args.on_missing_pdf:
        config.behavior.on_missing_pdf = args.on_missing_pdf

    return config


# ── resume logic ────────────────────────────────────────────────


def _resume(run_id: str) -> None:
    """Resume an interrupted batch run."""
    try:
        old_tracker = ProgressTracker.load(run_id)
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    print(f"恢复运行: {run_id}")
    counts = old_tracker.counts()
    print(f"  总条目: {old_tracker.total_items}")
    print(f"  已完成: {counts.get('done', 0)}")
    print(f"  已跳过: {counts.get('skipped', 0)}")
    print(f"  失败: {counts.get('failed', 0)}")

    pending_keys = [
        k for k, v in old_tracker.items.items()
        if v.status in ("pending", "running")
    ]
    if not pending_keys:
        print("  所有条目已完成，无需恢复。")
        return

    print(f"  待处理: {len(pending_keys)}")

    # Reconstruct config from snapshot
    config = Config.default()
    config.resolve_paths()
    snap = old_tracker.config_snapshot
    if snap:
        config.apply_cli_overrides(
            format=snap.get("format"),
            save_local=snap.get("save_local"),
            concurrency=snap.get("concurrency"),
        )

    # Connect to Zotero and look up pending items
    reader = ZoteroReader(config.zotero.db_path)
    to_generate = []
    for key in pending_keys:
        status = old_tracker.items[key]
        # Fetch item info by key from DB
        item_info = _lookup_item(reader, key)
        if item_info:
            to_generate.append(item_info)
        else:
            print(f"  ⚠ 无法找到条目: {key} — {status.title}")

    if not to_generate:
        print("  无法找到任何待处理条目。")
        return

    # Create new tracker inheriting completed items from old one
    new_run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tracker = ProgressTracker(
        run_id=new_run_id,
        config_snapshot=snap,
    )
    # Pre-populate with completed/skipped items from old run
    for key, status in old_tracker.items.items():
        if status.status in ("done", "skipped"):
            tracker.items[key] = status
    tracker.register_items(
        [i.key for i in to_generate],
        {i.key: i.title for i in to_generate},
    )

    orchestrator = BatchOrchestrator(config, reader, tracker)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                orchestrator.run_with_items(
                    to_generate,
                    run_id=new_run_id,
                )
            )
            loop.run_until_complete(asyncio.sleep(0.1))
        finally:
            loop.close()
    except KeyboardInterrupt:
        print(f"\n\n⚠️  批量生成已中断。")
        print(f"   恢复命令: zotero-paper-report --resume {new_run_id}")
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ 错误: {exc}")
        sys.exit(1)

    if result.get("failed", 0) > 0:
        sys.exit(2)


def _lookup_item(reader: ZoteroReader, key: str):
    """Look up a single item by key in the Zotero database."""
    import sqlite3
    conn = sqlite3.connect(f"file:{reader.db_path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT itemID FROM items WHERE key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        item_id = row[0]
        items = reader.get_items_in_collections([])
    finally:
        conn.close()
    # Use a direct approach: query metadata for this specific item
    return _fetch_item_by_id(reader, item_id, key)


def _fetch_item_by_id(reader: ZoteroReader, item_id: int, key: str):
    """Fetch a single ItemInfo by item ID."""
    import sqlite3
    from .zotero_reader import ItemInfo

    conn = sqlite3.connect(f"file:{reader.db_path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        meta = {}
        rows = conn.execute(
            """
            SELECT f.fieldName, idv.value
            FROM itemData id
            JOIN fieldsCombined f ON id.fieldID = f.fieldID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ? AND f.fieldName IN
                ('title', 'abstractNote', 'date', 'DOI', 'url', 'publicationTitle')
            """, (item_id,)
        ).fetchall()
        meta = {r[0]: r[1] for r in rows}

        authors_rows = conn.execute(
            """
            SELECT c.firstName, c.lastName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ? AND ct.creatorType = 'author'
            ORDER BY ic.orderIndex
            """, (item_id,)
        ).fetchall()
        names = []
        for ar in authors_rows:
            first, last = ar[0] or "", ar[1] or ""
            if first and last:
                names.append(f"{last}, {first}")
            elif last:
                names.append(last)
        authors_str = "; ".join(names)

        # Check PDF
        pdf_row = conn.execute(
            "SELECT path FROM itemAttachments WHERE parentItemID = ? AND contentType = 'application/pdf' LIMIT 1",
            (item_id,)
        ).fetchone()
        has_pdf = pdf_row is not None

        # Check report
        report_row = conn.execute(
            """
            SELECT 1 FROM itemNotes n
            JOIN itemTags it ON n.itemID = it.itemID
            JOIN tags t ON it.tagID = t.tagID
            WHERE n.parentItemID = ? AND t.name = '文献报告' LIMIT 1
            """, (item_id,)
        ).fetchone()
        has_report = report_row is not None

        return ItemInfo(
            item_id=item_id,
            key=key,
            title=meta.get("title", "(无标题)"),
            authors=authors_str,
            year=meta.get("date", ""),
            abstract=meta.get("abstractNote", ""),
            doi=meta.get("DOI", ""),
            url=meta.get("url", ""),
            publication_title=meta.get("publicationTitle", ""),
            has_pdf=has_pdf,
            pdf_path=pdf_row[0] if pdf_row else None,
            has_report=has_report,
        )
    finally:
        conn.close()
