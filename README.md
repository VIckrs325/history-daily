# 历史上的今天 · 每日简报

每天自动生成的一页「历史上的今天」，覆盖三个领域各一至两个事件：

1. **科学发现 / 技术发明** —— 理论突破、实验发现、航天里程碑
2. **马克思主义 / 国际共产主义运动史** —— 重要会议、著作、工人运动
3. **中国革命史** —— 长征、抗战、解放战争中的关键节点

内容以公开史料为依据，拒绝阴谋论、伪科学、都市传说类题材。

## 快速下载

内容完整，仅在线预览受限。**推荐直接用 Gitee 整包下载——整个仓库不到 400 KB，几秒就下完，一次拿到全部历史。**

- **① 整包下载（推荐，含全部内容，< 400 KB）**
  - Gitee：https://gitee.com/vickrs/history-daily/repository/archive/main.zip
  - GitHub：https://github.com/VIckrs325/history-daily/archive/refs/heads/main.zip
- **② 一键获取最新一期（在线看/另存，无需改日期）**
  - https://github.com/VIckrs325/history-daily/raw/main/latest.md
- **③ 单篇（历史某天，把 `YYYY-MM-DD` 换成日期）**
  - https://github.com/VIckrs325/history-daily/raw/main/历史上的今天-YYYY-MM-DD.md
- **git 克隆**

```bash
git clone https://github.com/VIckrs325/history-daily.git
```

> 说明：Gitee 网页端个别文件可能无法在线预览（平台展示限制），单篇请用上方 GitHub 直链；整包 ZIP 与 `git clone` 不受影响。

## 目录结构

```
历史上的今天-YYYY-MM-DD.md   每日正文
_ops/                        每日同步脚本与配置
```

## 关于历史版本

本仓库保留**完整提交历史**，不使用 force push，也没有大文件——每日正文约 3 KB，十年累计不足 30 MB。因此不需要额外的压缩包归档层，git 本身就是最可靠的归档。

调取任意一天的历史版本：

```bash
# 列出某天的所有修订
git log --oneline -- 历史上的今天-2026-08-06.md

# 直接查看某个提交里的内容
git show <commit>:历史上的今天-2026-08-06.md

# 把某天的版本检出到当前目录
git checkout <commit> -- 历史上的今天-2026-08-06.md
```

## 更新方式

由本机每日定时任务在正文生成后自动提交推送，详见 [`_ops/README.md`](_ops/README.md)。

## 镜像

同一份内容同时托管在两处，任意一处可独立访问：

- Gitee：https://gitee.com/vickrs/history-daily
- GitHub：https://github.com/VIckrs325/history-daily

## 授权

[MIT](LICENSE) © 2026 Vickrs

正文中引用的史实、日期与结论均来自公开史料（人民网党史频道、中央党史和文献研究院、NASA 等），页面末尾逐条标注来源；事实本身不受著作权保护，此处授权仅针对文字组织与整理工作。
