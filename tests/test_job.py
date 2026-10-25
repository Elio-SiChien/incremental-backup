import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import backup
import job


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "source"
        self.dst = self.root / "destination"
        self.src.mkdir()
        self.dst.mkdir()

    def test_new_pair_and_reuse(self):
        profile = job.profile_for(str(self.src), str(self.dst), self.root)
        before = profile.read_bytes()
        again = job.profile_for(str(self.src), str(self.dst), self.root)
        self.assertEqual(profile, again)
        self.assertEqual(profile.read_bytes(), before)
        backup.validate(json.loads(before))

    def test_reverse_direction_has_separate_binding(self):
        forward = job.profile_for(str(self.src), str(self.dst), self.root)
        reverse = job.profile_for(str(self.dst), str(self.src), self.root)
        self.assertNotEqual(forward, reverse)
        self.assertEqual(json.loads(reverse.read_text())["source"], str(self.dst))

    def test_reuse_existing_default_config(self):
        existing = self.root / "config.local.json"
        self.assertEqual(backup.main(["bind", "--source", str(self.src), "--destination", str(self.dst),
                                      "--config", str(existing)]), 0)
        self.assertEqual(job.profile_for(str(self.src), str(self.dst), self.root), existing)
        self.assertFalse((self.root / "profiles").exists())

    def test_changed_identity_is_not_rebound(self):
        profile = job.profile_for(str(self.src), str(self.dst), self.root)
        config = json.loads(profile.read_text())
        config["destination_identity"]["directory_id"] += 1
        profile.write_text(json.dumps(config))
        before = profile.read_bytes()
        selected = job.profile_for(str(self.src), str(self.dst), self.root)
        self.assertEqual(selected.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            backup.validate(json.loads(selected.read_text()))

    def test_other_default_binding_is_preserved(self):
        old = self.root / "config.local.json"
        old.write_text(json.dumps({"source": str(self.root / "other"), "destination": str(self.dst)}))
        before = old.read_bytes()
        profile = job.profile_for(str(self.src), str(self.dst), self.root)
        self.assertNotEqual(profile, old)
        self.assertEqual(old.read_bytes(), before)

    def test_skill_entry_point_finds_repository(self):
        launcher = backup.BASE / "skills" / "incremental-backup" / "scripts" / "backup_job.py"
        result = subprocess.run([sys.executable, str(launcher), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--source", result.stdout)
        self.assertIn("--destination", result.stdout)


if __name__ == "__main__":
    unittest.main()
