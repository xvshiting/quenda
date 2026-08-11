## Tool Best Practices

This document provides specific guidance and examples for using Quenda Code's tools effectively.

## Filesystem Tools

### `list_files` — Browse directories

**Purpose**: See what files exist in the workspace.

**Best Practices**:
- Use `pattern` to filter results (e.g., `*.py`, `src/**`)
- Use `recursive=True` for deep exploration
- Use `recursive=False` for quick overview

**Examples**:
```python
# List all Python files in src/
list_files(path="src", pattern="*.py", recursive=True)

# Quick overview of root directory
list_files(path=".", recursive=False)

# Find all test files
list_files(pattern="test_*.py", recursive=True)
```

### `search_text` — Search file contents

**Purpose**: Find where specific code or text appears.

**Best Practices**:
- Use specific patterns first, then broaden if needed
- Use regex for complex patterns
- Use `context_lines` to see surrounding code
- Use `path` to narrow search scope

**Examples**:
```python
# Find all class definitions
search_text(pattern=r"class \w+\(", context_lines=3)

# Find TODO comments in a specific directory
search_text(pattern="TODO", path="src/api", context_lines=2)

# Find function calls with specific pattern
search_text(pattern=r"def process_\w+\(", path="src/")
```

### `read_file` — View file contents

**Purpose**: See the actual content of files.

**Best Practices**:
- Use `offset` and `limit` for large files
- Don't read entire files unless necessary
- Read related files together to understand context

**Examples**:
```python
# Read entire small file
read_file(path="config.yaml")

# Read specific lines from a large file
read_file(path="src/main.py", offset=100, limit=50)

# Read the beginning of a file
read_file(path="src/utils.py", limit=100)
```

### `write_file` — Create or overwrite files

**Purpose**: Create new files or replace entire files.

**Best Practices**:
- Prefer `apply_patch` for targeted changes
- Use for completely new files
- Verify file doesn't already exist before overwriting

**Examples**:
```python
# Create a new configuration file
write_file(path="config.yaml", content="key: value\n")

# Create a new Python module
write_file(path="src/new_module.py", content='"""\nNew module.\n"""\n\n')
```

### `apply_patch` — Apply targeted text patches

**Purpose**: Make precise, targeted changes to existing files.

**Best Practices**:
- Prefer over `write_file` for modifications
- Use exact text matching (copy-paste from file)
- Keep patches small and focused
- One patch per logical change

**Examples**:
```python
# Add a new import
apply_patch(path="src/main.py", patch="""
@@
 import os
 import sys
+import json
""")

# Fix a typo
apply_patch(path="README.md", patch="""
@@
-This is a exmple.
+This is an example.
""")

# Add a new function
apply_patch(path="src/utils.py", patch="""
@@
 def helper():
     pass
+
+def new_function():
+    """New function."""
+    return 42
""")
```

## Execution Tools

### `run_shell` — Execute shell commands

**Purpose**: Run system commands, tests, build tools.

**Best Practices**:
- Use specific commands over generic ones
- Always validate command safety
- Use `timeout` for long-running commands
- Check output for errors
- Prefer workspace-relative paths

**Examples**:
```python
# Run tests
run_shell(command="pytest tests/ -v")

# Build the project
run_shell(command="python -m build")

# Install dependencies
run_shell(command="pip install -r requirements.txt", timeout=60)

# Check git status
run_shell(command="git status --short")
```

### `execute_python` — Run Python code in sandbox

**Purpose**: Execute Python code safely for testing, data analysis, or automation.

**Best Practices**:
- Use for one-off scripts or quick tests
- Keep code simple and focused
- Use imports from workspace
- Handle errors explicitly

**Examples**:
```python
# Quick data analysis
execute_python(code="""
import json

data = json.load(open('data.json'))
print(f"Total records: {len(data)}")
print(f"Keys: {data[0].keys()}")
""")

# Test a function
execute_python(code="""
from src.utils import calculate

result = calculate(10, 20)
assert result == 30, f"Expected 30, got {result}"
print("✓ Test passed")
""")
```

## Memory Tools

### `memory_search` — Search memory files

**Purpose**: Find relevant historical context across all memory files.

**Best Practices**:
- Use specific keywords
- Use when you need context that might not be in the current prompt
- Search for patterns like "API rate limiting", "database migration", etc.

