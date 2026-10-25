"""Global skill entry point; delegate to the installed repository's job.py."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    skill = Path(__file__).resolve().parents[1]
    runtime = skill / "runtime.local.json"
    if runtime.exists():
        repository = Path(json.loads(runtime.read_text(encoding="utf-8-sig"))["repository"])
    else:
        repository = skill.parents[1]
    if not (repository / "job.py").is_file() or not (repository / "backup.py").is_file():
        print("Backup repository not found. Install the repository and set "
              "runtime.local.json: {\"repository\": \"ABSOLUTE_REPOSITORY_PATH\"}", file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, str(repository / "job.py"), *sys.argv[1:]],
                           cwd=repository)


if __name__ == "__main__":
    raise SystemExit(main())
