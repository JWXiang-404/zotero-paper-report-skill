---
name: zotero-paper-report
description: >-
  从 Zotero 中的论文自动生成中文文献报告，写入 Zotero 笔记并可选择保存本地文件。
  当用户提供论文标题并要求生成文献报告、论文总结、阅读笔记、文献综述时触发，
  尤其是涉及 Zotero 文献库、论文解读、文献整理等场景。
  同时也适用于用户想对 Zotero 中已有论文生成结构化文献分析报告的情况。
  支持 PDF 无法提取时回退到摘要模式，以及多种异常路径的优雅处理。
  支持按 Zotero 分类一键批量生成（通过内部调用 zotero-paper-report CLI），支持嵌套子分类递归遍历和并发生成。
---

# Zotero Paper Report

## 概述

本 skill 自动化以下工作流程：

1. 根据论文标题在 Zotero 中搜索对应条目
2. 提取论文 PDF 全文内容
3. 生成结构化的中文文献报告（Markdown 或 HTML）
4. 将报告写入 Zotero 笔记（可选同时保存本地文件）

## 触发条件

- 用户提供论文标题并要求生成"文献报告"、"论文总结"、"阅读笔记"
- 用户想对 Zotero 中的论文进行结构化分析
- 用户说"帮我分析这篇论文"、"写个文献报告"等

**重要**: 本 skill 需要 zotero-mcp 工具可用。如果 zotero-mcp 未连接，告知用户先配置 Zotero MCP 服务。

> **工具使用参考**: `references/zotero-tools-guide.md` 包含了本 skill 所用 Zotero MCP 工具的详细参数说明、返回值结构、常见调用模式和错误场景速查。在执行 Phase 1/2/5 时，遇到不确定的工具行为请查阅该文件。

---

## Phase 0: 意图识别与路由

在进入具体流程之前，**首先分析用户请求，判断是「单篇论文」还是「批量生成」**。

### 0.1 检测用户意图

分析用户输入中的关键词：

**批量生成的关键词（任一命中即判定为批量）**：
- 分类名/路径: "XX分类下的"、"XX目录下的"、"XX collection"
- 批量语义: "所有论文"、"全部论文"、"所有条目"、"批量生成"、"一键生成"
- 范围语义: "整个分类"、"全部分类"、"遍历"、"全部生成"
- 嵌套语义: "包括子分类"、"递归"、"子目录也"

**单篇论文的关键词（保持现有流程）**：
- 具体标题: "标题包含XXX"、"标题为XXX"、"这篇论文"
- "帮我分析这篇"、"写个文献报告"等

**模糊情况（无法确定）**：
- 使用 AskUserQuestion 让用户选择是「单篇生成」还是「批量生成」

### 0.2 批量模式：提取参数并执行

如果检测到批量意图，从用户自然语言中提取参数：

- **分类名**: 引号内的文本、"XX分类"、"XX目录"
- **格式偏好**: "用Markdown"、"HTML格式" → 使用 `--format`
- **并发度**: "同时跑3个"、"并发5个" → 使用 `--concurrency`
- **缺失PDF策略**: "没有PDF的跳过"、"缺少PDF就用摘要" → 使用 `--on-missing-pdf`

**执行步骤**：

1. **确认参数**: 向用户展示解析到的参数（分类名、格式、并发度），确认后继续。

2. **调用 zotero-paper-report CLI**: 通过 Bash 工具调用 Python 批量引擎（始终递归遍历子分类）：
   ```bash
   python -m zotero_paper_report \
     --collection "分类名" \
     --format html \
     --concurrency 3
   ```

3. **监控执行**: 
   - 如果论文数量 ≤ 5 篇，前台等待 zotero-paper-report 完成
   - 如果论文数量 > 5 篇，使用 `Bash(run_in_background=true)` 后台执行，
     告知用户可以通过 `zotero-paper-report --resume <run_id>` 查看进度

4. **汇报结果**: 程序完成后，读取 `~/.claude/zotero-paper-report/{run_id}.json`，
   向用户展示汇总结果（成功/失败/跳过数量）。

### 0.3 单篇模式

如果检测到单篇请求，直接进入 Phase 1（搜索 Zotero），保持现有流程不变。

---

## Phase 1: 搜索 Zotero

### 1.0 批量模式 vs 搜索模式

**批量模式（从 Phase 0 路由过来）**：
- 已知 item key，跳过 search_library
- 直接使用 `get_item_details(itemKey, mode="complete")` 进入 Phase 2
- 提示中会明确包含 "BATCH_MODE: true" 标识

**搜索模式（单篇论文）**：
- 执行原有的 search_library → 确认匹配流程（见 1.1-1.2）

### 1.1 执行搜索

