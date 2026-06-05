"""Subprocess management for individual Claude Code paper-report runs.

Each paper is processed by an independent ``claude -p`` OS process.
Process exit = 100% context cleanup (no shared state between papers).
Uses --output-format stream-json for real-time token tracking.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
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
    input_tokens: int = 0
    output_tokens: int = 0


# ── prompt builder ──────────────────────────────────────────────


def build_prompt(
    item_key: str,
    title: str,
    authors: str,
    year: str,
    config: "Config",
) -> str:
    """Build the prompt template for a single-paper subprocess."""
    save_desc = "保存本地文件" if config.output.save_local else "不保存本地文件"
    return f"""为以下论文生成中文文献报告：

Zotero Item Key: {item_key}
论文标题: {title}
作者: {authors}
年份: {year}
输出格式: {config.output.format}，{save_desc}

不要询问确认问题，使用以上配置直接生成。
完成后输出: BATCH_REPORT_DONE: {item_key} note_key=<note_key>"""


# ── helpers ─────────────────────────────────────────────────────


def _ensure_log_dir() -> Path:
    d = Path.home() / ".claude" / "zotero-paper-report" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def _shorten(text: str, max_len: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


# ── subprocess runner ────────────────────────────────────────────


async def run_subagent(
    item_key: str,
    title: str,
    authors: str,
    year: str,
    config: "Config",
) -> SubagentResult:
    """Run a single claude -p subprocess for one paper.

    Uses --output-format stream-json for real-time token tracking.
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
                "-p", prompt,
                "--print",
                "--output-format", "stream-json",
                "--verbose",
                "--permission-mode", "bypassPermissions",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            text_parts: list[str] = []
            input_tokens = 0
            output_tokens = 0
            log_fh = open(log_path, "w", encoding="utf-8")
            last_token_report = time.monotonic()

            # Use chunk-based reading to avoid 64KB line limit of readline()
            buf = b""
            try:
                while True:
                    chunk = await asyncio.wait_for(
                        proc.stdout.read(256 * 1024), timeout=timeout
                    )
                    if not chunk:
                        break
                    buf += chunk
                    # Process complete lines from buffer
                    while b"\n" in buf:
                        idx = buf.index(b"\n")
                        line_bytes = buf[:idx]
                        buf = buf[idx + 1:]
                        raw_line = line_bytes.decode("utf-8", errors="replace")
                        line = raw_line.strip()
                        log_fh.write(raw_line + "\n")

                        if not line:
                            continue
                        _process_stream_line(
                            line, raw_line, text_parts, short_title,
                        )
                        # Track token counts from JSON events
                        itok, otok = _parse_token_line(line)
                        if itok > input_tokens:
                            input_tokens = itok
                        if otok > output_tokens:
                            output_tokens = otok
                        if input_tokens > 0:
                            now = time.monotonic()
                            if now - last_token_report > 5:
                                sys.stderr.write(
                                    f"  [{short_title}] 📊 "
                                    f"in:{_fmt_tokens(input_tokens)} "
                                    f"out:{_fmt_tokens(output_tokens)}\n"
                                )
                                sys.stderr.flush()
                                last_token_report = now
                # Process remaining buffer
                if buf:
                    raw_line = buf.decode("utf-8", errors="replace").strip()
                    log_fh.write(raw_line + "\n")
                    if raw_line:
                        _process_stream_line(
                            raw_line, raw_line, text_parts, short_title,
                        )

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
                last_error = f"timeout after {timeout}s"
                total_retries = attempt
                continue
            finally:
                if not log_fh.closed:
                    log_fh.close()

            duration = time.monotonic() - start
            full_text = "".join(text_parts)

            if proc.returncode != 0:
                last_error = (
                    f"claude exited with code {proc.returncode}"
                    f"\n  Log: {log_path}"
                )
                total_retries = attempt
                if attempt < max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
                continue

            # Success
            note_key = _parse_result(full_text)
            try:
                os.remove(log_path)
            except OSError:
                pass
            # Force transport cleanup to avoid "Event loop is closed" warnings
            try:
                proc._transport.close()
            except Exception:
                pass

            return SubagentResult(
                item_key=item_key,
                title=title,
                success=True,
                note_key=note_key,
                duration_sec=duration,
                retries=attempt,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
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

    return SubagentResult(
        item_key=item_key,
        title=title,
        success=False,
        error=last_error or "unknown error",
        duration_sec=0,
        retries=total_retries,
        log_path=str(log_path),
    )


# ── stream-json helpers ──────────────────────────────────────────


def _process_stream_line(
    line: str, raw_line: str, text_parts: list[str], prefix: str,
) -> None:
    """Parse one line from stream-json output. Writes text to stderr."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        text_parts.append(raw_line)
        sys.stderr.write(f"  [{prefix}] {raw_line}\n")
        sys.stderr.flush()
        return

    ev_type = event.get("type", "")
    if ev_type == "assistant":
        msg = event.get("message", {})
        for block in msg.get("content", []):
            if block.get("type") == "text":
                t = block.get("text", "")
                if t:
                    text_parts.append(t)
                    sys.stderr.write(f"  [{prefix}] {t}")
                    sys.stderr.flush()


def _parse_token_line(line: str) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from a stream-json line."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return 0, 0

    usage = event.get("message", {}).get("usage") or event.get("usage", {})
    return usage.get("input_tokens", 0), usage.get("output_tokens", 0)


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
