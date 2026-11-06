#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日仓库同步（最小可用版）

流程：白名单文件 -> git add -> 有变更才 commit -> 逐个远端 push（带重试）

硬约束：
  1. 退出码恒为 0：任何异常只写日志，绝不阻断上游每日任务
  2. 只动白名单路径；.workbuddy/ 等敏感目录永不入库
  3. 出库前有一道独立闸门，检查暂存区里是否混入禁入路径
  4. 不依赖外部环境变量（会显式清掉 HTTP_PROXY，避免继承了已失效的代理）
"""

import os
import sys
import time
import shutil
import tomllib
import datetime
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # 仓库根目录
OPS = Path(__file__).resolve().parent                  # _ops/
LOG_DIR = OPS / "logs"
LOCK = OPS / ".lock"
CFG_PATH = OPS / "config.toml"

# 出现即中止推送的路径前缀（防泄露最后一道闸）
FORBIDDEN_PREFIXES = (".workbuddy/", "_ops/logs/", "_ops/state/")

# 定位到的 git / ssh 可执行文件，run() 里初始化
GIT_BIN = "git"
SSH_BIN = ""


def resolve_git(cfg=None):
    """定位 git.exe。

    不能依赖 PATH：本机 git 是 WorkBuddy 内置的 PortableGit，没进系统 PATH，
    而 Windows 计划任务继承的是系统环境，跑起来会直接 FileNotFoundError。
    顺序：配置指定 -> PATH -> WorkBuddy PortableGit -> 常见安装位置。
    """
    # 1) 配置里显式指定
    try:
        explicit = (cfg or {}).get("git", {}).get("executable", "") or ""
    except Exception:
        explicit = ""
    if explicit:
        p = Path(os.path.expandvars(os.path.expanduser(explicit)))
        if p.is_file():
            return str(p)

    # 2) PATH
    found = shutil.which("git")
    if found:
        return found

    # 3) WorkBuddy 内置 PortableGit（版本目录名会随更新变化，取排序最后一个）
    base = Path.home() / ".workbuddy" / "binaries" / "PortableGit" / "versions"
    try:
        hits = sorted(base.glob("*/cmd/git.exe"))
        if hits:
            return str(hits[-1])
        hits = sorted(base.glob("*/mingw64/bin/git.exe"))
        if hits:
            return str(hits[-1])
    except Exception:
        pass

    # 4) 常见安装位置
    for cand in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Git/cmd/git.exe",
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files (x86)/Git/cmd/git.exe"),
    ):
        try:
            if cand.is_file():
                return str(cand)
        except Exception:
            continue
    return ""


def resolve_ssh(cfg=None):
    """定位 ssh.exe。SSH 推送不受凭据管理器影响，是自动化最稳的通道。

    顺序：配置指定 -> PATH -> WorkBuddy PortableGit 的 usr/bin/ssh.exe。
    找不到也不致命：https 远端照旧能走 GCM。
    """
    try:
        explicit = (cfg or {}).get("git", {}).get("ssh_executable", "") or ""
    except Exception:
        explicit = ""
    if explicit:
        p = Path(os.path.expandvars(os.path.expanduser(explicit)))
        if p.is_file():
            return str(p)

    found = shutil.which("ssh")
    if found:
        return found

    base = Path.home() / ".workbuddy" / "binaries" / "PortableGit" / "versions"
    for pat in ("*/usr/bin/ssh.exe", "*/bin/ssh.exe"):
        try:
            hits = sorted(base.glob(pat))
            if hits:
                return str(hits[-1])
        except Exception:
            pass
    return ""


def now():
    return datetime.datetime.now()


def log(msg, fh=None):
    line = "[{}] {}".format(now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        print(line)
    except Exception:
        pass
    if fh:
        fh.write(line + "\n")
        fh.flush()


def git(args, proxy=None, timeout=120):
    """执行 git。proxy=None 表示强制直连；proxy='' 同 None；传字符串则走该代理。"""
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")}
    # 自动化运行绝不弹凭据窗口：拿不到凭据就立刻失败、写日志，下次运行自动补推。
    # 不加这三行，Git Credential Manager 会每重试一次弹一次 GUI，非常烦人。
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_ASKPASS"] = "echo"
    # SSH 通道：指定 ssh 绝对路径（计划任务里 PATH 没有 ssh），
    # BatchMode 保证绝不交互提问，accept-new 避免首次连接卡在 yes/no。
    if SSH_BIN:
        env["GIT_SSH_COMMAND"] = (
            '"{}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new'.format(SSH_BIN))
    cmd = [GIT_BIN, "-c", "core.quotepath=false"]
    if proxy:
        cmd += ["-c", "http.proxy=" + proxy, "-c", "https.proxy=" + proxy]
    else:
        cmd += ["-c", "http.proxy=", "-c", "https.proxy="]
    cmd += args
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return 124, "git 命令超时（{}s）: {}".format(timeout, " ".join(args))
    except Exception as e:
        return 1, "git 调用异常: {}".format(e)


def acquire_lock():
    if LOCK.exists():
        try:
            # 最坏情况：多个远端 x 重试 x 超时，约 12 分钟。超过 30 分钟视为僵尸锁。
            age = now().timestamp() - LOCK.stat().st_mtime
            if age < 1800:
                return False
            LOCK.unlink()
        except Exception:
            pass
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock():
    try:
        LOCK.unlink()
    except Exception:
        pass


def is_ignored(rel_path):
    rc, _ = git(["check-ignore", "-q", "--", rel_path])
    return rc == 0


def collect_targets(cfg):
    """按白名单展开实际文件，跳过不存在与被 gitignore 命中的。"""
    targets, skipped = [], []
    for pat in cfg["include"]["paths"]:
        hits = sorted(ROOT.glob(pat))
        if not hits:
            skipped.append(pat + " （无匹配）")
            continue
        for h in hits:
            if not h.is_file():
                continue
            rel = h.relative_to(ROOT).as_posix()
            if is_ignored(rel):
                skipped.append(rel + " （被 .gitignore 排除）")
                continue
            targets.append(rel)
    return targets, skipped


def guard(staged_files):
    """出库前闸门：暂存区不允许出现禁入路径。返回 (通过, 命中列表)。"""
    bad = [f for f in staged_files if f.startswith(FORBIDDEN_PREFIXES)
           or "/.workbuddy/" in f or f.startswith(".workbuddy")]
    return (len(bad) == 0), bad


def push_remote(r, branch, cfg, fh):
    name = r.get("name", "?")
    url = r.get("url", "")
    proxy = r.get("proxy", "") or None
    required = bool(r.get("required", False))
    retries = int(cfg["sync"].get("retries", 2))
    backs = list(cfg["sync"].get("retry_backoff_seconds", [5, 15]))
    timeout = int(cfg["sync"].get("timeout", 120))

    if "REPLACE_ME" in url:
        log("[{}] 未配置仓库地址，跳过（请改 _ops/config.toml）".format(name), fh)
        return False

    tag = "直连" if not proxy else "代理 " + proxy
    attempts = retries + 1
    for i in range(attempts):
        t0 = time.time()
        rc, out = git(["push", url, "HEAD:refs/heads/" + branch], proxy=proxy, timeout=timeout)
        cost = time.time() - t0
        if rc == 0:
            log("[{}] 推送成功（{}，{:.1f}s）".format(name, tag, cost), fh)
            return True
        log("[{}] 第 {}/{} 次推送失败（{:.1f}s）：{}".format(
            name, i + 1, attempts, cost, out.splitlines()[0] if out else "无输出"), fh)

        # 凭据/密钥问题不是瞬时故障，重试没有意义，直接停手
        low = out.lower()
        if any(k in low for k in ("authentication failed", "could not read username",
                                  "terminal prompts disabled", "permission denied",
                                  "403 forbidden", "401 unauthorized", "repository not found")):
            log("[{}] 凭据/密钥缺失或无效，已跳过剩余重试。".format(name), fh)
            if url.startswith("git@"):
                log("[{}] 处理：把 ~/.ssh/id_ed25519.pub 的公钥添加到该平台，见 _ops/README.md".format(name), fh)
            else:
                log("[{}] 处理：改用 SSH 远端，或手动推送一次保存凭据，见 _ops/README.md".format(name), fh)
            break

        if i < attempts - 1:
            time.sleep(backs[i] if i < len(backs) else backs[-1] if backs else 5)

    log("[{}] {}：本次未能推送，commit 已留在本地，下次运行会自动补推".format(
        name, "错误" if required else "警告"), fh)
    return False


def run(fh):
    global GIT_BIN, SSH_BIN

    with open(CFG_PATH, "rb") as f:
        cfg = tomllib.load(f)

    # --- 0. 定位 git / ssh（不依赖 PATH，计划任务环境里通常都没有）---
    GIT_BIN = resolve_git(cfg)
    if not GIT_BIN:
        log("未找到 git 可执行文件。请在 _ops/config.toml 的 [git] executable 里填绝对路径", fh)
        return
    log("使用 git：" + GIT_BIN, fh)

    SSH_BIN = resolve_ssh(cfg)
    log("使用 ssh：" + (SSH_BIN or "未找到（SSH 远端将不可用，https 远端不受影响）"), fh)

    if not (ROOT / ".git").exists():
        log("仓库未初始化（缺少 .git），请先执行 git init", fh)
        return

    branch = cfg["repo"].get("branch", "main")
    msg_tpl = cfg["repo"].get("commit_message", "update: {date} 每日数据更新")

    # --- 1. 白名单展开 ---
    targets, skipped = collect_targets(cfg)
    for s in skipped:
        log("跳过：" + s, fh)
    if not targets:
        log("白名单未匹配到任何文件，结束", fh)
        return
    log("白名单命中 {} 个文件".format(len(targets)), fh)

    # --- 2. add ---
    rc, out = git(["add", "--"] + targets)
    if rc != 0:
        log("git add 失败：" + out, fh)
        return

    # --- 3. 是否有变更 ---
    rc, _ = git(["diff", "--cached", "--quiet"])
    if rc == 0:
        log("无变更，跳过提交与推送", fh)
        return

    rc, out = git(["diff", "--cached", "--name-only"])
    staged = [x for x in out.splitlines() if x.strip()]

    # --- 4. 出库闸门 ---
    ok, bad = guard(staged)
    if not ok:
        log("闸门拦截：暂存区出现禁入路径，已中止推送：{}".format(", ".join(bad)), fh)
        git(["reset"])
        return
    log("本次变更 {} 个文件：{}".format(
        len(staged), ", ".join(staged[:8]) + (" ..." if len(staged) > 8 else "")), fh)

    # --- 5. commit ---
    message = msg_tpl.format(date=now().strftime("%Y-%m-%d"))
    rc, out = git(["commit", "-m", message])
    if rc != 0:
        log("提交失败：" + out, fh)
        return
    log("提交成功：" + message, fh)

    # --- 6. push ---
    for r in cfg.get("remotes", []):
        if not r.get("enabled"):
            log("[{}] 已禁用，跳过".format(r.get("name")), fh)
            continue
        push_remote(r, branch, cfg, fh)


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logpath = LOG_DIR / ("sync-" + now().strftime("%Y%m%d") + ".log")
    fh = None
    try:
        fh = open(logpath, "a", encoding="utf-8")
        log("=== 同步开始 ===", fh)
        if not acquire_lock():
            log("已有同步进程在运行，本次跳过", fh)
            return
        try:
            run(fh)
        finally:
            release_lock()
        log("=== 同步结束 ===", fh)
    except Exception:
        import traceback
        try:
            log("未捕获异常：\n" + traceback.format_exc(), fh)
        except Exception:
            pass
    finally:
        if fh:
            fh.close()
    # 恒为 0：绝不因本脚本失败而中断上游任务
    return 0


if __name__ == "__main__":
    sys.exit(main())
