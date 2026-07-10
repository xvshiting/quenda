# Policy 系统

Policy 是 Quenda 用来保持框架简洁、又允许 agent 定制行为的主要扩展点。

核心原则是：

- **Runtime/Kernel 负责机制**：模型调用、工具执行、消息写回、状态转换。
- **Policy 负责策略**：什么时候停止、哪些工具能执行、工具结果如何进入上下文。
- **没有配置时使用默认行为**：不写 `policies:` 时，Quenda 保持当前默认执行方式。

这让框架更接近 Unix 哲学：小核心、清晰协议、可组合策略，而不是在 runner 里 hard code 某个产品的工作流。

---

## 支持的 Policy 点

| Policy | 触发点 | 能改变控制流 | 常见用途 |
|--------|--------|--------------|----------|
| `TerminationPolicy` | model/tool step 之后 | 是 | 步数、时间、token、错误预算 |
| `ToolSelectionPolicy` | 模型返回 tool calls 后、执行前 | 是 | allowlist / denylist / 风险审批 |
| `ToolResultProcessingPolicy` | 工具执行后、写回上下文前 | 否，但可改写结果 | 截断、限行、摘要、脱敏 |
| `TraceSink` | 每个 runtime event 发出时 | 否 | JSONL trace、评估、观测 |
| `CompressionPolicy` | 每次 run 开始前检查上下文时 | 是 | 何时压缩上下文 |
| `PermissionPolicy` | 文件/命令等工具执行前 | 是 | workspace 边界、危险命令、用户授权 |

本教程重点讲可以从 agent `config.yaml` 绑定的三类 runtime policy：

- `termination`
- `tool_selection`
- `tool_result_processing`

---

## 在 config.yaml 中使用内置 Policy

不写 `policies:` 时，默认行为保持不变：

- 不提前终止，直到模型自然结束或硬保护触发
- 模型请求的工具默认都允许执行
- 工具结果默认原样写回上下文

配置示例：

```yaml
tools:
  bundles:
    - core
    - network

policies:
  termination:
    type: max_steps
    max_steps: 30

  tool_selection:
    type: allowlist
    allowed:
      - list_files
      - search_text
      - read_file
      - apply_patch
      - run_shell
      - request_interaction

  tool_result_processing:
    type: truncate
    max_chars: 6000
```

Host 会在 setup 阶段解析这些配置，并把生成的 policy 绑定到 `Agent -> Session -> Run`。

---

## 常见内置 Policy

### TerminationPolicy

限制执行规模，防止 agent 失控或成本爆炸。

```yaml
policies:
  termination:
    type: max_steps
    max_steps: 50
```

可用类型：

| type | 参数 | 说明 |
|------|------|------|
| `max_steps` | `max_steps` | 达到最大 step 数后停止 |
| `time_budget` | `max_time_ms` | 达到时间预算后停止 |
| `token_budget` | `max_total_tokens` | 达到 token 预算后停止 |
| `consecutive_errors` | `max_consecutive_errors` | 连续错误过多后停止 |
| `default` / `never` | 无 | 不配置提前终止 |

### ToolSelectionPolicy

控制模型请求的 tool call 是否真的执行。

Allowlist：

```yaml
policies:
  tool_selection:
    type: allowlist
    allowed:
      - read_file
      - search_text
      - apply_patch
```

Denylist：

```yaml
policies:
  tool_selection:
    type: denylist
    denied:
      - run_shell
      - execute_python
```

可用类型：

| type | 参数 | 说明 |
|------|------|------|
| `allowlist` | `allowed` | 只允许列出的工具执行 |
| `denylist` | `denied` | 禁止列出的工具执行 |
| `default` / `allow_all` | 无 | 保持默认：允许所有请求 |

被拒绝的工具调用不会消失。Runtime 会写回一个显式 denial result，让模型知道请求被拒绝以及原因。

### ToolResultProcessingPolicy

控制工具结果进入模型上下文前的形态。

字符截断：

```yaml
policies:
  tool_result_processing:
    type: truncate
    max_chars: 8000
```

行数限制：

```yaml
policies:
  tool_result_processing:
    type: line_limit
    max_lines: 120
```

可用类型：

