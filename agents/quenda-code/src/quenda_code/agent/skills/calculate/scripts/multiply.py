#!/usr/bin/env python3
"""Multiply two or more numbers."""

import sys
from functools import reduce
import operator


def main():
    if len(sys.argv) < 2:
        print("Usage: python multiply.py <number1> <number2> [number3...]")
        sys.exit(1)

    try:
        numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError as e:
        print(f"Error: Invalid number provided - {e}")
        sys.exit(1)

    result = reduce(operator.mul, numbers, 1)

    # Return integer if result is a whole number
    if result == int(result):
        print(int(result))
    else:
        print(result)


if __name__ == "__main__":
    main()
