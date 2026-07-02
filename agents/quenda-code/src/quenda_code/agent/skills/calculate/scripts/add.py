#!/usr/bin/env python3
"""Add two or more numbers."""

import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python add.py <number1> <number2> [number3...]")
        sys.exit(1)

    try:
        numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError as e:
        print(f"Error: Invalid number provided - {e}")
        sys.exit(1)

    result = sum(numbers)

    # Return integer if result is a whole number
    if result == int(result):
        print(int(result))
    else:
        print(result)


if __name__ == "__main__":
    main()
