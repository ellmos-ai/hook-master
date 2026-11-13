#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SessionStart hook: a real MCP update check, at most once a day per host.

Replaces the placeholder `echo 'MCP update check done'`, which reported a check
that never ran (found 2026-11-13; the first real run that day was RED).

- Starts `mcp_npm_check.py` (read-only, never `--apply`) at most once per 20 h
  as a detached background process. The check takes about a minute (one
  `npm view` per package plus the MCP registry), so it never runs inline.
- On session start it prints one line with the result of the last finished
  run, separating: locally outdated (fixed by `--apply`), MCP registry behind
  npm (publication pending) and repo version != npm (release pending).
- State lives host-locally in `~/.claude/mcp_npm_check/` (never in a synced
  folder: conflict copies). The result file is replaced atomically after the
  run ends; a run is cut off after 900 s.
- Never breaks session start: every error becomes one text line, exit 0.

Check script lookup (first existing wins): env `MCP_UPDATE_CHECK_SCRIPT`,
`../scripts/mcp_npm_check.py` next to this hook (ellmos `.SYNC` layout),
`~/OneDrive/.SYNC/scripts/mcp_npm_check.py`.

Usage: (no argument) hook  |  --run  check now, synchronously  |  --selftest
"""
import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

STATE = Path.home() / ".claude" / "mcp_npm_check"
LOG = STATE / "last.log"
STAMP = STATE / "started.txt"
MAX_AGE_S = 20 * 3600  # ponytail: fixed daily window; make it configurable when a host needs it
RUN_TIMEOUT_S = 900


def check_script() -> Path:
    candidates = [
        os.environ.get("MCP_UPDATE_CHECK_SCRIPT", ""),
        Path(__file__).resolve().parents[1] / "scripts" / "mcp_npm_check.py",
        Path.home() / "OneDrive" / ".SYNC" / "scripts" / "mcp_npm_check.py",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return Path(candidates[1])


def summarize(text: str, when: str, check: Path) -> str:
    total = next((l.split(":", 1)[1].strip() for l in text.splitlines() if l.startswith("GESAMT:")), None)
    if total is None:
        return f"MCP-Update-Check ({when}): Lauf unvollstaendig, siehe {LOG}"
    if total.startswith("GR"):
        return f"MCP-Update-Check ({when}): GRUEN, alle eigenen MCP-Pakete aktuell."
    lines = text.splitlines()
    stale = [l.split() for l in lines if l.strip().startswith("VERALTET") and len(l.split()) > 2]
    local = sorted({w[1] for w in stale if any(x.startswith("installiert=") for x in w)})
    registry = sorted({w[1] for w in stale if any(x.startswith("mcp-registry=") for x in w)})
    release = next((l.rsplit(":", 1)[1].strip() for l in lines if l.startswith("Paket auf npm ver")), "")
    red = [l.split(":", 1)[0].strip() for l in lines if l.startswith("  ") and ": ROT" in l]
    parts = [f"MCP-Update-Check ({when}): {total}"]
    if red:
        parts.append("rote Gates: " + ", ".join(red))
    if local:
        parts.append(f"lokal veraltet: {', '.join(local)} -> python \"{check}\" --apply")
    if registry:
        parts.append("MCP-Registry hinkt npm nach (Veroeffentlichung offen): " + ", ".join(registry))
    if release:
        parts.append("Repo-Version != npm (Release offen): " + release)
    parts.append(f"Details: {LOG}")
    return " | ".join(parts)


def report(check: Path, starting: bool) -> str:
    if not check.is_file():
        return f"MCP-Update-Check: Pruefskript fehlt ({check}); MCP_UPDATE_CHECK_SCRIPT setzen."
    if not LOG.is_file():
        if starting:
            return "MCP-Update-Check: noch kein Ergebnis, Lauf im Hintergrund gestartet."
        return f"MCP-Update-Check: noch kein Ergebnis; Lauf laeuft noch oder brach ohne Ergebnis ab (siehe {STATE})."
    when = datetime.datetime.fromtimestamp(LOG.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return summarize(LOG.read_text(encoding="utf-8", errors="replace"), when, check)


def due() -> bool:
    return not STAMP.is_file() or time.time() - STAMP.stat().st_mtime > MAX_AGE_S


def spawn() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(datetime.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # ponytail: two sessions starting in the same instant may both spawn; harmless (read-only check).
    subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--run"], **kwargs)


def run(check: Path) -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = LOG.with_suffix(".tmp")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with tmp.open("w", encoding="utf-8") as out:
        try:
            subprocess.run([sys.executable, "-X", "utf8", str(check)], stdout=out, stderr=subprocess.STDOUT,
                           env=env, timeout=RUN_TIMEOUT_S, check=False,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            out.write(f"\nGESAMT: ABBRUCH (Timeout {RUN_TIMEOUT_S} s)\n")
    os.replace(tmp, LOG)
    return 0


def selftest() -> int:
    check = Path("check.py")
    green = "  aktuell   x\nGESAMT: GRÜN\n"
    red = ("  VERALTET  ellmos-servercommander-mcp   installiert=1 npm=2 repo=2\n"
           "  VERALTET  ellmos-homebase-mcp          mcp-registry=1 npm=2\n"
           "  Registry-Aktualität: ROT (veraltet=1, unklar=0)\nGESAMT: ROT\n"
           "Paket auf npm veröffentlicht, aber Repo-Version != npm latest (Release offen: x): ellmos-filecommander-mcp\n")
    assert "GRUEN" in summarize(green, "t", check)
    s = summarize(red, "t", check)
    assert "lokal veraltet: ellmos-servercommander-mcp" in s, s
    assert "hinkt npm nach (Veroeffentlichung offen): ellmos-homebase-mcp" in s, s
    assert "Release offen): ellmos-filecommander-mcp" in s and "Registry-Aktualität" in s, s
    assert "unvollstaendig" in summarize("halber Lauf", "t", check)
    print("selftest ok")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    check = check_script()
    if "--run" in sys.argv:
        return run(check)
    if "--selftest" in sys.argv:
        return selftest()
    try:
        starting = check.is_file() and due()
        message = report(check, starting)
        if starting:
            spawn()
        print(message)
    except Exception as error:  # a hook must never break session start
        print(f"MCP-Update-Check: Hook-Fehler {type(error).__name__}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
