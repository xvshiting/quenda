#!/usr/bin/env python3
"""Divide numbers. First number is dividend, last is divisor (intermediate form chain)."""

import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: python divide.py <dividend> <divisor> [more divisors...]")
        sys.exit(1)

    try:
        numbers = [float(arg) for arg in sys.argv[1:]]
    except ValueError as e:
        print(f"Error: Invalid number provided - {e}")
        sys.exit(1)

    # Check for division by zero
    if 0 in numbers[1:]:
        print("Error: Division by zero")
        sys.exit(1)

    result = numbers[0]
    for n in numbers[1:]:
        result = result / n

    # Return integer if result is a whole number
    if result == int(result):
        print(int(result))
    else:
        print(result)


if __name__ == "__main__":
    main()
