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

> 首次推送前必须在**交互式终端**里手动跑一次，确认认证已通过。计划任务是非交互式的，届时不会弹窗要密码——凭据没准备好就会静默失败（但 commit 会留在本地，下次自动补推）。

## 认证方式：SSH（推荐，已启用）

远端地址现在用 SSH 形式 `git@gitee.com:vickrs/history-daily.git`。**SSH 是无人值守场景唯一可靠的通道**：不需要令牌、不走凭据管理器、永不弹窗，密钥认证在非交互式环境下也能直接通过。

已生成并验证的密钥：

| 项 | 值 |
|---|---|
| 私钥 | `C:\Users\ck108\.ssh\id_ed25519` |
| 公钥 | `C:\Users\ck108\.ssh\id_ed25519.pub`（注释为 `Gitee SSH Key`） |
| Gitee 认证 | ✅ 实测 `Hi Vickrs(@vickrs)! You've successfully authenticated` |
| GitHub 认证 | ❌ 公钥尚未加到 GitHub 账号，报 `Permission denied (publickey)` |

`sync.py` 运行时会自动定位 `ssh.exe`（计划任务的 PATH 里没有），并注入：

```
GIT_SSH_COMMAND="<ssh路径>" -o BatchMode=yes -o StrictHostKeyChecking=accept-new
```

`BatchMode=yes` 保证绝不交互提问，`accept-new` 避免首次连接卡在 yes/no 提示上。

### 给 GitHub 镜像加同一把公钥

同一把密钥可以同时注册到多个平台，不需要再生成新的：

```powershell
Get-Content C:\Users\ck108\.ssh\id_ed25519.pub
```

把输出整行复制，粘贴到 GitHub → Settings → SSH and GPG keys → New SSH key。

然后编辑 `_ops/config.toml`，把 GitHub 远端的 `REPLACE_ME` 换成你的 GitHub 用户名，`enabled` 改 `true`。

验证是否生效（不会推送，只测认证）：

```powershell
& "C:\Users\ck108\.workbuddy\binaries\PortableGit\versions\1.3.0\usr\bin\ssh.exe" -T git@github.com
```

成功时返回 `Hi <用户名>! You've successfully authenticated...`。

### 备用：HTTPS + 私人令牌

若 SSH 不可用，把 `url` 改回 `https://gitee.com/vickrs/history-daily.git`，然后在交互式终端手动推送一次、弹窗里填：

- 用户名：`vickrs`
- 密码：**Gitee 私人令牌**（不是登录密码）。Gitee → 头像 → 设置 → 安全设置 → 私人令牌 → 生成新令牌，勾选 `projects` 权限

保存后进入 Windows 凭据管理器（目标形如 `git:https://gitee.com`），此后不再询问。

> 如果推送被拒绝提示「Updates were rejected」，说明建仓时勾选了「使用 Readme 初始化」，改用 `push -f -u origin main`（空仓库强制推送安全）。

## 安全闸门

两道，互相独立：

1. `.gitignore` 排除 `.workbuddy/`、推送载荷 json、一次性脚本、日志、本地敏感配置
2. `sync.py` 里 `FORBIDDEN_PREFIXES` 检查——提交前若发现暂存区混入 `.workbuddy/` 等路径，直接 `git reset` 中止推送

## 已知限制

- **GitHub 镜像待启用**：SSH 到 GitHub 网络可达（22 端口通，主机指纹 `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` 已与官方核对一致），但公钥还没加到 GitHub 账号，认证报 `Permission denied (publickey)`。`config.toml` 里 GitHub 远端默认 `enabled = false`。加好公钥后改 `enabled = true` 即可；此前的 commit 会留在本地，恢复后自动补推，不会丢。
- **不做压缩包归档**：日均正文 3 KB，git 历史十年不足 30 MB，远低于平台限额。若将来接入影像/大文件输出，再启用按月打包 + 本地容量管控。
