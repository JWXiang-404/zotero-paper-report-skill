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

- 一条命令完成全部流程：只需提供论文标题
- PDF 不可用时自动回退到基于摘要的报告模式
- 支持 HTML / Markdown 两种输出格式，Zotero 笔记标题正确显示
- 报告中标有原文图表/公式引用标注（`[参考图N]`、`[参考公式(N)]`）
- 内置处理扫描件 PDF、缺失附件、搜索歧义等异常路径

## 依赖

| 依赖 | 安装方式 |
|------|---------|
| **Claude Code** | [官方文档](https://docs.anthropic.com/en/docs/claude-code) |
| **Zotero MCP 服务** | 参考 [zotero-mcp 安装指南](https://github.com/cookjohn/zotero-mcp/blob/main/README-zh.md) |
| **claude-scientific-writer 插件** | 通过 [Claude Code 插件方式安装](https://github.com/K-Dense-AI/claude-scientific-writer#-use-as-a-claude-code-plugin-recommended) |
| **Python PDF 库** | `pip install pypdf pdfplumber`（用于 PDF 提取的回退方案） |

`pdf` skill（来自 [anthropics/skills](https://github.com/anthropics/skills)）已内置在本仓库中，由安装脚本自动部署。

## 安装

### macOS & Linux

```bash
# 1. 克隆仓库（含子模块）
git clone --recurse-submodules https://github.com/<your-username>/zotero-paper-report-skill.git
cd zotero-paper-report-skill

# 2. 一键安装
./install.sh
```

安装脚本会：
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

## 许可证

MIT — 详见 [LICENSE](./LICENSE)。

## 致谢

- [zotero-mcp](https://github.com/cookjohn/zotero-mcp) — Zotero MCP 服务，作者 [cookjohn](https://github.com/cookjohn)
- [claude-scientific-writer](https://github.com/K-Dense-AI/claude-scientific-writer) — 科学写作插件，K-Dense Inc.
- [anthropics/skills](https://github.com/anthropics/skills) — PDF 处理 skill
