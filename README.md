# Incremental Backup · 增量备份工作流

基于 [rclone](https://github.com/rclone/rclone) 的 Windows 本地文件备份工具。
只复制新增、内容改动的文件，保留目标盘独有文件，覆盖前留存旧版本，完成后逐字节复核。
适用于工作盘 → 移动硬盘，目标目录原有文件可以直接复用，无需重新全量复制。

> 本工具以源目录为主版本。同名文件有差异时，即使目标文件更新，也会先归档目标旧文件，再用源文件替换。不要用它合并两边独立编辑的工作。

## 快速使用

需要 Python 3.10+ 和 [rclone 官方 Windows 版](https://rclone.org/downloads/)。
将 rclone 加入 PATH，或把官方 ZIP 解压到本项目的 `vendor/`，形成 `vendor/rclone-版本-windows-amd64/rclone.exe`。
本机测试版本为 rclone 1.75.2。可从对应官方版本目录的 SHA256SUMS 核对 ZIP 校验值。
Windows 启动器使用 `python` 命令；若你的环境使用 `py`，请在终端用 `py backup.py ...`。

先进入工具目录，绑定已经存在的两个目录（下面是示例，请替换）：

```powershell
python backup.py bind --source "G:\Work" --destination "H:\Work"
python backup.py plan
```

`bind` 只在工具目录写入 `config.local.json`，记录方向、卷序列号和目录标识，避免盘符被另一块硬盘占用后误写。两个数据目录必须已存在。配置不提交 GitHub。

`plan` 是预览，不写入 G/H 数据，只在工具目录产生本地日志；检查日志后正式运行：

```powershell
python backup.py run
```

也可以双击 `Preview.cmd` 预览、`Backup.cmd` 备份、`Verify.cmd` 校验。备份启动器有 Y/N 提示。
随时单独复核：

```powershell
python backup.py verify
```

## 备份规则

| 情况 | 行为 |
|---|---|
| 两边相对路径、内容相同 | 不复制文件内容 |
| 源目录新增文件 | 复制到目标同一路径 |
| 同一路径内容改动 | 目标旧文件移入版本目录，再复制源文件 |
| 文件只在目标存在 | 保留，不删除 |
| 源文件被删除或改名 | 目标旧文件保留；改名后的新路径按新增复制 |
| 空目录 | 创建对应目录 |
| 隐藏文件 | 默认包含，不自动排除 `.git` 等目录 |
| 源目录内部符号链接、目录联接 | rclone 跳过并写入警告，不备份链接指向内容 |
| 目标目录内链接或重解析点 | 拒绝运行，先人工检查 |
| 盘符、卷或目录身份变化 | 拒绝运行，避免写错盘 |

实际调用的是 `rclone copy --checksum --backup-dir ...`，不是镜像删除模式。
两个目录是本地路径，不使用云端，也不把数据发送到 GitHub。
清除子进程的 `RCLONE_*` 环境变量，并用内存空配置，避免既有 rclone 设置改变本工具行为。

默认用大小和内容校验和判断是否复制。**增量指减少传输，不表示可以跳过扫描和读盘。**
备份结束后用 `rclone check --one-way --download` 逐字节读取两边源文件对应内容复核；目标额外文件不视为失败。
日志与 JSON 报告在 `logs/`，`status=success` 且退出码为 0 才代表此次操作完成；预览状态是 `preview`。
目录不可用、磁盘身份不符等预检查失败会直接在终端返回错误和非零退出码，尚不会创建运行报告。
校验覆盖文件内容，不校验 Windows ACL、备用数据流、所有者、空目录元数据或历史版本完整性。

可以用 `python backup.py plan --fast` 按大小和时间快速预览；这可能漏掉大小、时间相同的内容变化。
`run --fast` 仍执行完整内容复核，发现漏项会失败；此时使用默认 `run` 修复。
预览是实时判断，不是冻结清单，预览后继续修改文件会改变正式执行结果。

## 旧版本与恢复

如果目标为 `H:\Work`，旧版本保存在旁边：

```text
H:\Work\                         当前文件，直接用资源管理器打开
H:\Work.versions\
  20261025T...Z-随机标识\           某次运行被替换的目标旧文件
    子目录\论文.docx
```

版本目录只包含该次被替换的旧文件，**不是完整时间点快照**。初次接入也不会为所有未变文件再做一份副本。
不自动清理历史，以便你决定保留多久；目标空闲容量需容纳新增数据、历史和传输临时文件。

恢复时优先从 H 盘当前目录取文件；需要覆盖前版本时，到对应版本目录查找同一相对路径。
先复制到单独的恢复目录，打开确认后再决定是否替换工作文件。例如：

```powershell
Copy-Item -LiteralPath "H:\Work.versions\某次运行\子目录\论文.docx" -Destination "G:\Recovery\论文.docx"
```

提前创建 `G:\Recovery`。本工具不提供自动覆盖工作盘的恢复命令。

## 中断与限制

- 运行前关闭持续写入的数据程序。它不是 VSS 或数据库一致性快照；校验通过也不保证应用级多文件事务一致性。
- 不拔盘，完成后安全弹出。失败或中断后查看日志，可重新运行，已相同文件会跳过。
- 版本归档与新文件写入不是整体事务。中断后旧内容可能已归档，目标对应路径尚未更新；请先查看版本目录，再重跑。
- 同一个目标只允许一个写入任务。进程被强制结束可能留下目标旁的 `.目录名.incremental-backup.lock`。确认没有备份进程后才能手动移除锁。
- 运行期间不要由其他工具修改目标或替换目录联接。本工具的预检查不防御并发恶意篡改。
- 盘身份检查防止常见误操作，不是密码学硬件认证。更换/格式化磁盘、重建目录后，人工核对再另存配置并重新绑定。
- 复制以整个改动文件为单位。100 GB 文件只改一处，也可能复制整个文件；需要分块去重时应另建 restic 仓库。
- 同步副本不能替代异地备份。当前工作流提供一份外接盘副本和覆盖历史；可后续另加一份离线或异地副本。

## 重复调用与 Codex 技能

以后可以直接说：“把 `G:\Project` 新增和改动的文件备份到 `H:\Project`，保留旧版本。”
全局 `incremental-backup` Skill 支持自动匹配请求；也可显式写 `$incremental-backup`。
方案及与 rclone 的职责区别见 [全局技能方案](docs/workflow-plan.md)。

多组目录无需覆盖默认配置：

```powershell
python job.py plan --source "G:\Project" --destination "H:\Project" --fast
python job.py run --source "G:\Project" --destination "H:\Project"
```

程序复用匹配的已有绑定，新组合保存到不公开的 `profiles/`。正式备份默认仍用内容比较和完整复核。
全局技能的入口为 `scripts/backup_job.py`，安装时在技能目录增加私有 `runtime.local.json`，
格式为 `{"repository": "本机工具仓库的绝对路径"}`。这让其他工作目录里的聊天也能定位工具。

日常流程：接上移动硬盘 → 双击 `Preview.cmd` 看日志 → 双击 `Backup.cmd` → 确认成功 → 安全弹出。
不默认设置定时任务，避免移动硬盘不在时反复运行。确需计划任务时，程序支持直接用命令调用并返回退出码。

仓库包含 `skills/incremental-backup/SKILL.md`。将此文件夹安装到 `~/.codex/skills/` 后，可说：

> 使用 $incremental-backup 预览我的备份差异。
>
> 使用 $incremental-backup 将工作盘的新增和改动文件备份到移动硬盘。

配置运行指针后无需每次提供工具仓库位置。技能遵守预览与正式备份的授权范围，报告日志和版本位置。

## 开发与验证

```powershell
python -m unittest discover -s tests -v
```

测试仅在临时目录创建数据。包含真实 rclone 的预览、增量、同大小同时间内容变化、重复执行零传输、保留目标独有文件、源端删除不传播、错误检测和历史恢复。
未安装 rclone 时本地集成测试会跳过；CI 必须安装，否则失败。
Windows GitHub Actions 测试模板见 `docs/ci-windows.yml`。当前发布凭据不含 `workflow` 权限，
因此没有自动启用 Actions；以后可在 GitHub 网页将其放到 `.github/workflows/test.yml` 启用。

公开仓库仅保存代码、文档、测试和技能。个人配置、日志、官方二进制、研究数据不提交。
调研依据和选型见 [docs/research.md](docs/research.md)。MIT 许可证；rclone 是独立依赖，使用其自身 MIT 许可证。
