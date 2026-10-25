import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.src = self.root / "source"
        self.dst = self.root / "destination"
        self.src.mkdir()
        self.dst.mkdir()
        self.config = {
            "source": str(self.src), "destination": str(self.dst),
            "versions": str(self.root / "destination.versions"),
            "source_identity": backup.identity(self.src),
            "destination_identity": backup.identity(self.dst),
        }

    def test_overlap_rejected(self):
        self.config["destination"] = str(self.src)
        with self.assertRaisesRegex(ValueError, "overlap"):
            backup.validate(self.config)

    def test_identity_mismatch_rejected(self):
        self.config["destination_identity"]["directory_id"] += 1
        with self.assertRaisesRegex(ValueError, "identity changed"):
            backup.validate(self.config)

    def test_missing_drive_rejected(self):
        self.dst.rmdir()
        with self.assertRaisesRegex(ValueError, "unavailable"):
            backup.validate(self.config)

    def test_nested_versions_rejected(self):
        self.config["versions"] = str(self.dst / "old")
        with self.assertRaisesRegex(ValueError, "overlap"):
            backup.validate(self.config)

    def test_no_rebind(self):
        conf = self.root / "config.local.json"
        args = ["bind", "--source", str(self.src), "--destination", str(self.dst), "--config", str(conf)]
        self.assertEqual(backup.main(args), 0)
        before = conf.read_bytes()
        self.assertEqual(backup.main(args), 1)
        self.assertEqual(conf.read_bytes(), before)

    def test_lock_and_cleanup(self):
        with backup.destination_lock(self.dst):
            with self.assertRaisesRegex(ValueError, "lock exists"):
                with backup.destination_lock(self.dst):
                    self.fail("Must not acquire second lock")
        with backup.destination_lock(self.dst):
            pass

    def test_environment_isolation(self):
        with patch.dict(os.environ, {"RCLONE_COPY_LINKS": "true", "RCLONE_FILTER": "- **"}):
            self.assertFalse(any(k.upper().startswith("RCLONE_") for k in backup.clean_env()))

    def test_failure_recorded(self):
        logs = self.root / "logs"
        with patch.object(backup, "invoke", side_effect=subprocess.CalledProcessError(7, "rclone")):
            with self.assertRaises(subprocess.CalledProcessError):
                backup.execute(self.config, "run", "fake", False, logs)
        report = json.loads(next(logs.glob("*.json")).read_text())
        self.assertEqual(report["status"], "failed")
        self.assertFalse(list(self.root.glob("*.lock")))
        self.assertFalse(list(self.root.glob(".*.lock")))

    def test_plan_is_read_only(self):
        calls = []
        with patch.object(backup, "invoke", side_effect=calls.append):
            report = backup.execute(self.config, "plan", "fake", False, self.root / "logs")
        self.assertEqual(report["status"], "preview")
        self.assertIn("--dry-run", calls[0])
        self.assertIn("--checksum", calls[0])
        self.assertEqual(list(self.dst.iterdir()), [])
        self.assertFalse(Path(self.config["versions"]).exists())

    def test_destination_junction_rejected(self):
        if os.name != "nt":
            (self.dst / "escape").symlink_to(self.src, target_is_directory=True)
        else:
            subprocess.run(["cmd", "/c", "mklink", "/J", str(self.dst / "escape"), str(self.src)],
                           check=True, capture_output=True)
        with patch.object(backup, "invoke") as invoke:
            with self.assertRaisesRegex(ValueError, "reparse"):
                backup.execute(self.config, "run", "fake", False, self.root / "logs")
            invoke.assert_not_called()

    def test_rclone_end_to_end(self):
        try:
            exe = backup.find_rclone(os.environ.get("BACKUP_TEST_RCLONE"))
        except ValueError:
            if os.environ.get("CI"):
                self.fail("CI must install rclone for integration tests")
            self.skipTest("rclone not installed")
        # Chinese names, spaces, empty folders, hidden data, same-size/time edits.
        (self.src / "论文 notes").mkdir()
        (self.src / "empty").mkdir()
        (self.src / "论文 notes" / "new.txt").write_text("new", encoding="utf-8")
        for directory in (self.src, self.dst):
            (directory / "same.txt").write_bytes(b"same")
        (self.src / "change.txt").write_bytes(b"NEW!")
        (self.dst / "change.txt").write_bytes(b"OLD!")
        stamp = (self.dst / "change.txt").stat().st_mtime_ns
        os.utime(self.src / "change.txt", ns=(stamp, stamp))
        (self.dst / "destination-only.txt").write_bytes(b"keep me")
        (self.src / ".hidden").write_bytes(b"hidden")
        original = (self.dst / "same.txt").stat().st_mtime_ns
        logs = self.root / "logs"

        backup.execute(self.config, "plan", exe, False, logs)
        self.assertEqual((self.dst / "change.txt").read_bytes(), b"OLD!")
        self.assertFalse((self.dst / ".hidden").exists())
        report = backup.execute(self.config, "run", exe, False, logs)
        self.assertEqual((self.dst / "change.txt").read_bytes(), b"NEW!")
        self.assertEqual((Path(report["versions"]) / "change.txt").read_bytes(), b"OLD!")
        self.assertEqual((self.dst / "same.txt").stat().st_mtime_ns, original)
        self.assertEqual((self.dst / "destination-only.txt").read_bytes(), b"keep me")
        self.assertTrue((self.dst / "论文 notes" / "new.txt").exists())
        self.assertTrue((self.dst / "empty").is_dir())
        self.assertTrue((self.dst / ".hidden").exists())

        # Second run transfers nothing and does not add historical copies.
        second = backup.execute(self.config, "run", exe, False, logs)
        self.assertFalse(Path(second["versions"]).exists())
        log = Path(second["log"]).read_text(encoding="utf-8")
        self.assertIn("0 B / 0 B", log)

        # Deletion on source must not propagate to backup.
        (self.src / ".hidden").unlink()
        backup.execute(self.config, "run", exe, False, logs)
        self.assertTrue((self.dst / ".hidden").exists())
        # Standalone verification must report content corruption.
        (self.dst / "same.txt").write_bytes(b"bad!")
        with self.assertRaises(subprocess.CalledProcessError):
            backup.execute(self.config, "verify", exe, False, logs)
        # Restore a historical file to a separate recovery folder.
        restored = self.root / "restored"
        backup.invoke([exe, "--config=", "copy", report["versions"], str(restored)])
        self.assertEqual((restored / "change.txt").read_bytes(), b"OLD!")


if __name__ == "__main__":
    unittest.main()
