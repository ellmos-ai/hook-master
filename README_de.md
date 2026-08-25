[![Tests](https://img.shields.io/badge/tests-37%20bestanden-brightgreen)]() [![Version](https://img.shields.io/badge/version-0.1.0-blue)]() [![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)]() [![Plattform](https://img.shields.io/badge/plattform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]() [![Datenschutz](https://img.shields.io/badge/datenschutz-100%25%20Offline%20%7C%20Zero--Egress-success)]() [![Sicherheit](https://img.shields.io/badge/sicherheit-Local--First-success)]() [![Ökosystem](https://img.shields.io/badge/ökosystem-ellmos--ai-blueviolet)]() [![Dachverband](https://img.shields.io/badge/dachverband-open--bricks-informational)]() [![LLM-Ready](https://img.shields.io/badge/LLM--Ready-llms.txt-orange)](llms.txt)

# hook-master

[English](README.md) | [Deutsch](README_de.md)

> [!NOTE]
> Dieses Repository liefert eine [`llms.txt`](llms.txt)-Discovery-Datei für KI-Agenten/LLMs.

Lokale, pointer-basierte Registry mit Einweg-Materialisierung für Agenten-Hooks
(Claude Code, Codex, Kimi, Antigravity, ...). Gebaut als Schwestermodul zu
[`policy-registry`](https://github.com/ellmos-ai/policy-registry) — dieselbe
Mechanik (reine Zeiger-Registry, optionaler `system-gap-master`-Transport,
vollständig eigenständig ohne das übrige Ökosystem lauffähig), angewendet auf
eine strukturell andere Domäne: Hooks sind **ausführbarer Code**, kein Text —
deshalb bringt dieses Modul einen expliziten `deploy`/`diff`/`status`-
Materialisierungsschritt mit, den eine reine Text-Registry nicht braucht.

## Warum

Ein in der Config eines Agenten registrierter Hook kann still von einer Datei
abhängen, die im **privaten** Verzeichnis eines ANDEREN Agenten liegt. Das ist
hier kein Hypothetisches: Bevor dieses Modul existierte, zeigte Codex'
`~/.codex/hooks.json` seinen `PreToolUse`-Guard direkt auf
`C:/Users/<user>/.claude/hooks/guards.py` — einen Pfad, den Codex nur kennt,
weil er zufällig da war. `hook-master` behebt das allgemeine Problem, nicht
nur diesen einen Fall: Hooks bekommen ein kanonisches Zuhause (`library/`),
eine Zeiger-Registry, die jeden konsumierenden Agenten kennt, und einen
Materialisierungsschritt, der die kanonische Datei genau dorthin kopiert, wo
die Config jedes Agenten sie tatsächlich erwartet — nur in eine Richtung,
kanonisch → materialisiert, nie umgekehrt.

## Schnellstart

```bash
pip install -e .
hook-master init
hook-master register my-hook.json
hook-master verify           # stimmt der Hash der kanonischen Datei mit der Registry?
hook-master deploy            # kanonisch -> jeden registrierten deploy_path kopieren
hook-master diff              # nur lesend: in-sync / drifted / not-deployed?
hook-master status            # verify + diff kombiniert
```

## Eintragsmodell

Jeder Registry-Eintrag ist reine Metadatensache — nie Skript-Text
(`model.py` weist `content`/`body`/`script_text`-Felder rundweg zurück). Zwei
Arten:

- **`kind: "hook"`** — ein konkretes Skript. `source.kind: "canonical"`
  bedeutet, das Skript lebt in diesem Modul (`source.uri` + `source.hash`,
  SHA-256). Jeder `targets[]`-Eintrag nennt einen `agent`, dessen
  `config_path` und (bei kanonischen Hooks) einen `deploy_path` — den Ort
  der materialisierten Kopie.
- **`kind: "consumer"`** — ein registriertes *Modul*, das seine eigene
  Hook-Registrierungslogik vollständig selbst besitzt (aktuell:
  `memoryhooker`, `workflowhooker`, beide über `source.kind:
  "external-module"`). `hook-master` katalogisiert nur, dass es existiert
  und welche Agenten/Events es abdeckt — es reimplementiert oder umhüllt
  die eigene Logik des Konsumenten nie.

Reserviert, noch nicht durchgesetzt (geplantes Folgeticket "HE2" —
Hook-Doctor + Consent-Allowlist): ein optionales `doctor`-Objekt je Eintrag
(`exec_check`, `mtime_policy`, `allowlist`). Das Schema validiert die Form
dieser Felder heute schon, damit ein Doctor-Check später andocken kann, ohne
eine zweite Schema-Migration zu brauchen — ausgewertet wird noch nichts.

## Befehle

| Befehl | Wirkung |
|---|---|
| `init` | Leere Registry am Standard- (oder `--registry`-) Pfad anlegen |
| `register <entry.json>` | Einen Eintrag hinzufügen/ersetzen |
| `list` / `get <id>` / `search [query]` | Registry lesen |
| `verify` | Hash-Check jedes kanonischen Eintrags gegen seine Quelldatei |
| `deploy [--id <id>] [--dry-run]` | Kanonisch → deploy_path fuer passende Einträge kopieren |
| `diff [--id <id>]` | Nur lesend: in-sync / drifted / not-deployed melden, keine Schreibvorgänge |
| `status` | `verify` + `diff` kombiniert |
| `import-sync --root <dir> --slot <slot>` | Einmalige Migration: `kind=consumer`-Zeiger aus einer bestehenden `.SYNC/hooks/adoption/<slot>.json`-Struktur übernehmen |
| `export-sync-view --root <dir> --slot <slot>` | Optional: reine Metadaten-Ansicht nach `.SYNC/hooks/registry/<slot>.json` veröffentlichen |

## Optionaler Transport, nie erforderlich

`adapters/system_gap.py` aktiviert sich nur, wenn `system_gap_master`
importierbar ist. Die Registry — und jeder Befehl oben — funktioniert
vollständig offline und eigenständig auch ohne dieses Paket, genau wie bei
`policy-registry` (D-20260728-001: „system-gap-master ist nur ein
optionaler Transportadapter"). Ein Ein-System-Setup ganz ohne `.SYNC`-Ordner
ist eine vollständig unterstützte Konfiguration, keine degradierte.

## Geschwisterwerkzeuge & Ökosystem

Innerhalb des `ellmos-ai`-/`open-bricks`-Ökosystems: [`policy-registry`](https://github.com/ellmos-ai/policy-registry) (architektonisches Schwestermodul — dieselbe Mechanik für Policies/Regeln statt Hooks), [`memoryhooker`](https://github.com/ellmos-ai/memoryhooker) und [`workflowhooker`](https://github.com/ellmos-ai/workflowhooker) (registrierte `kind=consumer`-Einträge — ihre eigene Domänenlogik bleibt bei ihnen), [`system-gap-master`](https://github.com/ellmos-ai/system-gap-master) (der optionale Transport, in den dieses Modul einhängen kann), [`source-resolver`](https://github.com/ellmos-ai/source-resolver) (Rolle → Anbieter-Auflösung, eine verwandte, aber eigenständige Mechanik), [`lock-master`](https://github.com/ellmos-ai/lock-master), [`ticket-master`](https://github.com/ellmos-ai/ticket-master), [`DevCenter`](https://github.com/dev-bricks/DevCenter), [`CodeBox`](https://github.com/dev-bricks/CodeBox).

## Sicherheit

Siehe [SECURITY.md](SECURITY.md) — local-first, Zero-Egress, reine
Zeiger-Registry (nie Skript-Text), Einweg-Materialisierung,
Non-Elevation.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
