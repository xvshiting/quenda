---
name: calculate-nums
description: Perform mathematical calculations (add, subtract, multiply, divide) on two or more numbers. Use when user asks to compute, calculate, or perform math operations on numbers.
version: "1.0.0"

quenda:
  resources:
    assets:
      - path: "scripts/add.py"
        description: "Add two or more numbers"
        type: script
      - path: "scripts/subtract.py"
        description: "Subtract numbers"
        type: script
      - path: "scripts/multiply.py"
        description: "Multiply two or more numbers"
        type: script
      - path: "scripts/divide.py"
        description: "Divide numbers"
        type: script
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
3. **Run the appropriate script** - Check the "Skill Resources" section below for the **absolute path** of each script, then execute it

### Available Scripts

| Script | Operation | Usage |
|--------|-----------|-------|
| `add.py` | Addition | `python <path_to_add.py> 1 2 3` |
| `subtract.py` | Subtraction | `python <path_to_subtract.py> 10 3 2` |
| `multiply.py` | Multiplication | `python <path_to_multiply.py> 2 3 4` |
| `divide.py` | Division | `python <path_to_divide.py> 20 4` |

**Important**: Use the absolute paths from the "Skill Resources" section, NOT relative paths like `scripts/add.py`.

### Usage Pattern

```bash
python <absolute_script_path> <number1> <number2> [number3...]
```

## Examples

**User**: "What is 15 + 27 + 8?"
```bash
# Use the absolute path from Skill Resources section
python /path/to/add.py 15 27 8
# Result: 50
```

**User**: "Calculate 100 minus 35 minus 12"
```bash
python /path/to/subtract.py 100 35 12
# Result: 53
```

**User**: "Multiply 7, 8, and 9"
```bash
python /path/to/multiply.py 7 8 9
# Result: 504
```

**User**: "What's 144 divided by 12?"
```bash
python /path/to/divide.py 144 12
# Result: 12.0
```

## Notes

- For subtraction: the first number is the starting value, subsequent numbers are subtracted from it
- For division: the first number is the dividend, the last number is the divisor
- Division by zero will return an error
- Results are returned as integers when possible, floats when necessary
