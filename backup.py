"""Repeatable local incremental backup powered by rclone (Python 3.10+)."""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import uuid

BASE = Path(__file__).resolve().parent


def no_links(path: Path) -> None:
    """Reject junctions/reparse points as well as symlinks in existing ancestors."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Link/reparse point is not supported: {part}")


def inspect_destination(dst: Path) -> None:
    """Inspect each entry once; scandir reuses Windows directory metadata."""
    pending = [dst]
    count = 0
    updated = time.monotonic()
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValueError(f"Link/reparse point is not supported: {entry.path}")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
                count += 1
                if time.monotonic() - updated >= 10:
                    print(f"Safety scan: {count:,} entries checked", flush=True)
                    updated = time.monotonic()
    print(f"Safety scan complete: {count:,} entries checked", flush=True)


def folder(value: str) -> Path:
    p = Path(value).expanduser()
    if not p.is_absolute():
        raise ValueError(f"Use an absolute local path: {value}")
    p = Path(os.path.abspath(p))
    no_links(p)
    if not p.is_dir():
        raise ValueError(f"Directory unavailable (connect the drive first): {p}")
    if p == Path(p.anchor):
        raise ValueError("A drive root cannot be used as a backup folder")
    return p


def overlaps(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def identity(path: Path) -> dict:
    """Bind both the volume and directory; never trust a drive letter alone."""
    result = {"directory_id": path.stat().st_ino, "device": path.stat().st_dev}
    if os.name == "nt":
        serial = ctypes.c_ulong()
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        ok = kernel.GetVolumeInformationW(
            ctypes.c_wchar_p(path.anchor), None, 0, ctypes.byref(serial),
            None, None, None, 0,
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        result["volume_serial"] = serial.value
    return result


def validate(config: dict) -> tuple[Path, Path, Path]:
    src, dst = folder(config["source"]), folder(config["destination"])
    versions = Path(config["versions"])
    if not versions.is_absolute():
        raise ValueError("Versions directory must be absolute")
    versions = Path(os.path.abspath(versions))
    no_links(versions)
    if overlaps(src, dst) or overlaps(src, versions) or overlaps(dst, versions):
        raise ValueError("Source, destination and versions must not overlap")
    if versions.parent != dst.parent:
        raise ValueError("Versions directory must be a sibling of destination")
    if src.name == versions.name or dst.name == versions.name:
        raise ValueError("Invalid versions directory")
    if identity(src) != config["source_identity"]:
        raise ValueError("Source disk/folder identity changed; inspect and bind again")
    if identity(dst) != config["destination_identity"]:
        raise ValueError("Destination disk/folder identity changed; inspect and bind again")
    return src, dst, versions


def find_rclone(value: str | None) -> str:
    if value:
        found = shutil.which(value)
        if found:
            return found
        raise ValueError(f"rclone executable not found: {value}")
    found = shutil.which("rclone")
    if found:
        return found
    choices = sorted((BASE / "vendor").glob("rclone-*/rclone.exe"))
    if len(choices) == 1:
        return str(choices[0])
    raise ValueError("Install rclone from https://rclone.org/downloads/ or pass --rclone")


def clean_env() -> dict:
    # Prevent ambient rclone settings from enabling copy-links, filters or inplace.
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("RCLONE_")}


def invoke(args: list[str]) -> None:
    print(subprocess.list2cmdline(args), flush=True)
    subprocess.run(args, check=True, env=clean_env())


@contextlib.contextmanager
def destination_lock(dst: Path):
    # Deterministic sibling lock prevents concurrent runs even with other configs.
    path = dst.parent / ("." + dst.name + ".incremental-backup.lock")
    no_links(path)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"Backup lock exists: {path}. Check running processes before removing it.") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump({"pid": os.getpid(), "started": dt.datetime.now(dt.timezone.utc).isoformat()}, out)
        yield
    finally:
        path.unlink()


def base_args(exe: str, log: Path) -> list[str]:
    return [exe, "--config=", "--log-file", str(log), "--log-level", "INFO",
            "--stats", "10s", "--checkers", "4", "--retries", "2",
            "--copy-links=false", "--links=false", "--local-links=false"]


def execute(config: dict, action: str, exe: str, fast: bool, logs: Path) -> dict:
    src, dst, versions = validate(config)
    logs = logs.absolute()
    no_links(logs)
    if any(overlaps(logs, p) for p in (src, dst, versions)):
        raise ValueError("Logs must be outside source, destination and versions")
    # Fail closed if a destination tree contains any reparse points. rclone does
    # not follow source links, but pre-existing destination links need guarding.
    inspect_destination(dst)
    logs.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ-") + uuid.uuid4().hex[:8]
    report = {"run_id": run_id, "action": action, "comparison": "size-time" if fast else "checksum",
              "status": "running", "source": str(src), "destination": str(dst),
              "versions": str(versions / run_id), "log": str(logs / (run_id + ".log"))}
    summary = logs / (run_id + ".json")
    common = base_args(exe, Path(report["log"]))
    print(f"{action.upper()}: {src} -> {dst}\nOld versions: {report['versions']}", flush=True)

    def check():
        invoke(common + ["check", str(src), str(dst), "--one-way", "--download",
                         "--combined", str(logs / (run_id + ".check.txt"))])

    try:
        if action == "verify":
            check()
        else:
            cmd = common + ["copy", str(src), str(dst), "--backup-dir", report["versions"],
                            "--create-empty-src-dirs", "--transfers", "2", "--check-first"]
            if not fast:
                cmd += ["--checksum"]
            if action == "plan":
                invoke(cmd + ["--dry-run"])
            else:
                with destination_lock(dst):
                    validate(config)
                    invoke(cmd)
                    check()
        report["status"] = "preview" if action == "plan" else "success"
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        summary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {summary}", flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bind", "plan", "run", "verify"])
    parser.add_argument("--config", type=Path, default=BASE / "config.local.json")
    parser.add_argument("--source")
    parser.add_argument("--destination")
    parser.add_argument("--rclone")
    parser.add_argument("--fast", action="store_true", help="Compare size/time; run still verifies full content")
    parser.add_argument("--logs", type=Path, default=BASE / "logs")
    args = parser.parse_args(argv)
    try:
        if args.action == "bind":
            if not args.source or not args.destination:
                parser.error("bind requires --source and --destination")
            src, dst = folder(args.source), folder(args.destination)
            config = {"source": str(src), "destination": str(dst),
                      "versions": str(dst.with_name(dst.name + ".versions")),
                      "source_identity": identity(src), "destination_identity": identity(dst)}
            validate(config)
            conf = args.config.absolute()
            no_links(conf)
            if any(overlaps(conf, p) for p in (src, dst, Path(config["versions"]))):
                raise ValueError("Save configuration outside the data directories")
            # Exclusive creation avoids accidentally rebinding an existing job.
            with conf.open("x", encoding="utf-8") as out:
                json.dump(config, out, ensure_ascii=False, indent=2)
            print(f"Bound {src} -> {dst}. Configuration saved: {conf}")
            return 0
        if args.source or args.destination:
            parser.error("source/destination are only accepted with bind")
        config = json.loads(args.config.read_text(encoding="utf-8"))
        execute(config, args.action, find_rclone(args.rclone), args.fast, args.logs)
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted. Inspect log and versions before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
