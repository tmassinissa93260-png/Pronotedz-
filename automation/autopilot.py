#!/usr/bin/env python3
"""autopilot - petit moteur d'automatisation local.

Surveille un dossier, compare chaque fichier a une liste de regles, applique
l'action de la premiere regle qui correspond. Aucune dependance externe.

    python autopilot.py init                  # ecrit un fichier de regles d'exemple
    python autopilot.py run --dry-run         # une passe, sans rien modifier
    python autopilot.py run                   # une passe, pour de vrai
    python autopilot.py watch --interval 5    # boucle jusqu'a Ctrl-C
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_CONFIG = "rules.json"
ACTIONS = ("move", "copy", "rename", "delete", "run")


class ConfigError(Exception):
    """Fichier de regles invalide."""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


@dataclass
class Rule:
    name: str
    match: dict
    action: dict
    enabled: bool = True


@dataclass
class Config:
    watch_dir: Path
    rules: list[Rule]
    log_file: Path | None = None
    recursive: bool = False
    skip_hidden: bool = True
    settle_seconds: float = 0.0
    source: Path | None = field(default=None, compare=False)


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"fichier de regles introuvable: {path}") from None
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON invalide dans {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("la racine du fichier de regles doit etre un objet JSON")

    base = path.parent
    watch_dir = raw.get("watch_dir")
    if not watch_dir:
        raise ConfigError("champ 'watch_dir' manquant")

    log_file = raw.get("log_file")
    rules = [_parse_rule(i, r) for i, r in enumerate(raw.get("rules") or [])]
    if not rules:
        raise ConfigError("aucune regle definie dans 'rules'")

    return Config(
        watch_dir=_resolve(base, watch_dir),
        rules=rules,
        log_file=_resolve(base, log_file) if log_file else None,
        recursive=bool(raw.get("recursive", False)),
        skip_hidden=bool(raw.get("skip_hidden", True)),
        settle_seconds=float(raw.get("settle_seconds", 0.0)),
        source=path,
    )


def _resolve(base: Path, value: str) -> Path:
    p = Path(os.path.expanduser(str(value)))
    return p if p.is_absolute() else (base / p)


def _parse_rule(index: int, raw: object) -> Rule:
    label = f"regle #{index + 1}"
    if not isinstance(raw, dict):
        raise ConfigError(f"{label}: doit etre un objet JSON")

    name = str(raw.get("name") or label)
    action = raw.get("action")
    if not isinstance(action, dict):
        raise ConfigError(f"{name}: champ 'action' manquant ou invalide")

    kind = action.get("type")
    if kind not in ACTIONS:
        raise ConfigError(
            f"{name}: action '{kind}' inconnue (attendu: {', '.join(ACTIONS)})"
        )
    if kind in ("move", "copy") and not action.get("dest"):
        raise ConfigError(f"{name}: l'action '{kind}' exige un champ 'dest'")
    if kind == "rename" and not action.get("template"):
        raise ConfigError(f"{name}: l'action 'rename' exige un champ 'template'")
    if kind == "run" and not action.get("command"):
        raise ConfigError(f"{name}: l'action 'run' exige un champ 'command'")

    match = raw.get("match")
    if match is None:
        match = {}
    if not isinstance(match, dict):
        raise ConfigError(f"{name}: champ 'match' invalide")

    return Rule(
        name=name,
        match=match,
        action=action,
        enabled=bool(raw.get("enabled", True)),
    )


# --------------------------------------------------------------------------
# Correspondance
# --------------------------------------------------------------------------


def matches(rule: Rule, path: Path, now: float | None = None) -> bool:
    """Vrai si `path` satisfait tous les criteres de la regle."""
    crit = rule.match
    if not crit:
        return True

    exts = crit.get("ext")
    if exts is not None:
        wanted = {("." + e.lstrip(".")).lower() for e in exts}
        if path.suffix.lower() not in wanted:
            return False

    pattern = crit.get("glob")
    if pattern and not fnmatch.fnmatch(path.name, pattern):
        return False

    excluded = crit.get("exclude_glob")
    if excluded and fnmatch.fnmatch(path.name, excluded):
        return False

    needle = crit.get("name_contains")
    if needle and needle.lower() not in path.name.lower():
        return False

    min_size = crit.get("min_size_kb")
    max_size = crit.get("max_size_kb")
    older = crit.get("older_than_days")
    if min_size is not None or max_size is not None or older is not None:
        try:
            stat = path.stat()
        except OSError:
            return False
        size_kb = stat.st_size / 1024
        if min_size is not None and size_kb < float(min_size):
            return False
        if max_size is not None and size_kb > float(max_size):
            return False
        if older is not None:
            reference = time.time() if now is None else now
            age_days = (reference - stat.st_mtime) / 86400
            if age_days < float(older):
                return False

    return True


def first_match(rules: list[Rule], path: Path, now: float | None = None) -> Rule | None:
    for rule in rules:
        if rule.enabled and matches(rule, path, now=now):
            return rule
    return None


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------


def render(template: str, path: Path) -> str:
    """Remplit un gabarit avec les champs du fichier courant."""
    stamp = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else datetime.now()
    return template.format(
        name=path.name,
        stem=path.stem,
        ext=path.suffix.lstrip("."),
        parent=str(path.parent),
        path=str(path),
        date=stamp.strftime("%Y-%m-%d"),
        year=stamp.strftime("%Y"),
        month=stamp.strftime("%m"),
        day=stamp.strftime("%d"),
    )


def unique_destination(target: Path) -> Path:
    """Ne jamais ecraser: ajoute -1, -2, ... si la cible existe deja."""
    if not target.exists():
        return target
    for counter in range(1, 1000):
        candidate = target.with_name(f"{target.stem}-{counter}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"impossible de trouver un nom libre pour {target}")


def apply_action(rule: Rule, path: Path, config: Config, dry_run: bool) -> dict:
    """Execute l'action de la regle. Retourne une entree de journal."""
    action = rule.action
    kind = action["type"]
    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": rule.name,
        "action": kind,
        "file": str(path),
        "dry_run": dry_run,
        "status": "ok",
    }

    try:
        if kind in ("move", "copy"):
            dest_dir = _resolve(config.source.parent if config.source else Path.cwd(),
                                render(str(action["dest"]), path))
            target = unique_destination(dest_dir / path.name)
            entry["target"] = str(target)
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if kind == "move":
                    shutil.move(str(path), str(target))
                else:
                    shutil.copy2(str(path), str(target))

        elif kind == "rename":
            new_name = render(str(action["template"]), path)
            if "/" in new_name or "\\" in new_name:
                raise ValueError("le gabarit 'template' ne doit pas contenir de separateur")
            if new_name == path.name:
                entry["status"] = "skip"  # deja au bon nom: ne pas creer nom-1.ext
                return entry
            target = unique_destination(path.parent / new_name)
            entry["target"] = str(target)
            if not dry_run:
                path.rename(target)

        elif kind == "delete":
            if not dry_run:
                path.unlink()

        elif kind == "run":
            command = [render(part, path) for part in _as_argv(action["command"])]
            entry["command"] = command
            if not dry_run:
                result = subprocess.run(command, capture_output=True, text=True)
                entry["returncode"] = result.returncode
                if result.returncode != 0:
                    entry["status"] = "error"
                    entry["error"] = (result.stderr or "").strip()[:500]

    except Exception as exc:  # une regle qui echoue ne doit pas tuer la passe
        entry["status"] = "error"
        entry["error"] = f"{type(exc).__name__}: {exc}"

    return entry


