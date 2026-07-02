#!/usr/bin/env python3
"""Subtract numbers. First number is the starting value, rest are subtracted from it."""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python subtract.py <start> <number1> [number2...]")
        sys.exit(1)

    try:
        numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError as e:
        print(f"Error: Invalid number provided - {e}")
        sys.exit(1)

    result = numbers[0]
    for n in numbers[1:]:
        result -= n

    # Return integer if result is a whole number
    if result == int(result):
        print(int(result))
    else:
        print(result)


if __name__ == "__main__":
    main()
