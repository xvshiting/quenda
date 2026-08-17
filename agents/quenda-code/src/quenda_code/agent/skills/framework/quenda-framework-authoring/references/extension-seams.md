# Extension seams

Use `quenda capabilities --json` for the exact currently exposed contracts.
Use `quenda capabilities --json --section lifecycle` for the ordered lifecycle
catalog, including active and reserved seams, failure behavior, mutation scope,
transition authority, and prompt-cache impact.

| Need | Preferred seam |
| --- | --- |
| Model wire protocol | `Api` implementation registered with `ApiRegistry` |
| Provider and model catalog | Declarative `providers` config or `ProviderSpec` |
| Callable operation | Tool registered through the Host tool registry |
| Additional prompt material | `extensions/context/*.py` context provider |
| Run stopping rule | `TerminationPolicy` |
| Tool admission | `ToolSelectionPolicy` |
| Tool result shaping | `ToolResultProcessingPolicy` |
| Context compression decision | `CompressionPolicy` |
| Agent-local commands or setup | The matching `extensions/<kind>/*.py` loader |

Keep registration, exposure, permission, and execution separate. An installed
extension must not silently become enabled or privileged. Runtime policies
receive typed snapshots and return decisions; they must not mutate a shared Run
as an undocumented hook mechanism.

For a missing lifecycle point, add a narrow core contract first, then build the
official behavior through the same public contract available to third parties.
