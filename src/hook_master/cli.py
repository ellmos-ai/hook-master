from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import materialize
from .adapters.sync_hooks import export_aggregated_view, import_adoption_pointers
from .registry import HookRegistry, RegistryError


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=lambda o: o.__dict__))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="hook-master")
    root.add_argument("--registry", help="Pfad zur lokalen Registry")
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("init")
    commands.add_parser("list")

    get = commands.add_parser("get")
    get.add_argument("id")

    search = commands.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--event")
    search.add_argument("--agent")
    search.add_argument("--kind")

    register = commands.add_parser("register")
    register.add_argument("entry_json")
    register.add_argument("--replace", action="store_true")

    commands.add_parser("verify")

    deploy = commands.add_parser("deploy")
    deploy.add_argument("--id", dest="entry_id")
    deploy.add_argument("--dry-run", action="store_true")

    diff = commands.add_parser("diff")
    diff.add_argument("--id", dest="entry_id")

    commands.add_parser("status")

    migrate = commands.add_parser("import-sync")
    migrate.add_argument("--root", required=True)
    migrate.add_argument("--slot", required=True)
    migrate.add_argument("--no-replace", action="store_true")

    export = commands.add_parser("export-sync-view")
    export.add_argument("--root", required=True)
    export.add_argument("--slot", required=True)

    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    registry = HookRegistry(args.registry)
    try:
        if args.command == "init":
            _print({"registry": str(registry.init())})
        elif args.command == "list":
            _print(registry.load()["entries"])
        elif args.command == "get":
            item = registry.get(args.id)
            _print(item)
            return 0 if item else 1
        elif args.command == "search":
            _print(registry.search(args.query, event=args.event, agent=args.agent, kind=args.kind))
        elif args.command == "register":
            entry = json.loads(Path(args.entry_json).read_text(encoding="utf-8"))
            _print(registry.register(entry, replace=args.replace))
        elif args.command == "verify":
            result = registry.verify()
            _print(result)
            return 0 if result["ok"] else 1
        elif args.command == "deploy":
            results = materialize.deploy(registry, entry_id=args.entry_id, dry_run=args.dry_run)
            _print([r.__dict__ for r in results])
        elif args.command == "diff":
            rows = materialize.diff(registry, entry_id=args.entry_id)
            _print(rows)
            return 0 if all(r["state"] in {"in-sync", "no-canonical-source"} for r in rows) else 2
        elif args.command == "status":
            result = materialize.status(registry)
            _print(result)
            return 0 if result["ok"] else 1
        elif args.command == "import-sync":
            result = import_adoption_pointers(registry, args.root, slot=args.slot, replace=not args.no_replace)
            _print({"registered": len(result["registered"]), "skipped": result["skipped"], "registry": str(registry.path)})
        elif args.command == "export-sync-view":
            target = export_aggregated_view(registry, args.root, slot=args.slot)
            _print({"view": str(target), "authority": str(registry.path)})
        return 0
    except (RegistryError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
