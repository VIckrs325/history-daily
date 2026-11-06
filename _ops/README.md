# _ops —— 每日仓库同步

每日正文生成后，把白名单文件提交并推送到远端。设计成**上游任务的后置附加步骤**，自身失败绝不影响主任务。

## 文件

| 文件 | 作用 |
|---|---|
| `config.toml` | 全部配置（提交模板、白名单、远端地址、代理、重试参数） |
| `sync.py` | 同步脚本，无第三方依赖（仅用 Python 3.11+ 内置 `tomllib`） |
| `logs/` | 每日运行日志 `sync-YYYYMMDD.log`，不入库 |

## 手动跑一次

```bash
"C:/Users/ck108/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
  "C:/Users/ck108/WorkBuddy/automation-2026-07-01-10-57-52/_ops/sync.py"
```

退出码恒为 0。看结果要看日志或 stdout，不要看退出码。

## 关于 git 不在 PATH 上

本机的 git 是 WorkBuddy 内置的 PortableGit，**没有加入系统 PATH**，所以 PowerShell 里直接敲 `git` 会报「无法识别」。这不影响自动化——`sync.py` 会自己找：

1. `config.toml` 里 `[git] executable` 指定的路径
2. 系统 PATH
3. WorkBuddy 内置 PortableGit（`~/.workbuddy/binaries/PortableGit/versions/*/cmd/git.exe`，取最新版本目录）
4. `Program Files\Git`、`%LOCALAPPDATA%\Programs\Git`

只有手动操作时需要完整路径：

```powershell
& "C:\Users\ck108\.workbuddy\binaries\PortableGit\versions\1.3.0\cmd\git.exe" push -u origin main
```

若想让 `git` 命令长期可用，把上面 `\cmd` 目录加进用户 PATH 即可（注意 WorkBuddy 升级后版本目录名可能变，届时需要改）。

## 接入每日定时任务

用**独立的 Windows 计划任务**，比正文任务晚 30 分钟，彻底解耦：

```powershell
schtasks /create /tn "WB-HistoryDaily-Sync" ^
  /tr "\"C:\Users\ck108\.workbuddy\binaries\python\envs\default\Scripts\python.exe\" \"C:\Users\ck108\WorkBuddy\automation-2026-07-01-10-57-52\_ops\sync.py\"" ^
  /sc daily /st 06:00 /f
```

删除：`schtasks /delete /tn "WB-HistoryDaily-Sync" /f`

> 首次推送前必须在**交互式终端**里手动跑一次并输入令牌，让 Windows 凭据管理器记住它。计划任务是非交互式的，届时不会弹窗要密码——没存过就会静默失败。

## 首次配置凭据（只需一次）

`sync.py` 在运行时会把 `GIT_TERMINAL_PROMPT=0`、`GCM_INTERACTIVE=never`、`GIT_ASKPASS=echo` 传给 git，**所以自动化运行永远不会弹凭据窗口**——拿不到凭据就直接失败写日志，下次运行自动补推。

凭据必须先在交互式终端存一次：

```powershell
cd C:\Users\ck108\WorkBuddy\automation-2026-07-01-10-57-52
& "C:\Users\ck108\.workbuddy\binaries\PortableGit\versions\1.3.0\cmd\git.exe" push -u origin main
```

弹窗里填：

- 用户名：`vickrs`
- 密码：**Gitee 私人令牌**（不是登录密码）。Gitee → 头像 → 设置 → 安全设置 → 私人令牌 → 生成新令牌，勾选 `projects` 权限

保存后进入 Windows 凭据管理器（目标形如 `git:https://gitee.com`），此后不再询问。

> 如果推送被拒绝提示「Updates were rejected」，说明建仓时勾选了「使用 Readme 初始化」，改用 `push -f -u origin main`（空仓库强制推送安全）。

## 安全闸门

两道，互相独立：

1. `.gitignore` 排除 `.workbuddy/`、推送载荷 json、一次性脚本、日志、本地敏感配置
2. `sync.py` 里 `FORBIDDEN_PREFIXES` 检查——提交前若发现暂存区混入 `.workbuddy/` 等路径，直接 `git reset` 中止推送

## 已知限制

- **GitHub 镜像当前不可用**：本机 `github.com` 直连被阻断（`Connection reset`），原 WorkBuddy 代理端口 `127.0.0.1:56117` 已失效。`config.toml` 里 GitHub 远端默认 `enabled = false`。等有稳定代理后填上 `proxy` 再打开即可；此前的 commit 会留在本地，恢复后自动补推，不会丢。
- **不做压缩包归档**：日均正文 3 KB，git 历史十年不足 30 MB，远低于平台限额。若将来接入影像/大文件输出，再启用按月打包 + 本地容量管控。
