"""Install this complete skill folder into Codex without losing an existing copy."""

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def files_in(folder: Path) -> set[Path]:
    return {
        path.relative_to(folder)
        for path in folder.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def same_tree(source: Path, target: Path) -> bool:
    source_files = files_in(source)
    return source_files == files_in(target) and all(
        (source / relative).read_bytes() == (target / relative).read_bytes()
        for relative in source_files
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="Back up and replace a different installed version")
    args = parser.parse_args()

    source = Path(__file__).resolve().parent
    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    target = codex_home / "skills" / source.name
    if source == target:
        print(f"Already installed: {target}")
        return
    if target.exists() and same_tree(source, target):
        print(f"Already up to date: {target}")
        return
    if target.exists() and not args.replace:
        raise SystemExit(f"Different skill exists at {target}; use --replace to back it up and upgrade.")

    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.parent / f".{source.name}-{uuid4().hex}.tmp"
    shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    backup = None
    try:
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = codex_home / "skill-backups" / f"{source.name}-{stamp}-{uuid4().hex[:8]}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(target, backup)
        shutil.move(staged, target)
    except Exception:
        if backup and backup.exists() and not target.exists():
            shutil.move(backup, target)
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    if backup:
        print(f"Previous version backed up: {backup}")
    print(f"Installed: {target}")


if __name__ == "__main__":
    main()
