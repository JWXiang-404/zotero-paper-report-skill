# Zotero MCP 工具实用指南

> 本文档为 `zotero-paper-report` skill 提供所需的 Zotero MCP 工具快速参考。
> 所有工具均以 `mcp__zotero-mcp__` 为前缀。

---

## 工具总览

| 工具 | 用途 | 阶段 |
|------|------|------|
| `search_library` | 搜索 Zotero 文献库 | Phase 1 |
| `get_item_details` | 获取条目完整元数据 | Phase 2 |
| `get_content` | 提取 PDF 全文文本 | Phase 2 |
| `write_note` | 写入子笔记到条目 | Phase 5 |

---

## 1. search_library — 搜索文献库

### 关键参数

| 参数 | 说明 |
|------|------|
| `q` | 通用搜索查询（最常用，传论文标题） |
| `title` | 精确标题搜索 |
| `titleOperator` | `"contains"`（默认）/ `"exact"` / `"startsWith"` / `"endsWith"` / `"regex"` |
| `itemType` | 按类型筛选（`"attachment"` 获取独立 PDF） |
| `mode` | `"minimal"`（30条）/ `"preview"`（100条）/ `"standard"`（自适应，推荐）/ `"complete"`（500+） |
| `limit` | 覆盖 mode 的默认数量 |
| `sort` | `"relevance"` / `"date"` / `"title"` / `"year"` |

### 返回值结构（关键字段）

```json
{
  "results": [
    {
      "key": "VFPYB58F",              // ← 条目唯一 ID，后续所有操作的基础
      "title": "论文标题",
      "creators": "作者1, 作者2, ...", // 仅 standard/complete mode
      "date": "2025",
      "itemType": "journalArticle",    // 空字符串 = 未识别类型
      "attachments": [                 // standard/complete mode 包含
        {
          "key": "3K7SPS59",
          "filename": "xxx.pdf",
          "contentType": "application/pdf",
          "linkMode": 1
        }
      ]
    }
  ],
  "pagination": { "total": 1, "hasMore": false }
}
```

### 调用模式

```typescript
// 标准标题搜索（推荐）
search_library(q="efficient sparse kernel generator", mode="standard")

// 精确标题匹配
search_library(title="Efficient Sparse Kernel", titleOperator="contains")

// 搜索独立 PDF 附件（没有父条目的 PDF）
search_library(itemType="attachment", includeAttachments="true")
```

### 注意事项

- `search_library` 搜索的是**用户个人库**，不包括群组库
- 模糊搜索可能返回多个结果，需要让用户确认
- `mode` 决定了返回的字段丰富度：`minimal` 可能不含 `creators` 和 `attachments`
- **推荐始终使用 `mode="standard"`** 以获取足够的元数据

---

## 2. get_item_details — 获取条目详情

### 关键参数

| 参数 | 说明 |
|------|------|
| `itemKey` | **必填**。条目 key（来自 search_library 结果） |
| `mode` | `"minimal"` / `"preview"` / `"standard"` / `"complete"` |

### 返回值结构（关键字段，mode="complete"）

```json
{
  "key": "VFPYB58F",
  "itemType": "journalArticle",       // 空字符串表示未识别
  "title": "论文完整标题",
  "creators": [
    { "firstName": "Vivek", "lastName": "Bharadwaj", "creatorType": "author" }
  ],
  "date": "2025/01/23",
  "publicationTitle": "",
  "DOI": "",
  "url": "https://arxiv.org/abs/2501.13986v4",
  "abstractNote": "Rotation equivariant graph neural networks...",
  "tags": ["openeq"],
  "notes": ["<h1>已有笔记</h1>..."],   // HTML 格式的已有笔记
  "attachments": [
    {
      "key": "3K7SPS59",              // ← 附件 key，用于 get_content 和 write_note
      "linkMode": 1,                  // 1=导入文件, 2=链接文件, 3=web链接
      "hasFulltext": true,            // ← 是否已完成全文索引
      "size": 1918391,
      "title": "Full Text PDF",
      "path": "/Users/.../storage/3K7SPS59/xxx.pdf",  // 本地文件路径
      "contentType": "application/pdf",
      "filename": "xxx.pdf"
    }
  ]
}
```

### 调用模式

```typescript
// 获取完整信息（推荐用于 Phase 2）
get_item_details(itemKey="VFPYB58F", mode="complete")
```

### 注意事项

- 在 `mode="complete"` 下才返回 `path` 和 `hasFulltext` 等详细字段
- `abstractNote` 可能为空字符串
- **`attachments[].key`** 是附件条目 key，与父条目 key 不同

---

## 3. get_content — 提取 PDF 全文

### 关键参数

| 参数 | 说明 |
|------|------|
| `itemKey` | **必填**。此处应为**附件条目的 key**（非父条目 key） |

### 返回值

返回 PDF 的全文文本内容（字符串）。内容为提取后的纯文本，已去除 PDF 排版信息。

### 调用模式

```typescript
// 先获取附件 key，再提取全文
// step 1: 获取条目详情
const details = get_item_details(itemKey="VFPYB58F", mode="complete")
// step 2: 找到 PDF 附件的 key
const pdfKey = details.attachments.find(a => a.contentType === "application/pdf")?.key
// step 3: 提取全文
const fulltext = get_content(itemKey=pdfKey)  // 注意：pdfKey 是附件 key
```