def _as_argv(command: object) -> list[str]:
    if isinstance(command, list):
        return [str(c) for c in command]
    return shlex.split(str(command))


# --------------------------------------------------------------------------
# Moteur
# --------------------------------------------------------------------------


def iter_files(config: Config) -> list[Path]:
    root = config.watch_dir
    if not root.is_dir():
        return []
    walker = root.rglob("*") if config.recursive else root.glob("*")
    files = []
    for entry in sorted(walker):
        if not entry.is_file():
            continue
        if config.skip_hidden and any(part.startswith(".") for part in entry.relative_to(root).parts):
            continue
        files.append(entry)
    return files


def run_once(config: Config, dry_run: bool = False) -> list[dict]:
    """Une passe complete sur le dossier surveille."""
    now = time.time()
    entries = []
    for path in iter_files(config):
        if config.settle_seconds > 0:
            try:
                if now - path.stat().st_mtime < config.settle_seconds:
                    continue  # fichier encore en cours d'ecriture
            except OSError:
                continue
        rule = first_match(config.rules, path, now=now)
        if rule is None:
            continue
        entries.append(apply_action(rule, path, config, dry_run))
    if entries and config.log_file and not dry_run:
        write_log(config.log_file, entries)
    return entries


def write_log(log_file: Path, entries: list[dict]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

EXAMPLE_CONFIG = {
    "watch_dir": "~/Downloads",
    "log_file": "autopilot.log.jsonl",
    "recursive": False,
    "skip_hidden": True,
    "settle_seconds": 2,
    "rules": [
        {
            "name": "Images vers Photos/AAAA-MM",
            "match": {"ext": ["jpg", "jpeg", "png", "heic"]},
            "action": {"type": "move", "dest": "~/Photos/{year}-{month}"},
        },
        {
            "name": "Factures PDF horodatees",
            "match": {"ext": ["pdf"], "name_contains": "facture",
                      "exclude_glob": "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*"},
            "action": {"type": "rename", "template": "{date}-{stem}.{ext}"},
        },
        {
            "name": "Archives vers Archives/",
            "match": {"ext": ["zip", "tar", "gz"]},
            "action": {"type": "move", "dest": "~/Archives"},
        },
        {
            "name": "Purge des vieux .tmp",
            "enabled": False,
            "match": {"ext": ["tmp"], "older_than_days": 7},
            "action": {"type": "delete"},
        },
    ],
}


def describe(entry: dict) -> str:
    if entry["status"] == "error":
        mark = "!"
    elif entry["status"] == "skip":
        mark = "="
    else:
        mark = "~" if entry["dry_run"] else "+"
    name = Path(entry["file"]).name
    if entry["status"] == "skip":
        return f"  {mark} [{entry['rule']}] {name} deja conforme, rien a faire"
    if entry["action"] in ("move", "copy", "rename"):
        detail = f"{entry['action']} {name} -> {entry.get('target', '?')}"
    elif entry["action"] == "run":
        detail = f"run {' '.join(entry.get('command', []))}"
    else:
        detail = f"{entry['action']} {name}"
    if entry["status"] == "error":
        detail += f"  [{entry.get('error', 'erreur')}]"
    return f"  {mark} [{entry['rule']}] {detail}"


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        print(f"{path} existe deja (utiliser --force pour ecraser)", file=sys.stderr)
        return 1
    path.write_text(json.dumps(EXAMPLE_CONFIG, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"Regles d'exemple ecrites dans {path}")
    print("Edite-les, puis lance: python autopilot.py run --dry-run")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    entries = run_once(config, dry_run=args.dry_run)
    mode = "SIMULATION" if args.dry_run else "APPLIQUE"
    print(f"[{mode}] {config.watch_dir} - {len(entries)} action(s)")
    for entry in entries:
        print(describe(entry))
    return 1 if any(e["status"] == "error" for e in entries) else 0


def cmd_watch(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    print(f"Surveillance de {config.watch_dir} toutes les {args.interval}s (Ctrl-C pour arreter)")
    try:
        while True:
            for entry in run_once(config, dry_run=args.dry_run):
                print(describe(entry), flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nArret.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autopilot",
        description="Petit moteur d'automatisation local pilote par un fichier de regles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="ecrire un fichier de regles d'exemple")
    p_init.add_argument("--config", default=DEFAULT_CONFIG)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="une passe sur le dossier surveille")
    p_run.add_argument("--config", default=DEFAULT_CONFIG)
    p_run.add_argument("--dry-run", action="store_true", help="ne rien modifier")
    p_run.set_defaults(func=cmd_run)

    p_watch = sub.add_parser("watch", help="boucler jusqu'a Ctrl-C")
    p_watch.add_argument("--config", default=DEFAULT_CONFIG)
    p_watch.add_argument("--interval", type=float, default=5.0)
    p_watch.add_argument("--dry-run", action="store_true")
    p_watch.set_defaults(func=cmd_watch)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"Configuration invalide: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
