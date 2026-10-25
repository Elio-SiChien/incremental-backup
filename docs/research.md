# 开源方案调研与选型

调研日期：2026-10-25。目标：复用已有目标副本，把工作目录新增和改动文件单向复制到外接盘；保留目标独有数据并支持覆盖前恢复。

| 方案 | 原理与优点 | 对本场景的取舍 |
|---|---|---|
| [rclone/rclone](https://github.com/rclone/rclone) | `copy` 跳过相同文件、不删除目标额外文件；checksum、dry-run、backup-dir、check 可组合 | 选用：直接复用现有目录，普通文件可直接打开，适合命令化和技能封装 |
| [restic/restic](https://github.com/restic/restic) | 加密快照、内容分块去重，只存新增块 | 适合完整历史和巨型改动文件；需初始化独立仓库，不能把当前普通目录直接当成其既有去重仓库，恢复需 restic |
| [FreeFileSync](https://freefilesync.org/) | 文件夹比较与同步，图形化查看差异，支持版本保存 | 适合想主要用鼠标操作的人；配置更新规则时注意数据库行为。GitHub 上存在代码镜像，本文不把镜像当作官方发布源 |

FreeFileSync 官方说明：Mirror 会删除目标额外文件；Update 可保留源端删除的文件，但新版数据库模式还追踪目标侧删除等状态。因此本项目不用一个含糊的“同步”按钮，明确提供单向 copy 规则。
来源：[官方同步设置](https://freefilesync.org/manual.php?topic=synchronization-settings)。

rclone 官方 `copy` 文档明确：相同文件不传输，不删除目标已有额外文件；内容复制到目标目录本身，不多套一层源目录。
来源：[rclone copy](https://rclone.org/commands/rclone_copy/)。

`--backup-dir` 会把将被覆盖的目标旧文件按原相对目录移动到指定位置；官方也建议脚本用日期命名。这里使用 UTC 时间加随机标识，避免重复运行碰撞。版本目录放目标旁边，避免递归重叠。
来源：[rclone backup-dir](https://rclone.org/docs/#backup-dir-dir)。

`check --one-way` 仅要求源文件在目标匹配，允许目标有额外文件；`--download` 读取内容逐字节比较，避免只依赖元数据。
来源：[rclone check](https://rclone.org/commands/rclone_check/)。

本地链接和目录联接默认被 rclone 跳过。目标目录联接可能影响写入边界，封装器因此在操作前拒绝目标树中的重解析点。
来源：[本地文件系统链接语义](https://rclone.org/local/#symlinks-junction-points)。

restic 使用内容定义分块，其设计允许只存储新块，即使文件内部插入、删除字节。若后续需要长期快照或巨大文件的小幅改动去重，可作为额外备份层；当前不迁移已有 H 盘普通文件副本。
来源：[restic 设计文档](https://github.com/restic/restic/blob/master/doc/design.rst)。

## 最终设计

沿用 rclone 的比较、复制、归档、复核实现；Python 只封装固定操作、目录/磁盘身份校验、独占锁和运行报告。
默认只预览的启动入口，明确的正式执行入口，支持重复运行；不实现新的数据传输算法，不 fork 上游代码。
保留可见文件结构，覆盖前历史放同一外接盘的旁目录。G 为主版本，H 为备份；不做双向冲突合并。

验收标准：未变文件零传输；同大小同时间的内容变化可检出；改动前旧文件可恢复；H 独有文件不丢失；误盘、嵌套路径和目标联接拒绝；错误返回非零且有报告。
