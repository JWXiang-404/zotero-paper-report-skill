"""Subprocess management for individual Claude Code paper-report runs.

Each paper is processed by an independent ``claude -p`` OS process.
Process exit = 100% context cleanup (no shared state between papers).
Output is written to a per-subagent log file; deleted on success, kept on failure.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config


# ── data types ──────────────────────────────────────────────────


@dataclass
class SubagentResult:
    item_key: str
    title: str
    success: bool
    note_key: str | None = None
    error: str | None = None
    duration_sec: float = 0.0
    retries: int = 0
    log_path: str | None = None


# ── prompt builder ──────────────────────────────────────────────


def build_prompt(
    item_key: str,
    title: str,
    authors: str,
    year: str,
    config: "Config",
) -> str:
    """Build the prompt template for a single-paper subprocess."""
    fmt = config.output.format
    save_local_str = "true" if config.output.save_local else "false"

    return f"""使用 zotero-paper-report skill 为以下论文生成中文文献报告：

【论文信息】
- Zotero Item Key: {item_key}
- 论文标题: {title}
- 作者: {authors}
- 年份: {year}

【输出配置】
- 输出格式: {fmt} (html 或 markdown)
- 保存本地文件: {save_local_str} (true 或 false)

【模式说明】
这是批量生成模式。请遵循以下规则：
1. 使用 get_item_details(itemKey="{item_key}", mode="complete") 直接获取论文详情
   不需要 search_library 搜索
2. 跳过 Phase 3 的格式确认 (AskUserQuestion)，直接使用以上配置
3. 按 Phase 4 的模板结构生成完整报告
4. 按 Phase 5 的规范写入 Zotero 笔记并保存本地文件（如适用）
5. 报告写入完成后，输出一行: BATCH_REPORT_DONE: {item_key} note_key=<note_key>

不要询问任何确认问题。"""


# ── log directory ────────────────────────────────────────────────

def _ensure_log_dir() -> Path:
    d = Path.home() / ".claude" / "zotero-paper-report" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── subprocess runner ────────────────────────────────────────────


async def run_subagent(
    item_key: str,
    title: str,
    authors: str,
    year: str,
    config: "Config",
) -> SubagentResult:
    """Run a single claude -p subprocess for one paper.

    Returns a SubagentResult with success/failure info.
    Handles timeout and retry per config.
    Streams real-time output to stderr AND a per-subagent log file.
    On success the log file is deleted; on failure it is kept.
    """
    prompt = build_prompt(item_key, title, authors, year, config)
    claude_bin = os.environ.get("CLAUDE_BIN", "claude")
    timeout = config.behavior.subagent_timeout
    max_retries = config.behavior.max_retries if config.behavior.on_subagent_error == "retry" else 0

    last_error: str | None = None
    total_retries = 0
    short_title = _shorten(title, 40)
    log_dir = _ensure_log_dir()

    for attempt in range(max_retries + 1):
        start = time.monotonic()
        log_path = log_dir / f"{item_key}_{int(start)}.log"

        try:
            proc = await asyncio.create_subprocess_exec(
                claude_bin,
                "-p",
                prompt,
                "--print",
                "--output-format",
                "text",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream output line by line to both stderr and log file
            stdout_lines: list[str] = []
            log_fh = open(log_path, "w", encoding="utf-8")

            try:
                while True:
                    line_bytes = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=timeout
                    )
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace")
                    stdout_lines.append(line)
                    sys.stderr.write(f"  [{short_title}] {line}")
                    sys.stderr.flush()
                    log_fh.write(line)
                    log_fh.flush()

                await proc.wait()
            except asyncio.TimeoutError:
                log_fh.write(f"\n--- TIMEOUT after {timeout}s ---\n")
                log_fh.close()
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    await asyncio.sleep(5)
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                sys.stderr.write(f"  [{short_title}] ⏱ timeout after {timeout}s\n")
                sys.stderr.flush()
                duration = time.monotonic() - start
                last_error = f"timeout after {timeout}s"
                total_retries = attempt
                continue
            finally:
                if not log_fh.closed:
                    log_fh.close()

            duration = time.monotonic() - start
            stdout = "".join(stdout_lines)

            if proc.returncode != 0:
                last_error = f"claude exited with code {proc.returncode}\n  Log: {log_path}"
                total_retries = attempt
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
                continue

            # Success — delete log file
            note_key = _parse_result(stdout)
            try:
                os.remove(log_path)
            except OSError:
                pass

            return SubagentResult(
                item_key=item_key,
                title=title,
                success=True,
                note_key=note_key,
                duration_sec=duration,
                retries=attempt,
            )

        except FileNotFoundError:
            return SubagentResult(
                item_key=item_key,
                title=title,
                success=False,
                error=f"claude CLI not found. Is Claude Code installed? Tried: {claude_bin}",
                duration_sec=time.monotonic() - start,
                retries=attempt,
            )
        except Exception as exc:
            last_error = f"unexpected error: {exc}"
            total_retries = attempt
            if attempt < max_retries:
                await asyncio.sleep(2 ** (attempt + 1))

    # All attempts exhausted — log path points to last failed attempt
    return SubagentResult(
        item_key=item_key,
        title=title,
        success=False,
        error=last_error or "unknown error",
        duration_sec=0,
        retries=total_retries,
        log_path=str(log_path),
    )


def _parse_result(stdout: str) -> str | None:
    """Extract note_key from the BATCH_REPORT_DONE marker line."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("BATCH_REPORT_DONE:"):
            parts = line.split()
            for part in parts:
                if part.startswith("note_key="):
                    return part.split("=", 1)[1]
    return None


def _shorten(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
