---
name: incremental-backup
description: Preview, run and verify one-way local incremental backups using rclone with retained old versions. Use for backing up a work folder to an external drive and repeating a configured backup job.
---

Use the repository's `backup.py` rather than assembling a separate copy engine.
Find the repository location from the user's workspace; keep its local config and
logs private. Read its README for setup and restoration instructions.

For a configured job:

1. Run `python backup.py plan` from the repository and review the log. This writes
   only local logs, without changing the source or destination data.
2. Explain the direction and relevant differences. A plan is a live preview, not
   a frozen list; changes made afterwards can affect execution.
3. If the user authorized a real backup, run `python backup.py run`. It archives
   overwritten destination files and verifies source content against destination.
   A request for a proposal, research or preview alone does not authorize copying.
4. Report the exit status, JSON report, log and version directory. A failed or
   interrupted job is incomplete even if some files have already copied. Diagnose
   the error and rerun the same job when safe; never infer success from copied files.

For a new job, use `bind --source ABSOLUTE_PATH --destination ABSOLUTE_PATH`.
Binding records disk/folder identity in a local config and does not write to the
data folders. Do not silently replace an existing binding or remove a stale lock:
first inspect why the disk identity changed or whether a backup is still running.

G is the user's authoritative work drive and H the external backup in the initial
use case; local configuration holds actual paths. Destination-only files remain.
Never substitute `sync`, `bisync`, `move`, `--inplace`, or automatic history deletion.
Only publish scripts and documentation to GitHub, excluding configs, logs and data.
If restoring, first copy the selected historical file to a separate recovery folder
and inspect it; replacing live research files needs the user's restoration intent.
