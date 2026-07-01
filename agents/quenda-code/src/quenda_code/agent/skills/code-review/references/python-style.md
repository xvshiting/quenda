# Python Style Guidelines

Essential Python style rules following PEP 8 and modern best practices.

## Naming Conventions

| Type | Style | Example |
|------|-------|---------|
| Module | snake_case | `data_processor.py` |
| Class | PascalCase | `DataProcessor` |
| Function | snake_case | `process_data()` |
| Variable | snake_case | `user_count` |
| Constant | UPPER_SNAKE | `MAX_RETRIES` |
| Private | _leading_underscore | `_internal_value` |
| Protected | _leading_underscore | `_protected_method` |

## Imports

```python
# Standard library first
import os
import sys
from pathlib import Path

# Third-party second
import numpy as np
import pandas as pd
from flask import Flask, request

# Local imports last
from myproject import utils
from myproject.models import User
```

## Code Layout

### Indentation
- Use 4 spaces (not tabs)
- Continuation lines should align with opening delimiter

```python
# Good
result = some_function(
    arg1, arg2,
    arg3, arg4
)

# Also good
result = some_function(arg1, arg2,
                        arg3, arg4)
```

### Line Length
- Maximum 88 characters (Black default) or 79 (PEP 8)
- Break lines at operators, not after

```python
# Good
total = (first_variable
         + second_variable
         - third_variable)

# Bad
total = first_variable + second_variable - \
    third_variable
```

### Blank Lines
- 2 blank lines before top-level functions/classes
- 1 blank line between methods
- 1 blank line separating logical sections

## Common Anti-Patterns

### Mutable Default Arguments

```python
# BAD: Default list is shared across calls
def add_item(item, items=[]):
    items.append(item)
    return items

# GOOD: Use None as default
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### Bare except

```python
# BAD: Catches everything including KeyboardInterrupt
try:
    do_something()
except:
    pass

# GOOD: Catch specific exceptions
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
```

### String Concatenation in Loops

```python
# BAD: O(n²) performance
result = ""
for item in items:
    result += str(item)

# GOOD: Use join
result = "".join(str(item) for item in items)
```

### Late Binding in Closures

```python
# BAD: All lambdas use final i value
functions = [lambda: i for i in range(5)]

# GOOD: Capture current value
functions = [lambda i=i: i for i in range(5)]
```

## Type Hints

```python
from typing import Optional, List, Dict, Any

def process_data(
    items: List[str],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """Process a list of items and return counts."""
    result: Dict[str, int] = {}
    for item in items:
        result[item] = result.get(item, 0) + 1
    return result
```

## Docstrings

```python
def calculate_discount(
    price: float,
    discount_rate: float,
    min_price: float = 0.0,
) -> float:
    """Calculate the discounted price.

    Applies the discount rate to the original price,
    ensuring the result doesn't fall below min_price.

    Args:
        price: Original price in dollars.
        discount_rate: Discount rate as decimal (0.1 = 10%).
        min_price: Minimum price floor.

    Returns:
        The discounted price.

    Raises:
        ValueError: If discount_rate is negative or > 1.

    Example:
        >>> calculate_discount(100.0, 0.2)
        80.0
    """
    if not 0 <= discount_rate <= 1:
        raise ValueError("discount_rate must be between 0 and 1")

    discounted = price * (1 - discount_rate)
    return max(discounted, min_price)
```

## Context Managers

```python
# GOOD: Always use context managers for resources
with open("file.txt") as f:
    content = f.read()

# GOOD: Multiple context managers
with open("input.txt") as fin, open("output.txt", "w") as fout:
    fout.write(fin.read())
```

## Comprehensions

```python
# GOOD: Clear and readable
squares = [x**2 for x in range(10)]
even_squares = {x: x**2 for x in range(10) if x % 2 == 0}
unique_lengths = {len(s) for s in strings}

# BAD: Too complex, use a loop instead
result = [process(x) for sublist in data if validate(sublist)
          for x in sublist if filter(x) if condition(x)]
```

## f-strings

```python
# GOOD: Use f-strings for formatting
name = "Alice"
count = 42
message = f"Hello {name}, you have {count} messages"

# GOOD: Format specifiers
price = 19.99
print(f"Price: ${price:.2f}")

# GOOD: Debug mode (Python 3.8+)
print(f"{price=}")  # Output: price=19.99
```