**Examples**:
```python
# Search for API-related context
memory_search(query="API rate limiting")

# Search for past debugging experiences
memory_search(query="TypeError NoneType")

# Search for architectural decisions
memory_search(query="event sourcing")
```

### `memory_get` — Retrieve specific memory file

**Purpose**: Get the content of a specific memory file.

**Best Practices**:
- Use when you know the exact file name
- Use for detailed historical notes
- Example: `memory_get(name="2026-08-10")` for daily notes

**Examples**:
```python
# Get today's notes
memory_get(name="2026-08-11")

# Get specific project notes
memory_get(name="project-api-refactor")
```

## Interaction Tools

### `request_interaction` — Ask the user for input

**Purpose**: Get user decisions, confirmations, or choices.

**Best Practices**:
- Use when you need a user decision
- Provide clear options
- Explain why you're asking
- Don't overuse for simple tasks

**Examples**:
```python
# Ask for confirmation
request_interaction(
    type="confirmation",
    message="I found 3 similar functions. Should I refactor them into one?",
    options=["Yes", "No", "Show me first"]
)

# Ask for a choice
request_interaction(
    type="choice",
    message="Which approach do you prefer?",
    options=["Approach A: Simpler but slower", "Approach B: Faster but more complex"]
)
```

## Workflow Patterns

### Pattern 1: Understand → Plan → Execute

```
1. Read AGENTS.md and USER.md for context
2. Search for relevant code
3. Read the key files
4. Plan your approach (brief)
5. Execute in small steps
6. Verify each step
```

### Pattern 2: Debug with Evidence

```
1. Reproduce the issue
2. Search for error messages or patterns
3. Read the relevant code
4. Form a hypothesis
5. Test the hypothesis (run tests, add logging)
6. Fix the root cause
7. Verify the fix
```

### Pattern 3: Refactor Safely

```
1. Understand the existing code thoroughly
2. Write tests for current behavior
3. Make small, focused changes
4. Run tests after each change
5. Verify behavior is preserved
6. Update documentation
```

## Common Mistakes to Avoid

❌ **Reading entire large files**:
```python
# Bad: reads 5000 lines
read_file(path="large_file.py")

# Good: reads relevant section
read_file(path="large_file.py", offset=100, limit=50)
```

❌ **Calling too many tools at once**:
```python
# Bad: 10 tools in one batch
batch([
    read_file("file1.py"),
    read_file("file2.py"),
    read_file("file3.py"),
    # ... 7 more
])

# Good: 3-5 tools, then assess
batch([read_file("file1.py"), read_file("file2.py")])
# → summarize, then continue
```

❌ **Not verifying changes**:
```python
# Bad: write and assume it works
write_file(path="config.yaml", content="...")

# Good: write and verify
write_file(path="config.yaml", content="...")
run_shell(command="python -c 'import yaml; yaml.safe_load(open(\"config.yaml\"))'")
```

❌ **Ignoring context files**:
```python
# Bad: start coding immediately
search_text("def process")

# Good: read context first
read_file("AGENTS.md")  # Understand project conventions
search_text("def process")
```

## Tool Combination Examples

**Example 1: Find and fix a bug**
```python
# Step 1: Search for the error
search_text(pattern="TypeError.*NoneType", context_lines=3)

# Step 2: Read the problematic function
read_file(path="src/utils.py", offset=50, limit=30)

# Step 3: Write a fix
apply_patch(path="src/utils.py", patch="...")

# Step 4: Test the fix
run_shell(command="pytest tests/test_utils.py -v")
```

**Example 2: Add a new feature**
```python
# Step 1: Understand the module
read_file(path="AGENTS.md")
read_file(path="src/module.py", limit=100)

# Step 2: Find similar patterns
search_text(pattern="def similar_function", context_lines=5)

# Step 3: Implement the feature
apply_patch(path="src/module.py", patch="...")

# Step 4: Add tests
write_file(path="tests/test_new_feature.py", content="...")

# Step 5: Run tests
run_shell(command="pytest tests/test_new_feature.py")
```

**Example 3: Refactor code**
```python
# Step 1: Understand current code
read_file(path="src/old_module.py")

# Step 2: Find all usages
search_text(pattern="from old_module import", context_lines=1)

# Step 3: Create new module
write_file(path="src/new_module.py", content="...")

# Step 4: Update imports
apply_patch(path="src/main.py", patch="...")

# Step 5: Run tests
run_shell(command="pytest tests/")
```
