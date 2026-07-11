---
name: calculate-nums
description: Perform mathematical calculations (add, subtract, multiply, divide) on two or more numbers. Use when user asks to compute, calculate, or perform math operations on numbers.
version: "1.0.0"
---

# Calculate

Perform accurate mathematical calculations using Python scripts.

## When to Use

Use this skill when the user asks you to:
- Add, sum, or combine numbers
- Subtract or find the difference between numbers
- Multiply or find the product of numbers
- Divide or find the quotient of numbers
- Perform any arithmetic operation on two or more numbers

## How to Use

1. **Identify the operation** - Determine if the user wants add, subtract, multiply, or divide
2. **Extract the numbers** - Get all numbers from the user's request
3. **Execute the script** - Use `execute_skill_asset` with the skill:// URI

### Available Scripts

| Script | Operation | URI |
|--------|-----------|-----|
| `add.py` | Addition | `skill://calculate-nums/scripts/add.py` |
| `subtract.py` | Subtraction | `skill://calculate-nums/scripts/subtract.py` |
| `multiply.py` | Multiplication | `skill://calculate-nums/scripts/multiply.py` |
| `divide.py` | Division | `skill://calculate-nums/scripts/divide.py` |

### Usage Pattern

```
execute_skill_asset(uri="skill://calculate-nums/scripts/add.py", arguments=["15", "27", "8"])
```

## Examples

**User**: "What is 15 + 27 + 8?"
```
execute_skill_asset(uri="skill://calculate-nums/scripts/add.py", arguments=["15", "27", "8"])
# Result: 50
```

**User**: "Calculate 100 minus 35 minus 12"
```
execute_skill_asset(uri="skill://calculate-nums/scripts/subtract.py", arguments=["100", "35", "12"])
# Result: 53
```

**User**: "Multiply 7, 8, and 9"
```
execute_skill_asset(uri="skill://calculate-nums/scripts/multiply.py", arguments=["7", "8", "9"])
# Result: 504
```

**User**: "What's 144 divided by 12?"
```
execute_skill_asset(uri="skill://calculate-nums/scripts/divide.py", arguments=["144", "12"])
# Result: 12
```

## Notes

- For subtraction: the first number is the starting value, subsequent numbers are subtracted from it
- For division: the first number is the dividend, the last number is the divisor
- Division by zero will return an error
- Results are returned as integers when possible, floats when necessary
