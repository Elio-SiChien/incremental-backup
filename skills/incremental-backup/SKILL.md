---
name: incremental-backup
description: 将工作目录新增或改动的文件单向备份到移动硬盘，保留覆盖前版本并校验。用户提供源路径和硬盘目标路径、要求复制更新或重复备份时自动使用；支持多组路径、差异预览和进度查询。不用于双向同步、删除镜像或仅复制单个文件。
---

Use the installed skill's `scripts/backup_job.py` for arbitrary local directory
pairs. It resolves the repository through `runtime.local.json` in this skill
folder; when used from the repository itself no pointer is needed. This pointer,
path profiles, logs and research data are local-only and must not be published.
Read the repository README for restore or setup details.

## Resolve the request

Take the source and destination directory from the user's message. If both are
clear, proceed without asking for them again. The destination is the final folder
whose contents should match source paths, not merely a drive root. If only a drive
root is supplied, use a child with the source folder's name; tell the user the
resolved direction. If either path is missing or the direction is ambiguous, ask
only for that missing detail. Source and destination must already exist; if the
target is new, create only that exact directory when a backup request authorizes
it, after checking the external volume and resolving the intended final path.

Providing paths together with an instruction to back up/copy updates authorizes
the backup. A request for a proposal, research or preview authorizes preview only.
Do not ask a second confirmation for an already authorized backup. Files with
different content at the same relative path use source as authoritative, with the
target's old file retained in the versions directory.

## Execute

1. Check for a running job/target lock first. If this pair is already running,
   report its progress; do not launch a duplicate. For long jobs inspect the
   repository `logs/active-job.json` and the target's sibling lock, and confirm
   process command lines before treating a PID as this job.
2. Preview using:
   `python SKILL_DIR/scripts/backup_job.py plan --source SOURCE --destination DEST --fast`
   A fast preview estimates work by size/time and may miss equal-metadata content
   changes. Use normal checksum preview when the user requests full comparison.
3. Read the preview log and check space. Explain direction, estimated changes and
   source precedence briefly. A preview is live, not a frozen execution list.
4. If a real backup is authorized, execute:
   `python SKILL_DIR/scripts/backup_job.py run --source SOURCE --destination DEST`
   Do not add `--fast` to real backups unless the user requests that tradeoff.
   `job.py` reuses matching bindings or creates a separate private profile per
   ordered source/destination pair. Identity mismatches must not be auto-rebound.
5. For long jobs, start a hidden background process with persistent stdout/stderr
   logs and save per-job metadata including paths, PID and launch time. Retain
   existing metadata for other jobs. Keep monitoring when practical; if yielding,
   say running, link logs and distinguish it from completed/verified.
6. Success requires the backend's `status=success` report and successful content
   verification. For failure or interruption inspect logs before retrying; allow
   at most one automatic retry for a diagnosed transient error, then report the
   unresolved cause. Never loop on disk identity errors, full disks, access denied
   or stale locks. Do not remove a lock until the owning process is proven stopped.

## Status and estimates

Read logs without launching another backup or full verification. Full checksum
comparison, copying and verification are distinct phases. `--check-first` delays
file transfers until comparison finishes; transfer ETA alone excludes later full
verification. Base estimates on measured progress, bytes and speed, with a range
and uncertainty; never extrapolate from file count alone or count a preview's
"Transferred" bytes as actual copied data.

## Invariants

Never substitute `sync`, `bisync`, `move`, `--inplace`, or automatic version cleanup.
Keep destination-only files. Link/reparse-point checks, disk identity checks,
version retention and the backend's final verification must remain enabled.
Source links are skipped and reported; do not call this an exhaustive link backup.
For restoration, first copy historical files to a separate recovery directory;
replacing live research files requires the user's restoration intent.