使用 `mcp__zotero-mcp__search_library` 按标题搜索。如果用户提供了作者名或年份，一并作为辅助筛选条件。

```
search_library(q="<用户提供的标题>", mode="standard")
```

### 1.2 处理搜索结果

**无结果 (E1)**:
```
告知用户: "在 Zotero 中未找到匹配的论文。请检查：
1. 标题拼写是否正确？
2. 论文是否已导入 Zotero？
是否需要我按其他字段（作者、关键词）重新搜索？"

如果用户选择重新搜索，引导用户提供更多信息（作者名、DOI、关键词等）。
```

**单个结果**:
```
确认匹配: "在 Zotero 中找到了: [标题] by [作者] ([年份])
是否继续生成文献报告？"
```

**多个结果 (E2)**:
```
列出所有候选（显示序号、标题、作者、年份），让用户选择。
每个候选显示: "[序号]. [标题] — [作者] ([年份])"

用户回复序号后继续。
```

### 重要: 识别条目类型

`search_library` 返回的结果中，`itemType` 为 `"attachment"` 或标题为 `"Full Text PDF"` 的条目是独立的附件条目（不含元数据）。这种情况需要找到其父条目。

- 如果搜索结果直接返回了元数据完整的条目（有 `creators`、`abstractNote` 等字段），直接使用它
- 如果返回的是 attachment 条目，使用 `get_item_details` 查看其结构来确定父条目

通常情况下，`search_library` 搜索标题会返回有元数据的条目。但如果结果中的 `key` 对应的是附件，记录该 key 并检查 `attachments` 字段来找到父条目。

---

## Phase 2: 提取内容

### 2.1 获取条目详情

使用 `get_item_details(itemKey, mode="complete")` 获取完整信息，包括：
- 附件列表（`attachments`，包含 `key`、`contentType`、`hasFulltext`、`path`）
- 摘要（`abstractNote`）
- 元数据（标题、作者、年份、DOI、URL）

### 2.2 三级内容获取策略

#### 第一级: 使用 get_content（首选）

如果条目有 PDF 附件且 `hasFulltext` 为 `true`，使用 `get_content(itemKey=<pdf-key>)` 提取全文。

#### 第二级: 直接提取 PDF 文件（回退）

如果 `hasFulltext` 为 `false` 或 `get_content` 返回空/失败 (E7)：
1. 从 `get_item_details` 中获取 PDF 的文件系统路径 (`attachments[].path`)
2. 使用项目虚拟环境中的 pypdf 直接提取:

```bash
source /Users/xiangjiawei/Zotero/.venv/bin/activate && python3 -c "
from pypdf import PdfReader
reader = PdfReader('<PDF路径>')
for page in reader.pages:
    text = page.extract_text()
    if text:
        print(text)
"
```

#### 第三级: 摘要回退模式（最终回退）

如果以上两步均失败，或条目根本没有 PDF 附件:

**无附件 (E5)**:
```
告知用户: "该条目没有附件。是否基于摘要和元数据生成简化报告？
（报告将标注: ⚠️ 基于摘要生成，未读取全文）"
```

**附件非 PDF (E6)**:
```
告知用户: "该条目的附件不是 PDF（类型: [contentType]）。
是否基于摘要和元数据生成简化报告？"
```

**摘要回退模式的报告要求**:
- 在报告标题下添加醒目提示: `> ⚠️ 本报告基于论文摘要和元数据生成，未读取全文。内容可能不完整。`
- 基于 `abstractNote` 提取所有可用信息
- 对于无法从摘要推断的章节（如"研究方法详述"、"实验效果"），注明"无法从摘要中获取详细信息"

### 2.3 内容质量检查

提取全文后，进行质量检查：

**内容过短 (< 500 字符) (E8)**:
```
警告: "PDF 提取的内容过短（仅 <N> 字符），可能是扫描件（无 OCR 层）。
是否继续？报告质量可能受影响。"
如果用户选择继续，结合摘要补充信息。
```

**内容可能乱码 (E9)**:
如果提取结果包含大量不可打印字符或比例异常的乱码：
```
警告: "提取的内容可能存在乱码。将继续生成报告，但建议人工校对。"
在报告中标注"低置信度"。
```

---

## Phase 3: 确认输出格式

### 3.0 批量模式检测

如果用户请求中包含批量模式标识（Phase 0 判断为批量），或子进程 prompt 中包含
"BATCH_MODE: true"，则**跳过本节的所有 AskUserQuestion 调用**，直接使用以下预配置：

- 格式: 来自批量配置（默认 html）
- 保存本地: 来自批量配置（默认 true）
- 不询问任何确认问题，直接进入 Phase 4

**正常交互模式（单篇论文）**：

