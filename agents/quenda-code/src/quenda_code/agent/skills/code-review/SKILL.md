---
name: code-review
description: Apply when reviewing code, checking code quality, or providing feedback on code changes. Use this skill when the user asks you to look at, check, review, or evaluate code.
version: "1.0.0"
---

# Code Review

When reviewing code, provide thorough, constructive feedback that helps improve code quality.

## Review Process

1. **Understand context** - What does this code do? What patterns exist?
2. **Check correctness** - Does it work? Edge cases? Error handling?
3. **Check security** - Input validation? No secrets? Proper permissions?
4. **Check readability** - Clear names? Understandable flow?
5. **Check performance** - Obvious inefficiencies? N+1 queries?

## Feedback Format

```markdown
## Code Review: [file/section]

**Summary**: [One sentence assessment]

### 🔴 Blockers
[Must fix: security issues, data loss, crashes]

### 🟡 Important
[Should fix: performance, maintainability, missing tests]

### 🟢 Suggestions
[Nice to have: style, minor refactoring]

### ✅ Good Practices
[What's done well]
```

## Key Checks

### Python
- Mutable default arguments (dangerous)
- Bare `except:` (too broad)
- Type hints on public functions
- Docstrings for public APIs

### All Languages
- Input validation at boundaries
- Proper error handling
- Resource cleanup
- No secrets in code
