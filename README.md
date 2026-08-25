[![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen)]() [![Version](https://img.shields.io/badge/version-0.1.0-blue)]() [![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)]() [![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]() [![Privacy](https://img.shields.io/badge/privacy-100%25%20Offline%20%7C%20Zero--Egress-success)]() [![Security](https://img.shields.io/badge/security-Local--First-success)]() [![Ecosystem](https://img.shields.io/badge/ecosystem-ellmos--ai-blueviolet)]() [![Umbrella](https://img.shields.io/badge/umbrella-open--bricks-informational)]() [![LLM-Ready](https://img.shields.io/badge/LLM--Ready-llms.txt-orange)](llms.txt)

# hook-master

[English](README.md) | [Deutsch](README_de.md)

> [!NOTE]
> This repository ships an [`llms.txt`](llms.txt) discovery file for AI agents/LLMs.

Local-first pointer registry and one-way materialization for agent hooks
(Claude Code, Codex, Kimi, Antigravity, ...). Built as a sibling to
[`policy-registry`](https://github.com/ellmos-ai/policy-registry) — same
mechanic (pointer-only registry, optional `system-gap-master` transport,
fully standalone without the wider ecosystem), applied to a structurally
different domain: hooks are **executable code**, not text, so this module
adds an explicit `deploy`/`diff`/`status` materialization step that a pure
text registry does not need.

## Why

A hook registered in one agent's config can silently depend on a file that
lives in a *different* agent's private directory. That is not hypothetical
here: before this module existed, Codex's `~/.codex/hooks.json` pointed its
`PreToolUse` guard straight at `C:/Users/<user>/.claude/hooks/guards.py` — a
Claude-Code-owned path Codex has no reason to know about. `hook-master`
fixes the general problem, not just that one instance: hooks get a
canonical home (`library/`), a pointer registry that knows every agent that
consumes them, and a materialization step that copies the canonical file to
wherever each agent's config actually expects it — one direction only,
canonical → deployed, never the reverse.

## Quick start

```bash
pip install -e .
hook-master init
hook-master register my-hook.json
hook-master verify           # canonical file hash matches the registry?
hook-master deploy            # copy canonical -> every registered deploy_path
hook-master diff              # read-only: in-sync / drifted / not-deployed?
hook-master status            # verify + diff combined
```

## Entry model

Every registry entry is metadata only — never script text (`model.py`
rejects `content`/`body`/`script_text` fields outright). Two kinds:

- **`kind: "hook"`** — a concrete script. `source.kind: "canonical"` means
  the script lives in this module (`source.uri` + `source.hash`, SHA-256).
  Each `targets[]` entry names an `agent`, its `config_path`, and (for
  canonical hooks) a `deploy_path` — the materialized copy's location.
- **`kind: "consumer"`** — a registered *module* that owns its own hook
  registration logic entirely (currently: `memoryhooker`, `workflowhooker`,
  both via `source.kind: "external-module"`). `hook-master` catalogues that
  it exists and which agents/events it covers; it never re-implements or
  wraps the consumer's own logic.

Reserved, not yet enforced (planned follow-up, "HE2" — Hook-Doctor +
Consent-Allowlist): an optional `doctor` object per entry
(`exec_check`, `mtime_policy`, `allowlist`). The schema validates these
fields' shape today so a doctor check can attach later without a second
schema migration; nothing evaluates them yet.

## Commands

| Command | Effect |
|---|---|
| `init` | Create an empty registry at the default (or `--registry`) path |
| `register <entry.json>` | Add/replace one entry |
| `list` / `get <id>` / `search [query]` | Read the registry |
| `verify` | Hash-check every canonical entry's source file |
| `deploy [--id <id>] [--dry-run]` | Copy canonical → deploy_path for matching entries |
| `diff [--id <id>]` | Read-only: report in-sync / drifted / not-deployed, no writes |
| `status` | `verify` + `diff` combined |
| `import-sync --root <dir> --slot <slot>` | One-time migration: pull `kind=consumer` pointers from an existing `.SYNC/hooks/adoption/<slot>.json` layout |
| `export-sync-view --root <dir> --slot <slot>` | Optional: publish a metadata-only view into `.SYNC/hooks/registry/<slot>.json` |

## Optional transport, never required

`adapters/system_gap.py` only activates if `system_gap_master` is
importable. The registry — and every command above — works fully offline
and standalone without it, exactly like `policy-registry`
(D-20260728-001: "system-gap-master is only an optional transport
adapter"). A single-machine setup with no `.SYNC` folder at all is a fully
supported configuration, not a degraded one.

## Sibling tools & ecosystem

Within the `ellmos-ai` / `open-bricks` ecosystem: [`policy-registry`](https://github.com/ellmos-ai/policy-registry) (architectural sibling — same mechanic for policies/rules instead of hooks), [`memoryhooker`](https://github.com/ellmos-ai/memoryhooker) and [`workflowhooker`](https://github.com/ellmos-ai/workflowhooker) (registered `kind=consumer` entries — their own domain logic stays with them), [`system-gap-master`](https://github.com/ellmos-ai/system-gap-master) (the optional transport this module can seam into), [`source-resolver`](https://github.com/ellmos-ai/source-resolver) (role → provider resolution, a related but distinct mechanic), [`lock-master`](https://github.com/ellmos-ai/lock-master), [`ticket-master`](https://github.com/ellmos-ai/ticket-master), [`DevCenter`](https://github.com/dev-bricks/DevCenter), [`CodeBox`](https://github.com/dev-bricks/CodeBox).

## Security

See [SECURITY.md](SECURITY.md) — local-first, zero-egress, pointer-only
registry (never script text), one-way materialization, non-elevation.

## License

MIT — see [LICENSE](LICENSE).