| type | 参数 | 说明 |
|------|------|------|
| `passthrough` | 无 | 原样写回 |
| `truncate` | `max_chars`, `suffix` | 按字符截断 |
| `line_limit` | `max_lines`, `suffix` | 按行数截断 |

Trace 中仍会保留 raw result，方便调试和审计。

---

## 定义自定义 Policy

自定义 policy 放在 agent 包的：

```text
extensions/policies/
```

目录下。推荐用 `policies` 字典导出：

```python
# extensions/policies/safe_tools.py
from quenda.runtime.tool_policy import (
    RejectedToolCall,
    ToolSelectionDecision,
)


class NoShellPolicy:
    def select_tools(self, request):
        approved = []
        rejected = []

        for call in request.tool_calls:
            if call.name == "run_shell":
                rejected.append(RejectedToolCall(call, "run_shell disabled"))
            else:
                approved.append(call)

        return ToolSelectionDecision(approved, rejected)


policies = {
    "no_shell": NoShellPolicy(),
}
```

然后在 `config.yaml` 使用：

```yaml
policies:
  tool_selection:
    type: local
    name: no_shell
```

---

## 使用 Factory 接收配置

如果 policy 需要参数，导出 factory：

```python
# extensions/policies/result_limits.py
from quenda.runtime.tool_policy import ProcessedToolResult


class RedactingPolicy:
    def __init__(self, marker: str = "[redacted]"):
        self.marker = marker

    def process_result(self, result):
        content = result.raw_content.replace("SECRET", self.marker)
        return ProcessedToolResult(
            content=content,
            is_error=result.is_error,
            display_hint=result.display_hint,
            change_preview=result.change_preview,
            result_summary=result.result_summary,
        )


def make_redactor(config):
    return RedactingPolicy(marker=config.get("marker", "[redacted]"))


policies = {
    "redactor": make_redactor,
}
```

配置：

```yaml
policies:
  tool_result_processing:
    type: local
    name: redactor
    marker: "[secret removed]"
```

Host 会把除 `type` / `name` 之外的字段作为 `config` 传给 factory。

---

## register(builder) 形式

也可以显式注册：

```python
# extensions/policies/my_policies.py
from quenda.host import PolicyRegistryBuilder


def register(builder: PolicyRegistryBuilder):
    builder.register_factory("my_policy", lambda config: MyPolicy(config))
```

这种形式适合一个文件注册多个 policy，或需要更复杂的初始化逻辑。

---

## 程序化使用

如果不是通过 agent package，而是直接写 Python，也可以直接传实例：

```python
from quenda import Agent
from quenda.runtime.termination import MaxStepsPolicy
from quenda.runtime.tool_policy import (
    AllowlistToolSelectionPolicy,
    TruncatingToolResultProcessingPolicy,
)

agent = Agent(
    name="safe-agent",
    tools=tools,
    model=model,
    termination_policy=MaxStepsPolicy(max_steps=30),
    tool_selection_policy=AllowlistToolSelectionPolicy({
        "read_file",
        "search_text",
        "apply_patch",
    }),
    tool_result_processing_policy=TruncatingToolResultProcessingPolicy(max_chars=6000),
)
```

---

## TraceSink

`TraceSink` 是观察器，不改变控制流。常用于记录运行轨迹：

```python
from quenda.runtime import JsonlTraceSink

agent = Agent(
    name="traced-agent",
    tools=tools,
    model=model,
    trace_sink=JsonlTraceSink("traces/run.jsonl"),
)
```

自定义 TraceSink：

```python
class PrintTrace:
    def record(self, event):
        print(event.type)
```

注意：`record()` 不应该抛异常。Runtime 会尽量吞掉 trace sink 错误，避免观测逻辑影响主流程。

---

## 设计建议

- 把 policy 做小：一个 policy 只处理一个决策点。
- 默认保守：不配置时让框架行为保持简单。
- 安全策略优先放在 `ToolSelectionPolicy` 和 `PermissionPolicy`。
- 上下文成本控制优先放在 `ToolResultProcessingPolicy`、`CompressionPolicy` 和 `TerminationPolicy`。
- 不要把产品工作流 hard code 到 runner；放到 agent-local policy、tool、MCP 或上层 Host extension。

---

## 下一步

- [API 参考](./08-references.md)
- [事件系统](./06-events.md)
