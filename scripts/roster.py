#!/usr/bin/env python3
"""Leader roster for boss-reports-to-me.

The roster is the list of leaders to report on. It stores only what is needed
to run the weekly collection: each leader's display name, open_id, and a level
label (e.g. "直属上级", "+2", "+3"). It does NOT store any collected content.

open_id is required here because im/drive/minutes/vc searches filter by it; it
is operational configuration, kept in a private (0600) file separate from the
fingerprint state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
OPEN_ID_RE = re.compile(r"^ou_[A-Za-z0-9_-]{8,}$")
LEVEL_RE = re.compile(r"^(直属上级|\+[1-9])$")


class RosterError(ValueError):
    pass


def default_path() -> Path:
    configured = os.environ.get("BOSS_REPORTS_ROSTER_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex" / "boss-reports-to-me" / "roster.json"


def initial_roster() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "leaders": []}


def validate_roster(roster: dict[str, Any]) -> None:
    if roster.get("schema_version") != SCHEMA_VERSION:
        raise RosterError(f"schema_version must be {SCHEMA_VERSION}")
    leaders = roster.get("leaders")
    if not isinstance(leaders, list):
        raise RosterError("leaders must be a list")
    seen: set[str] = set()
    for i, ldr in enumerate(leaders):
        if not isinstance(ldr, dict):
            raise RosterError(f"leaders[{i}] must be an object")
        name = ldr.get("name")
        open_id = ldr.get("open_id")
        level = ldr.get("level")
        if not isinstance(name, str) or not name.strip():
            raise RosterError(f"leaders[{i}].name must be a non-empty string")
        if not isinstance(open_id, str) or not OPEN_ID_RE.match(open_id):
            raise RosterError(f"leaders[{i}].open_id must look like ou_...")
        if not isinstance(level, str) or not LEVEL_RE.match(level):
            raise RosterError(f"leaders[{i}].level must be 直属上级 or +N")
        if open_id in seen:
            raise RosterError(f"duplicate open_id in roster: {open_id}")
        seen.add(open_id)


def load_roster(path: Path) -> dict[str, Any]:
    try:
        roster = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return initial_roster()
    except json.JSONDecodeError as exc:
        raise RosterError(f"roster file is invalid JSON: {path}") from exc
    if not isinstance(roster, dict):
        raise RosterError("roster root must be an object")
    validate_roster(roster)
    return roster


def atomic_write(path: Path, roster: dict[str, Any]) -> None:
    validate_roster(roster)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, stat.S_IRWXU)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".roster-", suffix=".json", delete=False
    ) as handle:
        json.dump(roster, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temp_path, path)


def _sort_key(level: str) -> tuple[int, int]:
    # 直属上级 first, then +2, +3, +4 ...
    if level == "直属上级":
        return (0, 1)
    return (1, int(level.lstrip("+")))


def command_show(args: argparse.Namespace) -> int:
    roster = load_roster(args.path)
    leaders = sorted(roster["leaders"], key=lambda l: _sort_key(l["level"]))
    print(json.dumps({"ok": True, "leaders": leaders}, ensure_ascii=False, indent=2))
    return 0


def command_add(args: argparse.Namespace) -> int:
    if not OPEN_ID_RE.match(args.open_id):
        raise RosterError("open_id must look like ou_...")
    if not LEVEL_RE.match(args.level):
        raise RosterError("level must be 直属上级 or +N")
    roster = load_roster(args.path)
    leaders = [l for l in roster["leaders"] if l["open_id"] != args.open_id]
    leaders.append({"name": args.name, "open_id": args.open_id, "level": args.level})
    roster["leaders"] = leaders
    atomic_write(args.path, roster)
    print(json.dumps({"ok": True, "count": len(leaders)}, ensure_ascii=False))
    return 0


def command_remove(args: argparse.Namespace) -> int:
    roster = load_roster(args.path)
    before = len(roster["leaders"])
    roster["leaders"] = [l for l in roster["leaders"] if l["open_id"] != args.open_id]
    atomic_write(args.path, roster)
    print(json.dumps({"ok": True, "removed": before - len(roster["leaders"])}, ensure_ascii=False))
    return 0


def command_clear(args: argparse.Namespace) -> int:
    atomic_write(args.path, initial_roster())
    print(json.dumps({"ok": True, "count": 0}, ensure_ascii=False))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--path", type=Path, default=default_path())
    commands = root.add_subparsers(dest="command", required=True)

    show = commands.add_parser("show")
    show.set_defaults(func=command_show)

    add = commands.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--open-id", required=True, dest="open_id")
    add.add_argument("--level", required=True, help="直属上级 | +2 | +3 | +4")
    add.set_defaults(func=command_add)

    remove = commands.add_parser("remove")
    remove.add_argument("--open-id", required=True, dest="open_id")
    remove.set_defaults(func=command_remove)

    clear = commands.add_parser("clear")
    clear.set_defaults(func=command_clear)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, RosterError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