使用 `AskUserQuestion` 一次性询问用户两个偏好：

```
Q1: 输出格式?
  选项: Markdown (推荐) | HTML
  Markdown 适合导入笔记软件，HTML 适合直接浏览。
  默认: Markdown

Q2: 是否同时保存本地文件?
  选项: 是 (保存到 PDF 同目录) | 否 (仅写入 Zotero 笔记)
```

**注意**: 只问一次，合并为一个 AskUserQuestion 调用，包含两个问题。

---

## Phase 4: 生成报告

### 4.1 主要方式: 使用 scientific-writing skill

调用 scientific-writing skill 生成中文文献报告。遵循两阶段流程：

**Stage 1: 创建大纲**
- 从全文/摘要中提取关键信息
- 按报告模板结构组织要点
- 使用 bullet points 作为临时大纲

**Stage 2: 展开为完整段落**
- 将大纲中的 bullet points 转化为完整段落
- 添加过渡句，确保行文流畅
- 禁止在最终报告中保留 bullet points（除"术语对照"表格等少数例外）

### 4.2 报告结构模板

```markdown
# 文献报告：[论文标题]

> **作者**: [作者列表]
> **机构**: [机构（如有）]
> **发表时间**: [年份]
> **来源**: [DOI/arXiv/期刊]
> **[摘要模式标注]**: ⚠️ 本报告基于论文摘要生成，未读取全文（仅在摘要模式下添加）

---

## 一、文章概述
[用 2-3 个自然段概述论文的研究背景、核心问题和主要贡献]

## 二、核心创新点
[列出 3-5 个核心创新点，每个用完整段落阐述]

## 三、相关工作及存在的问题
[总结相关研究，指出各自的局限性]

## 四、研究方法详述
[详细描述论文提出的方法、算法、架构]

## 五、实验效果
[总结实验设置、baseline 对比、关键性能数据]

## 六、总结与展望
[研究贡献总结 + 未来工作方向]

---

## 关键术语对照

| 英文 | 中文 |
|------|------|
| [term1] | [翻译1] |
| [term2] | [翻译2] |
```

### 4.2.1 引用原文图表和算法

**CRITICAL**: 在报告中描述方法架构、实验数据、公式推导等内容时，**必须**标注对原文图表/算法/公式的引用。这让读者能快速定位原文对应内容进行交叉验证。

引用格式：
- 中文: `[参考图N]`、`[参考表N]`、`[参考算法N]`、`[参考公式(N)]`
- 英文: `[See Figure N]`、`[See Table N]`

正确示例：
- "EquiformerV3 的整体架构如图 1 所示，包含等变合并层归一化和 SwiGLU-S2 激活 [参考图1]"
- "消融实验结果汇总于表 1，各项改进逐步提升性能 [参考表1]"
- "SwiGLU-S2 激活函数的核心公式为 [参考公式(7)]"
- "S2 激活、gate 激活与 SwiGLU-S2 激活的对比见图 3 [参考图3]"
- "反向传播算法如 Algorithm 3 所述 [参考算法3]"

关键原则：
- 引用自然地融入段落语境中，而非孤立括号
- **每次首次提到**某个具体的图/表/算法/公式时都要标注
- 不要泛泛地说"如图表所示"——始终带上编号
- 如果 PDF 提取的内容中无法确定图表编号，标注 `[参考原文对应图表]`

### 4.3 Fallback: scientific-writing skill 未触发时

如果 scientific-writing skill 未正确触发，**不要停止**。直接按以下原则自行生成报告：

- 遵循第 4.2 节的模板结构
- 使用完整段落而非 bullet points
- 保持学术专业性
- 所有关键数据（加速比、模型名称、baseline 等）必须从原文中准确引用
- **标注对原文图表/算法/公式的引用**: 遵循 Phase 4.2.1 的引用格式（`[参考图N]`、`[参考表N]` 等）
- 生成中文报告，但专业术语保留英文并附带中文翻译

### 4.4 内容超长处理 (E11)

如果 PDF 提取内容超过 100,000 字符：
- 优先保留：方法、实验、创新点章节的详细信息
- 适当精简：相关工作、背景介绍
- 确保方法章节尽可能详尽

---

## Phase 5: 保存与验证

### 5.1 确定目标条目

**关键 (E14)**: 确认 `parentKey` 是有元数据的父条目，而非 attachment 条目。

从 Phase 1 搜索结果中获取正确的条目 key。如果搜索结果返回的是有 `creators`、`abstractNote` 等元数据的条目，直接使用其 key。如果返回的是 attachment 条目，需要找到其父条目。

### 5.2 写入 Zotero 笔记

**HTML 格式的 Zotero 笔记规范（重要）**:

