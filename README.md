<div align="center">

# Incremental Backup

**工作盘 → 移动硬盘，只复制新增和改动的文件。**

复用硬盘里的已有副本 · 覆盖前保留旧版本 · 复制后完整校验

[![Windows](https://img.shields.io/badge/Windows-本地备份-2563eb?style=flat-square)](#快速使用) [![Python](https://img.shields.io/badge/Python-3.10%2B-2563eb?style=flat-square)](#快速使用) [![Powered by rclone](https://img.shields.io/badge/Powered_by-rclone-0f766e?style=flat-square)](#为什么基于-rclone) [![License: MIT](https://img.shields.io/badge/License-MIT-475569?style=flat-square)](LICENSE)

[快速开始](#快速使用) · [备份规则](#备份规则) · [Codex 调用](#重复调用与-codex-技能) · [恢复文件](docs/user-guide.md#旧版本与恢复)

</div>

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/backup-flow-mobile.svg">
  <img src="docs/assets/backup-flow.svg" alt="备份流程示意：工作盘 → 只复制新增与改动 → 移动硬盘；覆盖前保留旧版本，完成后校验。">
</picture>

面向 Windows 本地文件夹和外接硬盘的增量备份工作流，基于 [rclone](https://github.com/rclone/rclone)。
适合已经有一份硬盘副本、以后只想更新差异的场景；目标文件依然是能直接打开的普通文件。

> **开始前请确认方向：源目录是主版本。** 同名文件内容不同时，会先保存目标旧版本，再用源文件替换；目标独有文件保留。这里的“备份”是单向更新，不合并两边独立编辑的内容。

## 备份规则

用一次普通更新就能理解：

| 你的文件 | 两边的情况 | 本次备份会做什么 |
|---|---|---|
| `论文.pdf` | 内容相同 | 跳过，不重复传输 |
| `结果.csv` | 源文件已修改 | 归档目标旧文件，再复制新内容 |
| `新实验.xlsx` | 只在源目录存在 | 复制到目标的对应位置 |
| `历史资料.zip` | 只在移动硬盘存在 | 保留，不删除 |
| `旧文件.txt` | 从源目录删除 | 硬盘里的副本仍保留 |

**默认按内容校验和判断差异，复制完成后逐字节复核。** 增量减少传输量，但仍需要扫描和读盘；大量视频、压缩包或小文件可能让检查耗时明显长于复制本身。

## 快速使用

### 1 · 准备工具与目录

需要 **Windows、Python 3.10+** 和 [rclone 官方 Windows 版](https://rclone.org/downloads/)。
将 rclone 加入 PATH，或将官方 ZIP 解压到 `vendor/`；[安装细节](docs/user-guide.md#快速使用)。两个数据目录必须已存在。

```powershell
git clone https://github.com/Elio-SiChien/incremental-backup.git
cd incremental-backup
```

### 2 · 先预览差异

下面以 `G:\Work` → `H:\Work` 为例，替换成你的实际目录：

```powershell
python job.py plan --source "G:\Work" --destination "H:\Work" --fast
```

自动为这组路径创建或复用本地配置。预览只写工具本地日志，不复制文件到目标盘。
`--fast` 按大小与修改时间估算，可能漏掉大小、时间不变的内容变化；正式备份默认重新按内容判断。

### 3 · 正式备份并自动校验

确认预览方向和目标空间后运行：

```powershell
python job.py run --source "G:\Work" --destination "H:\Work"
```

被替换的旧文件保存在 `H:\Work.versions\运行标识\`；运行日志和报告在工具目录的 `logs/`。
**正式任务退出码为 0，且报告的 `status` 为 `success`，才表示复制和校验均已完成。**

已配置默认任务？也可使用 [Preview.cmd](Preview.cmd) 预览、[Backup.cmd](Backup.cmd) 备份、[Verify.cmd](Verify.cmd) 校验。首次绑定方式见[使用指南](docs/user-guide.md#快速使用)。

## 重复调用与 Codex 技能

安装并配置仓库内的 [incremental-backup Skill](skills/incremental-backup/SKILL.md) 后，直接告诉 Codex：

> 把 `G:\项目目录` 新增和改动的文件备份到 `H:\项目目录`，保留旧版本。

也可显式使用 `$incremental-backup`。不同路径组合保存独立配置，无需覆盖已有任务；只要求“看看差异”时只预览。

[查看全局安装与配置方法 →](docs/user-guide.md#重复调用与-codex-技能)

## 为什么基于 rclone

| 层面 | rclone 提供 | 本项目补充 |
|---|---|---|
| 数据处理 | 文件比较、复制、旧文件归档、内容复核 | 固定为单向、不删除目标独有文件的备份流程 |
| 操作入口 | 命令行及参数 | 双击启动器、按路径管理任务、Codex 自然语言调用 |
| 运行保护 | 底层传输与重试能力 | 卷与目录身份检查、路径检查、目标独占锁、运行报告 |

本项目封装成熟能力，没有另造文件复制引擎，也不提高硬盘的物理速度。[设计与职责说明 →](docs/workflow-plan.md)

## 文档与支持

<a id="旧版本与恢复"></a>
<a id="中断与限制"></a>

| 你想了解 | 入口 |
|---|---|
| 安装、默认任务、多组目录和常用命令 | [完整使用指南](docs/user-guide.md) |
| 找回被替换的文件 | [旧版本与恢复](docs/user-guide.md#旧版本与恢复) |
| 拔盘、中断、占用、磁盘身份变化 | [中断与限制](docs/user-guide.md#中断与限制) |
| 方案原理、耗时与 rclone 的区别 | [工作流方案](docs/workflow-plan.md) |
| 为什么选择这条技术路线 | [开源方案调研](docs/research.md) |
| 遇到问题或提出改进建议 | [GitHub Issues](https://github.com/Elio-SiChien/incremental-backup/issues) |

**使用边界：** 旧版本目录不是完整时间点快照；源目录中的链接会被跳过；不备份 ACL、备用数据流等 Windows 元数据。运行时请保持硬盘连接，并暂停持续写入的应用。更多边界见[使用指南](docs/user-guide.md#中断与限制)。

## 开发与验证

```powershell
python -m unittest discover -s tests -v
```

测试在临时目录验证增量复制、重复执行零传输、历史恢复和多路径配置。
本地未安装 rclone 时会跳过集成测试；[Windows CI 配置](docs/ci-windows.yml) 目前作为模板提供，尚未启用 GitHub Actions。

## 致谢与许可证

数据比较与传输由 [rclone](https://github.com/rclone/rclone) 提供。
首页结构参考 [Best-README-Template](https://github.com/othneildrew/Best-README-Template) 与 [awesome-readme](https://github.com/matiassingers/awesome-readme)，徽章使用 [Shields.io](https://shields.io/)，流程图为本项目原创示意。

本项目采用 [MIT 许可证](LICENSE)。个人路径配置、日志、研究数据和依赖二进制不提交到本仓库。
