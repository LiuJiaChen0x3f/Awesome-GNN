import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "gnn-paper-digest"
INSTALLER = SOURCE / "install.py"


class SkillInstallTests(unittest.TestCase):
    def run_installer(self, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INSTALLER), *args],
            cwd=ROOT,
            env={**os.environ, "CODEX_HOME": str(home)},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_installs_entire_folder_and_preserves_existing_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            target = home / "skills" / "gnn-paper-digest"
            first = self.run_installer(home)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue((target / "SKILL.md").exists())
            self.assertTrue((target / "references" / "workflows.md").exists())
            self.assertTrue((target / "install.py").exists())
            self.assertIn("Already up to date", self.run_installer(home).stdout)

            (target / "SKILL.md").write_text("local version", encoding="utf-8")
            self.assertNotEqual(self.run_installer(home).returncode, 0)
            self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "local version")

            upgraded = self.run_installer(home, "--replace")
            self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
            backups = list((home / "skill-backups").glob("gnn-paper-digest-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(encoding="utf-8"), "local version")
            self.assertEqual((target / "SKILL.md").read_bytes(), (SOURCE / "SKILL.md").read_bytes())


if __name__ == "__main__":
    unittest.main()
