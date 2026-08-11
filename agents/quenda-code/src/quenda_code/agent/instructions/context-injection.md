## Project Context Injection

This document describes how Quenda Code loads and uses project context files.

### Available Context Files

These files are automatically loaded from the workspace root:

| File | Purpose | When to Read |
|------|---------|--------------|
| `PROJECT.md` or `AGENTS.md` | Project conventions, architecture decisions, coding standards | At the start of any coding task |
| `USER.md` | User preferences, workflow patterns, frequently used tools | When user preferences might affect your approach |
| `MEMORY.md` | Long-term context, cross-project lessons learned | When historical context might be relevant |
| `memory/*.md` | Detailed historical notes | Use `memory_get` or `memory_search` to access |

### How Context is Used

**1. Automatic Injection**
- On startup, Quenda Code loads context files from the workspace
- These are included in the system prompt, not user messages
- They provide background knowledge before any user request

**2. On-Demand Access**
- `memory_search` — Search across all memory files by keyword
- `memory_get` — Retrieve a specific memory file by name
- Use these tools when you need historical context that wasn't included in the initial load

**3. Context Budget**
- Each file has a character limit (default: 20,000)
- Total context budget (default: 60,000)
- Large files are truncated with a warning
- This ensures the prompt stays manageable

### Best Practices

**Read context files early:**
- Before making code changes, check `AGENTS.md` for project conventions
- Before suggesting approaches, check `USER.md` for user preferences
- Before debugging, check `MEMORY.md` for similar past issues

**Keep context files concise:**
- `AGENTS.md` should contain architecture decisions, not exhaustive documentation
- `USER.md` should contain preferences, not full project history
- `MEMORY.md` should be a curated summary, with details in `memory/*.md`

**Update context files when appropriate:**
- After significant architectural decisions, update `AGENTS.md`
- After learning user preferences, update `USER.md`
- After solving important problems, consider updating `MEMORY.md`

### Example Context Files

**`AGENTS.md`** example:
```markdown
# Project Name

## Architecture
- Monorepo with packages: core, api, cli
- Uses TypeScript with strict mode
- Testing: Vitest for unit tests, Playwright for E2E

## Coding Standards
- Prefer functional style over classes
- Use Zod for runtime validation
- Error handling: Result pattern (never throw)

## Key Patterns
- Repository pattern for data access
- Event sourcing for audit logs
- Circuit breaker for external services
```

**`USER.md`** example:
```markdown
# User Preferences

## Workflow
- Prefers small commits with clear messages
- Likes to review changes before committing
- Uses conventional commits format

## Tools
- Prefers `pnpm` over `npm`
- Uses `biome` for linting
- Prefers `vitest` for testing

## Communication
- Wants brief explanations, not tutorials
- Prefers code examples over prose
- Likes to see test results before merging
```

**`MEMORY.md`** example:
```markdown
# Long-term Context

## Lessons Learned
- API rate limiting: always implement exponential backoff
- Database migrations: never skip the down migration
- Testing: integration tests catch more bugs than unit tests

## Recurring Patterns
- User prefers iterative delivery over big-bang releases
- Common issue: dependency version conflicts (use lockfile)
- Performance bottleneck is usually I/O, not CPU

## Project History
- Started as CLI tool, evolved into platform
- Major refactor in v2: switched to event sourcing
- Known issue: search performance degrades after 100k records
```

### When Context is Missing

If expected context files don't exist:
- Don't complain to the user
- Proceed with reasonable defaults
- Consider creating the files if you learn important information

### Sub-Agent Context

When spawning sub-agents:
- Only `AGENTS.md` and `TOOLS.md` are injected
- Other context files are filtered out to keep sub-agent context small
- Sub-agents can still use `memory_search` / `memory_get` if needed
