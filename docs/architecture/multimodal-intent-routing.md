# Multimodal Intent Routing

## 问题背景

当前实现存在一个核心误区：**看到图片语法形式就自动走 vision**。

这导致：
1. 成本和延迟增加（不必要的 vision 调用）
2. 隐私暴露风险（不该看的内容被看）
3. 语义错位（有些图片只是引用/装饰，不需要像素理解）

## Claude Code 的设计参考

Claude Code 的图片处理遵循**用户主动控制**原则：

1. **用户主动粘贴/拖放图片** → 图片被存储，显示 `[Image #N]` 占位符
2. **不会自动从 URL/Markdown 提取图片** → 需要 Router 决策
3. **本地文件路径** → 用户主动输入时可以处理

```typescript
type PastedContent = {
  id: number
  type: 'text' | 'image'
  content: string  // base64
  mediaType?: string
  filename?: string
  sourcePath?: string  // 本地文件路径
}
```

## 核心原则

**任务意图决定是否 vision，语法形式只做候选提取。**

Markdown 图片语法 `![](url)` 只是表达"这里有一个媒体引用"，不等于需要视觉理解。

## 三段式架构

```
┌─────────────────────────┐
│   Stage 1: Parser       │  确定性解析，提取候选
│   (Deterministic)       │
└───────────┬─────────────┘
            │ 候选媒体列表
            ↓
┌─────────────────────────┐
│   Stage 2: Router       │  LLM 或规则决策
│   (Vision Decision)     │
└───────────┬─────────────┘
            │ routing decision
            ↓
┌─────────────────────────┐
│   Stage 3: Executor     │  执行对应路径
│   (Path Execution)      │
└─────────────────────────┘
```

---

## Stage 1: Deterministic Parser

**职责**：稳定识别并提取候选媒体引用，不做决策。

### 识别对象

| 类型 | 模式 | 提取结果 |
|------|------|----------|
| 本地路径 | `/path/to/file.jpg`, `~/Downloads/img.png` | `{type: "local_path", path: "...", media_type: "image/jpeg"}` |
| 明确图片 URL | `https://.../*.jpg`, `https://.../*.png` | `{type: "image_url", url: "...", media_type: "image/jpeg"}` |
| Markdown 图片 | `![alt](url)` | `{type: "markdown_image", url: "...", alt: "..."}` |
| HTML img 标签 | `<img src="...">` | `{type: "html_image", url: "..."}` |
| 普通网页 URL | `https://example.com/page` | `{type: "web_url", url: "..."}` |
| 文本链接提及 | `链接：https://...` | `{type: "text_reference", url: "..."}` |

### 输出

```python
class MediaCandidate:
    type: Literal["local_path", "image_url", "markdown_image", "html_image", "web_url", "text_reference"]
    uri: str  # path 或 URL
    media_type: str | None  # 如果能推断
    context: str  # 原始上下文（如周围的文本）
```

**Parser 不决策**，只提取候选，交给 Router。

---

## Stage 2: Vision Router

**职责**：根据任务意图，决定每个候选的处理路径。

### Routing Decision

```python
class RoutingDecision:
    action: Literal["vision", "text_only", "web_fetch", "ask_user"]
    reason: str  # 决策理由
```

### 决策规则（优先级从高到低）

#### 规则层（确定性）

| 规则 | 条件 | Action |
|------|------|--------|
| 本地图片路径 + 明确视觉问题 | path 存在 + 用户说"看看这张图" | `vision` |
| 明确图片 URL + 视觉动词 | URL 以 .jpg/.png 结尾 + "识别/分析/看看" | `vision` |
| 普通网页 URL | URL 不以图片扩展名结尾 | `web_fetch` 或 `text_only` |
| 纯引用/装饰图 | 无视觉动词 + 图片只是上下文的一部分 | `text_only` |

#### LLM 决策层（语义判断）

当规则无法确定时，交给 LLM 做 intent classification：

**Prompt 示例**：
```
用户输入："{user_input}"
检测到媒体引用：
  - type: {candidate.type}
  - uri: {candidate.uri}
  - context: {candidate.context}

请判断：这个引用是否需要视觉理解？
A. vision - 需要看图片内容才能回答
B. text_only - 只需要知道"有一个图片引用"，不需要看像素
C. web_fetch - 这是一个网页，需要抓取文本内容
D. ask_user - 不确定，需要询问用户

输出格式：{"action": "...", "reason": "..."}
```

### 决策示例

| 用户输入 | 候选类型 | Router 决策 | 原因 |
|----------|----------|-------------|------|
| "这张图里有什么？" + `/path/img.jpg` | local_path | `vision` | 明确视觉任务 |
| "帮我分析这个网页 https://example.com" | web_url | `web_fetch` | 网页分析任务 |
| "文中引用了一个图片链接 https://...jpg" | image_url | `text_only` | 只是提及，无视觉意图 |
| "这个链接是图片吗？" | ambiguous | `ask_user` | 需要用户澄清 |

---

## Stage 3: Executor

**职责**：根据 Routing Decision 执行对应路径。

### Action 路径

| Action | 执行 |
|--------|------|
| `vision` | 读取图片 -> 创建 `ImageContent` -> 发送给模型 |
| `text_only` | 不做特殊处理，保留原始文本引用 |
| `web_fetch` | 调用网页抓取工具 -> 获取文本内容 -> 加入上下文 |
| `ask_user` | 向用户询问："这个图片链接需要我查看内容吗？" |

### Vision 执行条件

只有当 Router 返回 `vision` 时，才：
1. 读取图片数据（本地文件或 URL）
2. 创建 `ImageRef` 和 `ImageContent`
3. 构建多模态消息发送给模型

---

## 推荐实现顺序

### Phase 1: Parser + 规则 Router

1. 实现 Deterministic Parser，稳定识别各类媒体引用
2. 实现规则层 Router，处理明确的视觉任务
3. 默认 fallback：不确定的走 `text_only`

### Phase 2: LLM Router

1. 当规则无法确定时，调用轻量 LLM 做 intent classification
2. 记录 router decision 用于审计和调优

### Phase 3: Executor 扩展

1. 实现 `web_fetch` 路径（网页抓取）
2. 实现 `ask_user` 交互流程

---

## 关键原则总结

1. **语法形式 ≠ 任务意图**：Markdown 图片语法只是载体，不代表需要 vision
2. **先识别，后决策**：Parser 提取候选，Router 决策路径
3. **宁可不自动转，也不要误转**：有歧义时默认 `text_only`
4. **任务意图驱动**："这张图里有什么" -> vision，"帮我分析网页" -> web_fetch
5. **本地路径优先**：本地图片文件基本可以直接走 vision（规则优先）

---

## 文件结构建议

```
src/quenda/host/
├── media_parser.py      # Stage 1: Deterministic Parser
├── vision_router.py     # Stage 2: Vision Decision Router
└── media_executor.py    # Stage 3: Executor
```

---

## 一句话结论

**不是看到图片就走 vision，而是先判断任务意图，再决定是否需要视觉理解。**