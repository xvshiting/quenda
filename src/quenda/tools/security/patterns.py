"""
Security patterns for Quenda tools.
"""

from __future__ import annotations

# =============================================================================
# Shell Security Patterns
# =============================================================================

SHELL_BLOCKED_COMMANDS: list[str] = [
    # Filesystem destruction
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\*",
    r"rm\s+-fr\s+/",
    r"rm\s+-fr\s+~",
    # Disk operations
    r"mkfs",
    r"dd\s+if=.*of=/dev/",
    r">\s*/dev/sd",
    r">\s*/dev/hd",
    # Fork bomb
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
    r":\(\)\{\s*:\|:&\s*\}\s*;:",
    # Dangerous chmod
    r"chmod\s+(-R\s+)?777\s+/",
    r"chmod\s+(-R\s+)?777\s+~",
    # Shutdown/reboot
    r"shutdown",
    r"reboot",
    r"init\s+[06]",
    # User management
    r"userdel",
    r"passwd\s+--",
    # Network dangerous
    r"iptables\s+-F",
    r"iptables\s+-P\s+INPUT\s+DROP",
]

SHELL_BLOCKED_ENV_VARS: list[str] = [
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "PYTHONPATH",
]


# =============================================================================
# Network Security Patterns
# =============================================================================

NETWORK_BLOCKED_IP_RANGES: list[str] = [
    # IPv4 private ranges
    "10.0.0.0/8",  # Class A private
    "172.16.0.0/12",  # Class B private
    "192.168.0.0/16",  # Class C private
    "127.0.0.0/8",  # Localhost
    "169.254.0.0/16",  # Link-local (AWS metadata)
    "0.0.0.0/8",  # Current network
    # IPv6
    "::1/128",  # IPv6 localhost
    "fc00::/7",  # IPv6 ULA
    "fe80::/10",  # IPv6 link-local
]

NETWORK_BLOCKED_DOMAINS: list[str] = [
    "localhost",
    "localhost.localdomain",
    "local",
    "internal",
    "*.internal",  # Block all .internal domains
    "*.local",  # Block all .local domains
    "metadata.google.internal",
    "metadata",
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
]

NETWORK_BLOCKED_HEADERS: list[str] = [
    "Authorization",
    "Cookie",
    "Set-Cookie",
    "X-Forwarded-For",
    "X-Real-IP",
    "Proxy-Authorization",
]

NETWORK_ALLOWED_SCHEMES: list[str] = ["http", "https"]


# =============================================================================
# Code Execution Security Patterns
# =============================================================================

SANDBOX_ALLOWED_MODULES: list[str] = [
    # Standard library - safe
    "math",
    "random",
    "statistics",
    "itertools",
    "functools",
    "collections",
    "datetime",
    "time",  # Required by datetime
    "re",
    "json",
    "csv",
    "typing",
    "dataclasses",
    "enum",
    "copy",
    "decimal",
    "fractions",
    "numbers",
    "string",
    "textwrap",
    "unicodedata",
    "hashlib",
    "base64",
    "hmac",
    "pprint",
    "operator",
    "pathlib",
    # Data science (optional, may not be installed)
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
]

SANDBOX_BLOCKED_MODULES: list[str] = [
    # System access
    "os",
    "sys",
    "subprocess",
    "socket",
    "socketserver",
    "select",
    "selectors",
    # Multiprocessing/threading
    "multiprocessing",
    "threading",
    "_thread",
    "concurrent",
    "asyncio",
    # Code execution
    "importlib",
    "pkgutil",
    "code",
    "codeop",
    "compileall",
    # Serialization (security risk)
    "pickle",
    "shelve",
    "marshal",
    "imp",
    # Native code
    "ctypes",
    "cffi",
    "winreg",
    "posix",
    "nt",
    # File system
    "shutil",
    "tempfile",
    "glob",
    # Network
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "poplib",
    "imaplib",
    "nntplib",
    "telnetlib",
]

SANDBOX_ALLOWED_BUILTINS: list[str] = [
    # Basic types and conversions
    "abs",
    "all",
    "any",
    "bin",
    "bool",
    "chr",
    "complex",
    "dict",
    "divmod",
    "float",
    "format",
    "frozenset",
    "hex",
    "int",
    "oct",
    "ord",
    "pow",
    "repr",
    "round",
    "set",
    "str",
    "tuple",
    "type",
    # Iteration
    "enumerate",
    "filter",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "range",
    "reversed",
    "slice",
    "sorted",
    "sum",
    "zip",
    # Inspection
    "dir",
    "hasattr",
    "id",
    "isinstance",
    "issubclass",
    # Constants
    "True",
    "False",
    "None",
    "Ellipsis",
    # Exceptions
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "StopIteration",
    "AttributeError",
    "NameError",
    "ZeroDivisionError",
    "ImportError",
    "ModuleNotFoundError",
    "FileNotFoundError",
    "OSError",
    "IOError",
    "PermissionError",
    "TimeoutError",
    "RecursionError",
    "MemoryError",
    "NotImplementedError",
    "ArithmeticError",
    "LookupError",
    "AssertionError",
    # I/O (safe version)
    "print",
]