### 注意事项

- **`itemKey` 必须是附件 key（如 `3K7SPS59`），而非父条目 key（如 `VFPYB58F`）**
- 只有 `hasFulltext: true` 的附件才能成功提取；`false` 说明 Zotero 尚未索引该 PDF
- 提取的内容可能包含页眉页脚、参考文献等噪音
- 扫描件 PDF（无 OCR 层）会返回空或极短的内容
- 如果在 `search_library` 中直接搜到了 attachment item（没有父条目的独立 PDF），该 attachment 的 key 可直接用于 `get_content`

---

## 4. write_note — 写入子笔记

### 关键参数

| 参数 | 说明 |
|------|------|
| `action` | `"create"`（新建）/ `"update"`（替换）/ `"append"`（追加） |
| `parentKey` | **必填**。笔记挂载的**父条目 key**（有元数据的 regular item） |
| `noteKey` | 已有笔记的 key（`"update"` / `"append"` 操作时必填） |
| `content` | 笔记内容，支持 **Markdown** 或 HTML |
| `tags` | 标签数组，如 `["文献报告", "openeq"]` |

### 返回值结构

```json
{
  "action": "create",
  "success": true,
  "data": {
    "noteKey": "4YLCGITZ",
    "parentKey": "VFPYB58F",
    "contentPreview": "...",
    "contentLength": 8484,
    "tags": ["文献报告", "openeq"],
    "dateCreated": "2026-06-04 11:17:31"
  }
}
```

### 调用模式

```typescript
// 创建新笔记（最常用）
write_note(
  action="create",
  parentKey="VFPYB58F",
  content="# 文献报告\n\n...",
  tags=["文献报告"]
)

// 追加到已有笔记
write_note(
  action="append",
  noteKey="4YLCGITZ",
  content="\n\n## 补充内容\n...",
  tags=[]
)
```

### 注意事项

- **`parentKey` 必须是有元数据的 regular item key（如 `VFPYB58F`），不能是 attachment item key（如 `3K7SPS59`）**
- 写入 attachment item 会失败或创建独立笔记
- Markdown 内容会被 Zotero 自动转换为 HTML 存储
- 内容长度可能有限制（Zotero 内部对笔记大小有约束），超长内容应先尝试，失败后再精简
- 从 `search_library` 结果中，有 `creators` 和 `abstractNote` 的条目即为 regular item，其 key 可直接用作 `parentKey`

---

## 常见数据模型：Item Types

Zotero 数据模型中有两种常见的条目类型：

### Regular Item（常规条目）

- 有完整的元数据（`creators`、`abstractNote`、`date`、`DOI` 等）
- 可以有 `attachments`（子附件）和 `notes`（子笔记）
- 在搜索结果中的 `itemType` 非空或为空字符串（取决于是否被 Zotero 识别）
- **示例**: `VFPYB58F`

### Attachment Item（附件条目）

- 通常由 PDF 文件导入时自动创建
- 元数据极简（通常标题为 "Full Text PDF"，无作者、摘要等）
- 可以独立存在（standalone PDF），也可以是 regular item 的子附件
- 在搜索结果中 `itemType` 为空，`creators` 为空数组
- **示例**: `3K7SPS59`

### 如何区分

通过 `get_item_details` 返回的字段判断：
- 有 `creators`（非空数组）且 `abstractNote` 非空的 → Regular Item
- `creators` 为空数组，`title` 为 "Full Text PDF" 的 → Attachment Item

如果搜索意外返回了 Attachment Item，需要找到其父条目。典型做法是：检查该 attachment 是否在某个 regular item 的 `attachments` 列表中（通过反向搜索其他结果中的 `attachments[].key`）。

---

## 标准调用链路

```
Phase 1: search_library(q="标题", mode="standard")
          ↓ itemKey (regular item, 如 VFPYB58F)
          
Phase 2: get_item_details(itemKey="VFPYB58F", mode="complete")
          ↓ attachments[0].key (PDF附件, 如 3K7SPS59)
          ↓ attachments[0].path (本地文件路径)
          ↓ abstractNote (摘要)
          
         get_content(itemKey="3K7SPS59")  [或用 pypdf 直接读 path]
          ↓ 全文文本
          
Phase 5: write_note(
           action="create",
           parentKey="VFPYB58F",     // ← 注意是 regular item key
           content="...",
           tags=["文献报告"]
         )
          ↓ noteKey (验证用)
          
Phase 5: get_item_details(itemKey="VFPYB58F")
         → 验证 notes[] 中是否包含新笔记
```

---

## 错误场景速查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| search_library 返回 0 结果 | 标题拼写错误或论文未导入 | 改用作者/关键词搜索，或建议用户先导入 |
| get_item_details 无 attachments | 条目为纯元数据（无文件） | 进入摘要回退模式（E5） |
| attachments 的 contentType 非 PDF | 附件为网页快照/链接等 | 列出类型，提供摘要回退（E6） |
| hasFulltext = false | PDF 尚未被 Zotero 索引 | 改用 pypdf 直接读 `path`（E7） |
| get_content 返回空 | PDF 为扫描件（无 OCR） | 警告用户，回退到摘要（E8） |
| write_note 失败，parentKey 指向 attachment | 用了 attachment key 而非 regular item key | 重新确认使用正确的 parentKey（E14） |
