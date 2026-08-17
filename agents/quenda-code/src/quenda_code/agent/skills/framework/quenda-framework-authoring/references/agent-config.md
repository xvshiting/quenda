# Agent configuration

Inspect `quenda capabilities --json --section configuration` before using these
shapes. Preserve keys that are not part of the requested change.

For chat-driven changes, use `apply_agent_config_patch` with an RFC 7396 JSON
Merge Patch. Preview first, then commit against the returned `base_revision`.
`null` removes a key, arrays replace, and objects merge recursively. The tool
validates the complete candidate Agent package, redacts credentials from its
diff, asks the user to approve `agent_config.write`, and records the previous
revision before atomically replacing `config.yaml`.

## Multiple providers and model roles

```yaml
providers:
  hosted:
    type: custom
    name: Hosted Models
    url: https://models.example.com/v1
    api: openai-completions
    api_key: "${HOSTED_API_KEY}"
    models:
      provider-model-id:
        name: Chat Model
        context_window: 128000
        tool_calling: true
      provider-vision-id:
        name: Vision Model
        vision: true

  local:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    models:
      - id: local-model-id
        name: Local Model
        context_window: 32768

models:
  default:
    provider: hosted
    model: provider-model-id
  vision:
    provider: hosted
    model: provider-vision-id
  routing:
    capability_routing: true
    missing_capability: error
```

The model `id` is the selector sent to the provider API; `name` is its display
name. In mapping form, omit `id` to use the mapping key as that selector. A
`llama-server` provider defaults to the OpenAI-compatible completions protocol
and does not require a real key unless that deployment enforces one.

Built-in providers can be overridden without repeating their model catalog:

```yaml
providers:
  jdcloud:
    api_key: "${JDCLOUD_API_KEY}"
```

## Execution trust

```yaml
execution:
  backend: local-trusted
  requires_isolation: false
```

`local-trusted` runs shell and Python commands in local subprocesses. It
provides lifecycle control, timeouts, and permission checks, but it is not a
filesystem or network isolation boundary. Set `requires_isolation: true` when
the Agent must fail closed unless an isolated backend is available. Docker and
SSH are reserved future backends and must not be configured as if they already
exist.

## Skills

```yaml
skills:
  include_catalog: true
  activate:
    - team-review
```

Skill discovery is recursive. Both layouts are valid:

```text
skills/team-review/SKILL.md
skills/review/security/team-review/SKILL.md
```

A directory containing `SKILL.md` is a package boundary. Put its supporting
files below `references/`, `resources/`, `templates/`, `assets/`, or `scripts/`.
