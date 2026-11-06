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

## git 与 ssh 的定位

本机装了两套 git：

| 来源 | 路径 | 用途 |
|---|---|---|
| 全局安装（2026-11-06 装，2.56.0.windows.4） | `G:\app\Git\cmd\git.exe` | **手动操作与自动化统一用这套** |
| WorkBuddy 内置 PortableGit | `~\.workbuddy\binaries\PortableGit\versions\*\cmd\git.exe` | WorkBuddy 自用，不要删、不要依赖 |

`config.toml` 的 `[git]` 段已把两套路径**写死**，而不是靠 PATH 自动探测。原因：不同运行环境（交互式终端 / 计划任务 / 编辑器内嵌终端）的 PATH 排序不同，会自动选中不同的 git，行为不可复现。写死后走到哪都是同一套。

```toml
[git]
executable     = "G:\\app\\Git\\cmd\\git.exe"
ssh_executable = "G:\\app\\Git\\usr\\bin\\ssh.exe"
```

若将来换了安装位置，改这两行即可。留空则退回自动探测顺序：配置 → PATH → 内置 PortableGit → `Program Files\Git`。

手动敲命令现在直接用 `git` 就行（`G:\app\Git\cmd` 已在系统 PATH 里）。

## 接入每日定时任务

**方式是挂在每日正文任务本身的最后一步**，不另开 Windows 计划任务。

WorkBuddy 的自动化任务 `历史上的今天`（每日 07:00）的 prompt 末尾已有第 6 步：

```
cd /c/Users/ck108/WorkBuddy/automation-2026-07-01-10-57-52
"C:/Users/ck108/.workbuddy/binaries/python/envs/default/Scripts/python.exe" _ops/sync.py
```

这样接的理由：**没有新正文就没有推送的必要**。正文生成失败的那天，本来也没有可推的东西；另开一个定时任务反而会在空跑时制造无意义的活动。

代价与兜底：假如某天正文生成了但推送失败（断网等），那天不会有重试。但 commit 已经落在本地，**第二天一旦推送成功，会把积压的提交一起带上去**，不会丢。日志里会留痕，两天后仍未成功才需要人工看一眼。

### 手工补推

任何时候想立刻同步（例如改完配置）：

```powershell
cd C:\Users\ck108\WorkBuddy\automation-2026-07-01-10-57-52
& "C:\Users\ck108\.workbuddy\binaries\python\envs\default\Scripts\python.exe" _ops\sync.py
```

GitHub 单独失败想补一次：

```powershell
git push github main
```

## 认证方式：SSH（推荐，已启用）

远端地址现在用 SSH 形式 `git@gitee.com:vickrs/history-daily.git`。**SSH 是无人值守场景唯一可靠的通道**：不需要令牌、不走凭据管理器、永不弹窗，密钥认证在非交互式环境下也能直接通过。

已生成并验证的密钥：

| 项 | 值 |
|---|---|
| 私钥 | `C:\Users\ck108\.ssh\id_ed25519` |
| 公钥 | `C:\Users\ck108\.ssh\id_ed25519.pub`（注释为 `Gitee SSH Key`） |
| Gitee 认证 | ✅ 实测 `Hi Vickrs(@vickrs)! You've successfully authenticated` |
| GitHub 认证 | ✅ 实测 `Hi VIckrs325! You've successfully authenticated`（账号名是 `VIckrs325`，大写 I） |

`sync.py` 运行时会自动定位 `ssh.exe`（自动化任务的环境里 PATH 可能不含 Git 目录），并注入：

```
GIT_SSH_COMMAND="<ssh路径>" -o BatchMode=yes -o StrictHostKeyChecking=accept-new
```

`BatchMode=yes` 保证绝不交互提问，`accept-new` 避免首次连接卡在 yes/no 提示上。

### 双远端状态（2026-11-07 已全部打通）

同一把密钥 `id_ed25519` 同时注册在 Gitee 和 GitHub，无需第二把：

| 远端 | 地址 | 状态 |
|---|---|---|
| Gitee（origin） | `git@gitee.com:vickrs/history-daily.git` | ✅ 主库，`required = true` |
| GitHub（github） | `git@github.com:VIckrs325/history-daily.git` | ✅ 镜像，`required = false` |

GitHub 仓库必须是**空仓**（建仓时不要勾 README / .gitignore / license），否则首次推送会因历史不相关被拒。

日常手工推送（两个远端）：

```powershell
git push origin main
git push github main
```

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

- **GitHub 推送比 Gitee 慢**：实测 Gitee 1.6s、GitHub 6.4s。两者串行执行，整体仍在 10s 内。GitHub 侧若失败只记 WARN、不重试（`required = false`），不影响 Gitee 主库。积压的 commit 会在下次推送时一起补上去，不会丢。
- **GitHub 走 SSH 而非 HTTPS**：本机 `github.com` 的 HTTPS 直连被阻断（`Connection reset`），只有 22 端口通。主机指纹 `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU` 已与官方核对一致。
- **不做压缩包归档**：日均正文 3 KB，git 历史十年不足 30 MB，远低于平台限额。若将来接入影像/大文件输出，再启用按月打包 + 本地容量管控。
