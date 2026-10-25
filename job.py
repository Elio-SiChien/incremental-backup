"""Select a stable private backup profile from a source/destination pair."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import backup


def path_key(path):
    return os.path.normcase(os.path.abspath(path))


def profile_for(source, destination, root=backup.BASE):
    candidates = [root / "config.local.json"]
    pair = [path_key(source), path_key(destination)]
    digest = hashlib.sha256(json.dumps(pair).encode("utf-8")).hexdigest()[:24]
    profile = root / "profiles" / (digest + ".local.json")
    candidates.append(profile)
    for candidate in candidates:
        if not candidate.exists():
            continue
        config = json.loads(candidate.read_text(encoding="utf-8"))
        if [path_key(config["source"]), path_key(config["destination"])] == pair:
            return candidate
        if candidate == profile:
            raise ValueError("Profile path is occupied by a different path pair")
    backup.folder(source)
    backup.folder(destination)
    backup.no_links(profile.parent)
    if any(backup.overlaps(profile.parent, Path(p)) for p in pair):
        raise ValueError("Private profiles must be outside backup data directories")
    profile.parent.mkdir(parents=True, exist_ok=True)
    result = backup.main(["bind", "--source", source, "--destination", destination,
                          "--config", str(profile)])
    if result:
        raise ValueError("Could not bind this path pair")
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "run", "verify"])
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--rclone")
    args = parser.parse_args(argv)
    try:
        backup.folder(args.source)
        backup.folder(args.destination)
        profile = profile_for(args.source, args.destination)
        print(f"Profile: {profile}", flush=True)
        command = [args.action, "--config", str(profile)]
        if args.fast:
            command.append("--fast")
        if args.rclone:
            command += ["--rclone", args.rclone]
        return backup.main(command)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
