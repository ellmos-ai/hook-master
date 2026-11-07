#!/usr/bin/env python3
r"""Claude Code PreToolUse guard: backslash content that is destroyed in transit.

Measured 2026-11-07 with Claude Code's Bash tool on Windows (Git Bash): the tool
turns `\\` into `\` before bash runs, also inside '...' and <<'EOF' heredocs
(`printf '%s' 'A\\B'` prints `A\B`; a Python argv check got 3 instead of 4
characters). Single backslashes arrive unchanged, but Python then turns `\r`
`\t` `\n` `\a` `\b` `\f` in ordinary string literals into control characters
without a warning. Doubling therefore never protects a Windows path such as
`C:\work\repos`: the tool undoes the doubling and Python eats `\r`. The
PowerShell tool was measured not to halve backslashes. Other hosts and
providers are not measured.

Blocks (exit 2, reason on stderr) when the command contains `\\` or a drive
path with a backslash (`C:\...`). Bypass on purpose: put `# backslash-ok` in
the command. Fails open on any internal error: this guard prevents silent
data corruption, it is not a security boundary.
"""
import json
import re
import sys

RISK = re.compile(r"\\\\|\b[A-Za-z]:\\")
BYPASS = "# backslash-ok"
MSG = (
    "BLOCKED (backslash_guard): the Bash tool turns '\\\\' into '\\' before bash runs "
    "(also inside '...' and <<'EOF'). Python then turns \\r \\t \\n \\a \\b \\f in ordinary "
    "string literals into control characters, so doubling does not protect. Instead: write "
    "paths with / (C:/path/to/dir), put backslash content into a file with the Write tool, "
    "or use the PowerShell tool (it does not halve). If intended, add '# backslash-ok'."
)


def verdict(cmd: str) -> bool:
    """True = block."""
    return BYPASS not in cmd and bool(RISK.search(cmd))


def main() -> int:
    try:
        cmd = (json.loads(sys.stdin.read() or "{}").get("tool_input") or {}).get("command") or ""
    except Exception:
        return 0
    if verdict(cmd):
        print(MSG, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        assert verdict(r"python - <<'EOF'" "\n" r'p = "C:\work\repos"')
        assert verdict(r"printf '%s' 'A\\B'")
        assert not verdict("ls C:/work/repos && grep -n 'a\\.b' f")
        assert not verdict(r"echo 'C:\x' # backslash-ok")
        assert not verdict(r"sed -n 's/\n//' f")
        print("selftest ok")
        sys.exit(0)
    sys.exit(main())
