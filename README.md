# zotero-paper-report-skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[→ 中文文档](./README_zh.md)

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that automatically generates structured Chinese literature reports from papers in your [Zotero](https://www.zotero.org/) library and saves them as Zotero notes.

## Overview

This skill automates the entire literature reporting workflow:

1. **Search** your Zotero library for a paper by title
2. **Extract** the full text from the PDF (with fallback to abstract-only mode)
3. **Generate** a comprehensive Chinese literature report covering overview, innovations, related work, methodology, experiments, and conclusions
4. **Save** the report as a Zotero child note (and optionally as a local HTML/Markdown file)

### Key Features

- One-command workflow: just provide a paper title
- Fallback to abstract-based reporting when PDF is unavailable
- Choice of HTML or Markdown output with automatic Zotero note formatting
- Cross-references to original paper figures, tables, and equations (`[参考图N]`)
- Built-in handling for scanned PDFs, missing attachments, and ambiguous search results

## Dependencies

| Dependency | How to Install |
|------------|---------------|
| **Claude Code** | [Official docs](https://docs.anthropic.com/en/docs/claude-code) |
| **Zotero MCP server** | Follow the [zotero-mcp install guide](https://github.com/cookjohn/zotero-mcp/blob/main/README-zh.md) (Chinese) |
| **claude-scientific-writer plugin** | Install as a [Claude Code plugin](https://github.com/K-Dense-AI/claude-scientific-writer#-use-as-a-claude-code-plugin-recommended) |
| **Python PDF libraries** | `pip install pypdf pdfplumber` (used as fallback for PDF extraction) |

The `pdf` skill (from [anthropics/skills](https://github.com/anthropics/skills)) is vendored in this repository and installed automatically.

## Installation

### macOS & Linux

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/JWXiang-404/zotero-paper-report-skill.git
cd zotero-paper-report-skill

# 2. Install
./install.sh
```

The installer will:
- Check that Claude Code, npm, and all dependencies are available
- Copy the skills to `~/.claude/skills/`
- Print helpful links for any missing dependencies

### Options

```bash
./install.sh --agent claude     # Install for Claude Code (default)
./install.sh --agent opencode   # Reserved for future OpenCode support
./install.sh --help             # Show help
```

## Usage

In Claude Code, invoke the skill with:

```
/zotero-paper-report 帮我为标题包含"ABC"的论文生成文献报告
```

Or describe your need in natural language — the skill triggers automatically when you mention generating a literature report from a Zotero paper.

### What happens next

1. The skill searches your Zotero library and confirms the match
2. It extracts the PDF content (or falls back to the abstract)
3. You choose the output format (HTML or Markdown) and whether to save a local copy
4. A structured report is generated and written to the paper's Zotero notes

### Example output structure

```
文献报告：Paper Title
├── 一、文章概述
├── 二、核心创新点
├── 三、相关工作及存在的问题
├── 四、研究方法详述
├── 五、实验效果
├── 六、总结与展望
└── 关键术语对照
```

## License

MIT — see [LICENSE](./LICENSE) for details.

## Acknowledgements

- [zotero-mcp](https://github.com/cookjohn/zotero-mcp) — Zotero MCP server by [cookjohn](https://github.com/cookjohn)
- [claude-scientific-writer](https://github.com/K-Dense-AI/claude-scientific-writer) — Scientific writing plugin by K-Dense Inc.
- [anthropics/skills](https://github.com/anthropics/skills) — PDF processing skill