当用户选择 HTML 格式时，Zotero 笔记和本地文件必须使用**不同的 HTML 结构**。原因：Zotero 取 HTML 的第一个文本节点作为笔记列表中显示的标题。如果内容以 `<style>` 或 `<html>` 标签开头，标题将显示为 CSS 代码。

**Zotero 笔记**（传给 `write_note` 的 `content` 参数）:
- ❌ 不要包含 `<html>`, `<head>`, `<body>`, `<style>` 标签
- ✅ 直接从 `<h1>文献报告：[标题]</h1>` 开始
- ✅ 所有样式使用内联 `style` 属性（如 `<h1 style="border-bottom: 3px solid #2563eb; ...">`）
- ✅ Zotero 会将第一个 `<h1>` 的文本用作笔记列表中的标题

**本地 HTML 文件**（传给 `Write` 工具）:
- ✅ 使用完整 HTML5 文档（`<!DOCTYPE html>` 到 `</html>`）
- ✅ 在 `<head>` 中嵌入 `<style>` 块定义样式
- ✅ 适合浏览器独立打开，视觉效果更好

**Markdown 格式**: 直接传递 Markdown 内容，Zotero 会自动转换为 HTML，无标题问题。

```typescript
mcp__zotero-mcp__write_note({
  action: "create",
  parentKey: "<父条目key>",
  content: "<报告内容 — 如果是HTML，直接从<h1>开始，无<html>/<head>/<style>标签>",
  tags: ["文献报告"]
})
```

**write_note 失败 (E13)**:
```
告知用户: "写入 Zotero 笔记失败: [错误信息]。
报告已保存到本地文件: [文件路径]（如果用户选择了保存本地文件）
你可以手动将此报告复制到 Zotero 笔记中。"
```
不要静默失败，确保用户知道发生了什么。

**内容过长 (E15)**:
如果因内容过长导致写入失败：
- 先尝试写入完整内容
- 如果失败，考虑精简"相关工作"和"关键术语"章节后重试
- 告知用户做了哪些简化

### 5.3 保存本地文件（可选）

如果用户在 Phase 3 选择了保存本地文件：

1. 确定保存路径: PDF 所在目录
2. 文件名: `{论文标题截断至50字符} - 文献报告.{md|html}`
3. 如果同名文件已存在，询问是否覆盖
4. 使用 `Write` 工具写入文件

### 5.4 验证

保存后执行验证：

1. **Zotero 笔记**: 使用 `get_item_details(itemKey=<父条目key>)` 确认 `notes` 数组中出现了新笔记，且内容非空
2. **本地文件**（如有）: 确认文件存在且大小 > 0

---

## 异常路径快速索引

| 编号 | 场景 | Phase | 处理 |
|------|------|-------|------|
| E1 | Zotero 搜索无结果 | 1 | 提示用户检查标题或更换搜索方式 |
| E2 | 多个搜索结果 | 1 | 展示候选列表让用户选择 |
| E3 | 搜索结果含 attachment 条目 | 1 | 识别并导航到父条目 |
| E4 | 匹配确认 | 1 | 始终让用户确认匹配的论文 |
| E5 | 条目无附件 | 2 | 询问是否使用摘要回退模式 |
| E6 | 附件非 PDF | 2 | 列出附件类型，提供摘要回退 |
| E7 | PDF 无法提取 | 2 | pypdf 直接提取 → 摘要回退 |
| E8 | 内容过短 | 2 | 警告用户，结合摘要补充 |
| E9 | 内容乱码 | 2 | 警告用户，标注低置信度 |
| E10 | 用户不指定格式 | 3 | 默认 Markdown |
| E11 | 内容超长 | 4 | 优先保留关键章节 |
| E12 | scientific-writing 未触发 | 4 | 使用内置 fallback 指引 |
| E13 | write_note 失败 | 5 | 告知错误，确保本地文件已保存 |
| E14 | parentKey 用错 | 5 | 使用有元数据的父条目 key |
| E15 | 笔记内容过长 | 5 | 精简非核心章节后重试 |

---

## 依赖

### 必需
- **zotero-mcp MCP 工具**: `search_library`, `get_item_details`, `get_content`, `write_note`
  - 详细用法见 `references/zotero-tools-guide.md`
- **scientific-writing skill** (claude-scientific-writer): 报告生成（有 fallback）
- **AskUserQuestion**: Phase 3 格式确认
- **Write**: Phase 5b 本地文件保存

### 可选
- **pypdf / pdfplumber** (项目 .venv): Phase 2 回退 PDF 提取
- **Bash**: 运行 pypdf 提取命令

## References

- `references/zotero-tools-guide.md` — Zotero MCP 工具完整参考：参数、返回值、常见模式、错误场景
