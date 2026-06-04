# zotero-paper-report-skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[→ English Docs](./README.md)

一个 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill，能从你的 [Zotero](https://www.zotero.org/) 文献库中自动生成结构化的中文文献报告，并保存为 Zotero 笔记。

## 概述

本 skill 自动化了完整的文献报告工作流：

1. **搜索**：根据论文标题在 Zotero 中查找对应条目
2. **提取**：从 PDF 中提取全文内容（支持回退到摘要模式）
3. **生成**：生成涵盖概述、创新点、相关工作、方法、实验、结论的全面中文文献报告
4. **保存**：将报告写入 Zotero 子笔记（可选同时保存本地 HTML/Markdown 文件）

### 核心特性

- **单篇模式**：一条命令完成全部流程 — 只需提供论文标题
- **批量模式**：一键为整个 Zotero 分类生成报告，支持嵌套子分类递归遍历和可配置并发生成
- PDF 不可用时自动回退到基于摘要的报告模式
- 支持 HTML / Markdown 两种输出格式，Zotero 笔记标题正确显示
- 报告中标有原文图表/公式引用标注（`[参考图N]`、`[参考公式(N)]`）
- 内置处理扫描件 PDF、缺失附件、搜索歧义等异常路径
- 断点续传：中断的批量任务可恢复，不重复处理已完成条目

## 依赖

| 依赖 | 安装方式 |
|------|---------|
| **Claude Code** | [官方文档](https://docs.anthropic.com/en/docs/claude-code) |
| **Zotero MCP 服务** | 参考 [zotero-mcp 安装指南](https://github.com/cookjohn/zotero-mcp/blob/main/README-zh.md) |
| **claude-scientific-writer 插件** | 通过 [Claude Code 插件方式安装](https://github.com/K-Dense-AI/claude-scientific-writer#-use-as-a-claude-code-plugin-recommended) |
| **Python PDF 库** | `pip install pypdf pdfplumber`（用于 PDF 提取的回退方案） |

`pdf` skill（来自 [anthropics/skills](https://github.com/anthropics/skills)）已内置在本仓库中，由安装脚本自动部署。

## 安装

> **一键安装脚本** — 自动创建隔离 Python 环境、安装全部依赖、配置 MCP 服务、部署 skills。

### 快速开始

```bash
# 1. 克隆仓库（含子模块）
git clone --recurse-submodules https://github.com/JWXiang-404/zotero-paper-report-skill.git
cd zotero-paper-report-skill

# 2. 一键安装
./install.sh
```

安装脚本会：
- 检查前置依赖（Claude Code、npm、Python）
- 自动创建隔离虚拟环境（默认 uv）
- 安装 Python 依赖（`pyyaml`、`pypdf`、`pdfplumber`）
- 安装 `zotero-paper-report` CLI 命令行工具
- 自动探测 Zotero 本地 API 端口，配置 `zotero-mcp` MCP 服务
- 克隆并安装 `claude-scientific-writer` skill
- 将所有 skill 文件复制到 `~/.claude/skills/`

### 可选参数

```bash
./install.sh --env uv              # 使用 uv venv（默认推荐）
./install.sh --env conda           # 使用 conda/miniconda
./install.sh --env venv            # 使用 python3 -m venv
./install.sh --skill-only          # 仅安装 skill 文件，跳过 Python 环境
./install.sh --zotero-port 23120   # 手动指定 Zotero 端口号
./install.sh --env-name "zpr-prod" # 自定义虚拟环境名称
./install.sh --help                # 查看所有选项
```
- 检查 Claude Code、npm 及所有依赖是否就绪
- 将 skill 复制到 `~/.claude/skills/`
- 对缺失的依赖打印安装指引链接

### 选项

```bash
./install.sh --agent claude     # 为 Claude Code 安装（默认）
./install.sh --agent opencode   # 预留：未来 OpenCode 支持
./install.sh --help             # 查看帮助
```

## 使用方法

在 Claude Code 中，通过斜杠命令调用：

```
/zotero-paper-report 帮我为标题包含"ABC"的论文生成文献报告
```

也可以用自然语言描述需求——当你提到为 Zotero 中的论文生成文献报告时，skill 会自动触发。

### 执行流程

1. 搜索你的 Zotero 文献库并确认匹配的论文
2. 提取 PDF 全文（如不可用则回退到摘要）
3. 你选择输出格式（HTML 或 Markdown）以及是否保存本地副本
4. 生成结构化报告并写入该论文的 Zotero 笔记

### 报告结构示例

```
文献报告：论文标题
├── 一、文章概述
├── 二、核心创新点
├── 三、相关工作及存在的问题
├── 四、研究方法详述
├── 五、实验效果
├── 六、总结与展望
└── 关键术语对照
```

## 批量生成

一键为整个 Zotero 分类（含嵌套子分类）的所有论文生成文献报告。

### 方式一：CLI 命令行

```bash
# 基本用法：为某分类下所有论文生成报告（始终递归子分类）
zotero-paper-report --collection "编译优化"

# 指定并发度
zotero-paper-report --collection "编译优化" --concurrency 5

# 预览模式（不实际生成）
zotero-paper-report --collection "编译优化" --preview-only

# 恢复中断的任务
zotero-paper-report --resume <run_id>

# 为所有顶级分类生成
zotero-paper-report --all
```

### 方式二：Skill 调用（在 Claude Code 中）

直接用自然语言请求，skill 会自动识别批量意图：

```
/zotero-paper-report 给"编译优化"分类下的所有论文生成文献报告
```

Skill 会：
1. 自动检测批量请求
2. 提取分类名和选项参数
3. 向你确认后执行
4. 论文较多时后台运行，完成后汇报汇总结果

### 全局配置

配置文件 `python/config.yaml`（可直接编辑）：

```yaml
output:
  format: html              # html | markdown
  save_local: true

batch:
  concurrency: 3            # 最大并行 Claude Code 实例数
  skip_existing: true       # 跳过已有报告的论文

behavior:
  on_missing_pdf: skip      # skip | abstract
  subagent_timeout: 600     # 每篇论文超时时间（秒）
```

所有配置均支持 CLI 参数覆盖或环境变量覆盖（如 `ZOTERO_BATCH_FORMAT`、`ZOTERO_BATCH_CONCURRENCY` 等）。

## 许可证

MIT — 详见 [LICENSE](./LICENSE)。

## 致谢

- [zotero-mcp](https://github.com/cookjohn/zotero-mcp) — Zotero MCP 服务，作者 [cookjohn](https://github.com/cookjohn)
- [claude-scientific-writer](https://github.com/K-Dense-AI/claude-scientific-writer) — 科学写作插件，K-Dense Inc.
- [anthropics/skills](https://github.com/anthropics/skills) — PDF 处理 skill
