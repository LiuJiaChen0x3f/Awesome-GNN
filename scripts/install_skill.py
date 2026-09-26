"""Install this project's reusable skill without overwriting unrelated skills."""
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "skills" / "gnn-paper-digest" / "SKILL.md"
target = Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "gnn-paper-digest" / "SKILL.md"
if target.exists() and target.read_bytes() != source.read_bytes():
    raise SystemExit(f"An existing different skill is installed at {target}; review before replacing it.")
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)
print(f"Installed: {target}")
