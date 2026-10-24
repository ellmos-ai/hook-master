#!/usr/bin/env python3
"""Codex PreToolUse guard for literal Python files launched by file association.

This is a candidate hook source. It is not installed by importing this module.
Codex's Bash matcher also covers unified exec; exit 2 blocks the pending call.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from typing import Any

_WORDS = re.compile(r'''"(?:`.|[^"])*"|'(?:''|[^'])*'|\S+''')
_PY_FILE = re.compile(r"\.py$", re.IGNORECASE)
_PS_SHELL = {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}
_CMD_SHELL = {"cmd", "cmd.exe"}
_START = {"start-process", "saps", "start"}
_INVOKE = {"invoke-item", "ii"}
_CMD_COMMAND = re.compile(r"^cmd(?:\.exe)?\s+/(?:c|k)\s+(.+)$", re.IGNORECASE)
_START_VALUE_OPTIONS = {
    "-argumentlist", "-credential", "-environment", "-redirectstandarderror",
    "-redirectstandardinput", "-redirectstandardoutput", "-verb",
    "-windowstyle", "-workingdirectory",
}


def _unquote(word: str) -> str:
    if len(word) >= 2 and word[0] == word[-1] and word[0] in "\"'":
        return word[1:-1]
    return word


def _is_python_file(word: str) -> bool:
    return bool(_PY_FILE.search(_unquote(word).strip()))


def _segments(command: str) -> Iterable[str]:
    """Split shell statements outside quotes; leave PowerShell's call operator intact."""
    quote = ""
    current: list[str] = []
    index = 0
    while index < len(command):
        char = command[index]
        if char == "`" and index + 1 < len(command):
            current.extend((char, command[index + 1]))
            index += 2
            continue
        if quote:
            if char == quote:
                if quote == "'" and index + 1 < len(command) and command[index + 1] == "'":
                    current.extend((char, char))
                    index += 2
                    continue
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (not current or current[-1].isspace()):
            # A PowerShell comment consumes the rest of the line, including
            # semicolons that would otherwise look like command separators.
            while index < len(command) and command[index] not in "\r\n":
                index += 1
            continue
        elif char in ";\r\n|{}()" or command[index:index + 2] == "&&":
            segment = "".join(current).strip()
            if segment:
                yield segment
            current = []
            if command[index:index + 2] == "&&":
                index += 2
                continue
            index += 1
            continue
        current.append(char)
        index += 1
    segment = "".join(current).strip()
    if segment:
        yield segment


def _file_argument(
    words: list[str], switches: tuple[str, ...], value_options: frozenset[str] = frozenset(),
) -> str | None:
    for index, word in enumerate(words[1:], 1):
        if word.lower() in switches and index + 1 < len(words):
            return words[index + 1]
    index = 1
    while index < len(words):
        word = words[index]
        if word.startswith("-"):
            index += 2 if word.lower() in value_options else 1
            continue
        if word.startswith("/"):
            index += 1
            continue
        return word
    return None


def _bad_words(words: list[str]) -> bool:
    if not words:
        return False
    head = _unquote(words[0]).lower()
    if head == "&":
        return len(words) > 1 and _is_python_file(words[1])
    if head.startswith("&"):
        return False  # Without whitespace this is not PowerShell's call operator.
    if _is_python_file(words[0]):
        return True
    if head in _START:
        path = _file_argument(words, ("-filepath",), frozenset(_START_VALUE_OPTIONS))
        if head == "start" and (path is None or not _unquote(path)):
            path = next((w for w in words[1:] if not w.startswith("/") and _unquote(w)), None)
        return path is not None and _is_python_file(path)
    if head in _INVOKE:
        path = _file_argument(words, ("-path", "-literalpath"))
        return path is not None and _is_python_file(path)
    if head in _CMD_SHELL:
        index = next((i for i, w in enumerate(words[1:], 1) if w.lower() in ("/c", "/k")), None)
        if index is None or index + 1 >= len(words):
            return False
        tail = words[index + 1:]
        if len(tail) == 1:
            return _bad_command(_unquote(tail[0]))
        if _unquote(tail[0]).lower() != "start":
            return _bad_words(tail)
        return any(_is_python_file(w) for w in tail[1:] if not w.startswith("/"))
    if head in _PS_SHELL:
        index = next((i for i, w in enumerate(words[1:], 1)
                      if w.lower() in ("-command", "-c", "-encodedcommand")), None)
        if index is not None and index + 1 < len(words) and words[index].lower() != "-encodedcommand":
            return _bad_command(_unquote(" ".join(words[index + 1:])))
    return False


def _bad_command(command: str) -> bool:
    for segment in _segments(command):
        if segment.startswith("#"):
            continue
        nested_cmd = _CMD_COMMAND.match(segment)
        if nested_cmd:
            tail = nested_cmd.group(1)
            if tail.startswith('"') and tail.endswith('"'):
                tail = tail[1:-1]
            if _bad_command(tail):
                return True
            continue
        if _bad_words(_WORDS.findall(segment)):
            return True
    return False


def blocking_reason(payload: Any) -> str:
    """Return a reason only for recognizable interpreterless literal launches."""
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd"):
        value = tool_input.get(key)
        if isinstance(value, str) and _bad_command(value):
            return "PYTHON-EXEC-GUARD: .py-Datei ohne Python-Interpreter gestartet; python.exe <skript.py> verwenden."
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            if _bad_words(value) or (len(value) == 1 and _bad_command(value[0])):
                return "PYTHON-EXEC-GUARD: .py-Datei ohne Python-Interpreter gestartet; python.exe <skript.py> verwenden."
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    reason = blocking_reason(payload)
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
