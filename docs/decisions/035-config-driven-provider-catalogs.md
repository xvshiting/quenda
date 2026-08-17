# ADR-035: Config-Driven Provider Catalogs

## Status

Accepted

## Context

Quenda already separates a model provider (`ProviderSpec`) from its HTTP
protocol adapter, but Agent authors could only select built-in providers from
`config.yaml`. Adding an OpenAI-compatible private endpoint required executable
Python under `extensions/providers/`, so an Agent could not safely explain or
apply the common configuration itself.

Agent packages also need several providers at once: a default text model, a
vision model, and sometimes a local llama.cpp model. Credentials are usually
environment references, but local and self-contained deployments also need an
explicit config value.

## Decision

`config.yaml` may contain a `providers` mapping. Each entry is either:

- a `builtin` override, which inherits the registered URL, protocol, and model
  catalog and may replace fields such as `api_key`; or
- a `custom` provider with an explicit URL, protocol, credential, and models;
  or
- a `llama-server` preset, which uses the existing `openai-completions`
  adapter and the conventional `no-key` placeholder when no key is supplied.

Example:

```yaml
providers:
  jdcloud:
    api_key: "${JDCLOUD_API_KEY}"

  local-llama:
    type: llama-server
    url: http://127.0.0.1:8080/v1
    models:
      - id: "qwen3.5:9b"
        name: Local Qwen 3.5 9B
        context_window: 32768
        tool_calling: true

  private-cloud:
    type: custom
    url: https://models.example.com/v1
    api: openai
    key: "${PRIVATE_MODEL_KEY}"
    models:
      - id: vision-1
        name: Private Vision
        vision: true

models:
  default: local-llama/qwen3.5:9b
  vision: private-cloud/vision-1
  routing:
    capability_routing: true
    missing_capability: error
```

`base_url`/`api_key` are canonical spellings; `url`/`key` are concise aliases.
`api: openai` maps to `openai-completions`, while `api: anthropic` maps to
`anthropic-messages`. Model `id` is passed unchanged to the upstream server;
`name` is display metadata.

Capability binding applies catalogs in this order:

1. framework built-ins;
2. Agent-local Python provider extensions;
3. the Agent's declarative provider entries.

The entries are registered only at capability bind/rebind time, never during a
text-only Run refresh. CLI provider/model overrides still win over role
selection, while `models.default` and `models.vision` retain ADR-028 semantics.

## Credential Policy

Both direct values and `${ENV_VAR}` references are supported. Environment
references are recommended because Agent Homes, backups, Web editors, and
support bundles may expose `config.yaml`. `ProviderConfig.__repr__` redacts the
credential field, but Quenda does not claim that a plaintext file secret is a
secret-store boundary.

## llama.cpp Compatibility

Current llama.cpp exposes OpenAI-compatible `/v1/models` and
`/v1/chat/completions` routes. Quenda therefore reuses its existing transport
adapter rather than creating a llama-specific Model implementation. Tool use
depends on llama.cpp being launched with a compatible chat template, normally
including `--jinja`. See the
[official llama-server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Unix Consequences

- Provider configuration is ordinary YAML: inspectable, diffable, and usable
  without an interactive control plane.
- Protocol adapters remain independent from provider declarations.
- Registration is separate from invocation; loading configuration makes no
  network request.
- A custom endpoint uses the same runtime interface as an official provider.

## Non-Goals

- automatic remote model discovery from `/v1/models`;
- encrypted secret storage inside `config.yaml`;
- silently guessing context windows or tool/vision capability;
- implementing llama.cpp-only sampling extensions.
