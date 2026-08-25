#!/usr/bin/env python3
"""Fail-open PreCompact fallback that saves recent user context to USMC."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from collections import deque
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_USMC_DB = r"C:\Users\User\.usmc\usmc_memory.db"
AGENT_ID = "claude-code"
RESUME_MARKER = "RESUME-PUNKT"
FRESH_MINUTES = 90
MESSAGE_LIMIT = 12
MESSAGE_CHAR_LIMIT = 300
SESSION_ID_LIMIT = 16
SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder\b[^>]*>.*?</system-reminder\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)


def _ensure_utf8_stdio() -> None:
    """Force hook output to UTF-8 even when the Windows console uses cp1252."""
    for stream in (sys.stdout, sys.stderr):
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _clean_user_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = SYSTEM_REMINDER_RE.sub("", value)
    if text.lstrip().casefold().startswith("<system-reminder"):
        return ""
    return " ".join(text.split())


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return _clean_user_text(content)
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            text = _clean_user_text(block)
        elif isinstance(block, dict):
            block_type = str(block.get("type") or "").casefold().replace("_", "-")
            if block_type in {"tool-result", "system-reminder"}:
                continue
            if block_type not in {"", "text", "input-text", "user-text"}:
                continue
            text = _clean_user_text(block.get("text"))
        else:
            continue
        if text:
            parts.append(text)
    return " ".join(parts)


def _user_text_from_record(record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    message = record.get("message")
    payload = message if isinstance(message, dict) else record
    if str(payload.get("role") or "").casefold() != "user":
        return ""
    return _text_from_content(payload.get("content"))


def _recent_user_messages(transcript_path: Any) -> list[str]:
    if not isinstance(transcript_path, str) or not transcript_path.strip():
        return []

    messages: deque[str] = deque(maxlen=MESSAGE_LIMIT)
    try:
        with open(transcript_path, "r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    text = _user_text_from_record(json.loads(line))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if not text:
                    continue
                if len(text) > MESSAGE_CHAR_LIMIT:
                    text = text[: MESSAGE_CHAR_LIMIT - 1].rstrip() + "…"
                messages.append(text)
    except (OSError, UnicodeError):
        return []
    return list(messages)


def _short_session_id(value: Any) -> str:
    session_id = " ".join(str(value or "unbekannt").split())
    return session_id[:SESSION_ID_LIMIT] or "unbekannt"


def _build_content(payload: dict[str, Any], now: datetime) -> str:
    timestamp = now.isoformat()
    session_id = _short_session_id(payload.get("session_id"))
    messages = _recent_user_messages(payload.get("transcript_path"))
    if messages:
        body = "\n".join(f"- {message}" for message in messages)
    else:
        body = "- Keine verwertbaren Nutzernachrichten im Transkript."
    return (
        "AUTO-STATE (PreCompact, kein frischer RESUME-PUNKT) "
        f"{timestamp} sitzung={session_id}:\n{body}"
    )


def _save_if_needed(payload: dict[str, Any]) -> str:
    db_path = Path(os.environ.get("USMC_DB") or DEFAULT_USMC_DB)
    if not db_path.is_file():
        return ""

    now = datetime.now()
    cutoff = (now - timedelta(minutes=FRESH_MINUTES)).isoformat()
    with closing(sqlite3.connect(db_path, timeout=5.0)) as connection:
        fresh_resume = connection.execute(
            """
            SELECT 1
            FROM usmc_working
            WHERE agent_id = ?
              AND instr(content, ?) > 0
              AND created_at > ?
            LIMIT 1
            """,
            (AGENT_ID, RESUME_MARKER, cutoff),
        ).fetchone()
        if fresh_resume is not None:
            return "Frischer RESUME-PUNKT vorhanden; kein AUTO-STATE geschrieben."

    content = _build_content(payload, now)
    timestamp = now.isoformat()
    with closing(sqlite3.connect(db_path, timeout=5.0)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        fresh_resume = connection.execute(
            """
            SELECT 1
            FROM usmc_working
            WHERE agent_id = ?
              AND instr(content, ?) > 0
              AND created_at > ?
            LIMIT 1
            """,
            (AGENT_ID, RESUME_MARKER, cutoff),
        ).fetchone()
        if fresh_resume is not None:
            connection.rollback()
            return "Frischer RESUME-PUNKT vorhanden; kein AUTO-STATE geschrieben."
        connection.execute(
            """
            INSERT INTO usmc_working
                (type, content, priority, tags, agent_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "note",
                content,
                8,
                "auto-state,precompact,resume-fallback",
                AGENT_ID,
                1,
                timestamp,
                timestamp,
            ),
        )
        connection.commit()
    return "AUTO-STATE in USMC gespeichert."


def main() -> int:
    _ensure_utf8_stdio()
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            return 0
        payload = json.loads(raw_input)
        if not isinstance(payload, dict):
            return 0
        message = _save_if_needed(payload)
        if message:
            print(message)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    raise SystemExit(0)
