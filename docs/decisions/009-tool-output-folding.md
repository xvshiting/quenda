# ADR-009: Tool Output Folding Strategy

## Status

Accepted

## Context

When agents execute tasks, they often perform many intermediate operations. Current output shows tool names as primary information:

```
✓ search_text: find Model definition [35 lines]
✓ read_file: check kernel Model [49 lines]
✓ apply_patch: fix mypy error
✓ run_shell: mypy check
```

**Problems with current approach:**

1. Tool names are implementation details, not user task semantics
2. Output looks like "executor logs" rather than "agent behavior summary"
3. Too many tool names reduce trust and feel mechanical
4. Violates Unix philosophy of "low noise, high signal"

**Users care about:**
1. What the agent is doing (high-level progress)
2. What changes were made (mutations)
3. Final results

## Decision

### Core Principle

**User view shows "what it's doing", debug view shows "what tools it used".**

Tool names are implementation details. Users should see task-semantic phases, not executor logs.

### Three Display Modes

**1. Default REPL Mode** (user-friendly, semantic)

- Show semantic phases, not tool names
- Fold operations into task-relevant summaries
- No tool names in normal output

Example output:
```
📖 Reading project files...
✏️ Editing code...
✏️ Editing code...
🔍 Verifying changes...
✅ Done. Added type hints to 2 functions.
```

**2. Verbose Mode** (`--verbose` or one-shot mode)

- Show tool names with summaries
- Aggregate by phase with timing
- Show line counts

Example output:
```
📖 Exploration (4 operations, 450ms):
  ✓ search_text: find Model [35 lines]
  ✓ read_file: kernel Model [49 lines]
  ✓ read_file: providers Model [68 lines]

🔧 Modification (3 operations, 200ms):
  ✓ apply_patch: fix mypy error
  ✓ apply_patch: simplify code
  ✓ run_shell: mypy check
```

**3. Debug Mode** (full detail, for development)

- Show every tool call in full detail
- Include complete arguments and results
- No aggregation

### Phase Icons and Labels

| Phase | Icon | Label |
|-------|------|-------|
| Reading | 📖 | Reading project files... |
| Searching | 🔍 | Searching codebase... |
| Editing | ✏️ | Editing code... |
| Writing | 📝 | Writing files... |
| Executing | ⚡ | Running commands... |
| Verifying | ✅ | Verifying changes... |
| Debugging | 🐛 | Debugging... |

### Tool to Phase Mapping

```python
PHASE_MAPPING = {
    # Reading phase
    "list_files": "reading",
    "read_file": "reading",

    # Searching phase
    "search_text": "searching",

    # Editing phase
    "apply_patch": "editing",
    "write_file": "editing",

    # Execution phase
    "run_shell": "executing",
    "python_execution": "executing",

    # Network phase
    "http_request": "executing",
    "web_fetch": "reading",
}
```

### Folding Logic

**Default mode:**
1. Map tool to phase
2. Emit phase label when phase changes
3. No tool names shown
4. Only show mutation confirmations if meaningful

**Verbose mode:**
1. Group consecutive tools by phase
2. Show phase header with count and timing
3. Show each tool with summary
4. Preserve line counts

**Debug mode:**
1. No grouping
2. Full details per tool

### What NOT to Show in Default Mode

- Tool names (implementation detail)
- Line counts (internal metric)
- Timing (unless user asks)
- Repeated operations (fold into count)

### What to Always Show

- Phase changes (user knows what's happening)
- Errors (user needs to know if something failed)
- Final summary (what was accomplished)

## Consequences

### Positive

- User sees task progress, not executor logs
- Cleaner, more trustworthy output
- Still have verbose/debug when needed
- Follows Unix philosophy: low noise, high signal

### Negative

- Less visibility into agent internals by default
- Requires good phase mapping
- More complex rendering logic

## Implementation Notes

### Phase 1: Phase Mapping

- Add `phase` property to Tool interface
- Map existing tools to phases
- Update ConsoleRenderer to use phases

### Phase 2: Default Mode Folding

- Emit phase labels instead of tool names
- Track phase transitions
- Generate semantic summaries

### Phase 3: Mode Support

- Add `--debug` flag for full output
- Implement verbose mode phase grouping
- Test with real agent workloads

## Examples

### Default Mode (Recommended)

```
>>> add type hints to the user module

📖 Reading project files...
✏️ Editing code...
🔍 Verifying changes...
✅ Done. Added type hints to 2 functions.
```

### Verbose Mode

```
>>> add type hints to the user module

📖 Exploration (4 operations, 450ms):
  ✓ search_text: find user module [12 lines]
  ✓ read_file: user.py [156 lines]
  ✓ read_file: types.py [45 lines]

🔧 Modification (3 operations, 200ms):
  ✓ apply_patch: add type hints to get_user
  ✓ apply_patch: add type hints to create_user
  ✓ run_shell: mypy check

✅ Completed in 7 steps (650ms)
```

### Debug Mode

```
>>> add type hints to the user module

[DEBUG] Tool call: search_text(query="def get_user")
[DEBUG] Result: Found 3 matches in user.py
[DEBUG] Tool call: read_file(path="user.py", start=1, end=200)
[DEBUG] Result: 156 lines read
...
```
