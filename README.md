---
!!! 使用AI辅助生成，仅供参考。
---

# 📡 RSS 阅读器 — 基于 GitHub Actions 的云端自动聚合器

一个**零成本、全自动、可定制**的个人 RSS 阅读器。  
使用 GitHub Actions 定时抓取 RSS 源，支持全文提取、去重、OPML 配置，  
输出**美观的静态页面**和**供 AI 调用的 JSON 摘要端点**。

**立即体验**：设置后每小时自动更新，通过 GitHub Pages 访问你的专属阅读页。

---

## 🎯 核心功能

- **🕒 每小时自动更新** — 通过 GitHub Actions `schedule` 定时抓取
- **📋 OPML 配置** — 使用标准 OPML 文件管理订阅源（支持备注名称）
- **🧠 智能去重** — 以文章链接为键，永久避免重复展示
- **📖 全文提取** — 自动从 RSS 链接抓取正文（失败则降级用摘要）
- **🎨 Catppuccin 主题** — 暗色护眼、优雅的阅读界面
- **📱 响应式布局** — 桌面侧边栏 + 移动端自适应
- **🔍 源可见性切换** — 左侧菜单可一键勾选/隐藏特定源
- **🤖 AI 助理端点** — `/summary.json` 提供结构化数据，可直接喂给 AI 工具
- **📦 极简部署** — 仅需 Fork 仓库 + 配置 OPML + 启用 Pages

---

## 🚀 快速开始（从零到上线只需 5 分钟）

### 1. Fork 或创建仓库
点击本仓库右上角 **Use this template** → **Create a new repository**，  
或手动将所有文件添加到你的新仓库。

**必需文件**：
- `.github/workflows/rss.yml`
- `scripts/`（fetch_rss.py、generate_site.py、requirements.txt）
- `templates/index.html.j2`
- `sources.opml`

### 2. 编辑订阅源
打开 `sources.opml`，按以下格式填入你要订阅的 RSS 源：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>我的订阅</title>
  </head>
  <body>
    <outline title="阮一峰的网络日志" xmlUrl="https://feeds.feedburner.com/ruanyifeng" />
    <outline title="GitHub Blog" xmlUrl="https://github.blog/feed/" />
    <outline title="我的其他博客" xmlUrl="https://example.com/feed" />
  </body>
</opml>
```

- `title`：显示在侧边栏的名称
- `xmlUrl`：RSS/Atom 地址
- 支持常规 OPML 2.0 导出文件（可从 Inoreader/Feedly 等导入）

### 3. 启用 GitHub Pages
进入仓库 **Settings → Pages**：  
- **Source**：选择 `Deploy from a branch`  
- **Branch**：选择 `gh-pages`，目录 `/ (root)`  
- 点击 **Save**

### 4. 首次运行工作流
- 进入仓库的 **Actions** 标签页
- 选择左侧的 **“RSS 抓取与发布”**
- 点击 **Run workflow** → **Run workflow**（手动触发）

等待约 1-2 分钟，运行成功后访问：
```
https://<你的用户名>.github.io/<仓库名>/
```
即可看到你的 RSS 阅读器。

> 之后 GitHub 会**每小时自动抓取**，无需任何操作。

---

## 📂 项目结构

```
rss-reader/
├── .github/workflows/rss.yml      # GitHub Actions 工作流（定时抓取+部署）
├── scripts/
│   ├── fetch_rss.py               # RSS 抓取、去重、全文、写入 articles.json
│   ├── generate_site.py           # 生成 index.html、summary.json、sources.json
│   └── requirements.txt           # Python 依赖
├── templates/
│   └── index.html.j2              # Jinja2 页面模板（Catppuccin 主题）
├── sources.opml                   # 用户编辑的订阅源列表
├── data/
│   └── articles.json              # 去重数据库（自动生成，无需修改）
├── public/                        # 静态输出（部署到 gh-pages 分支）
│   ├── index.html
│   ├── summary.json
│   ├── sources.json
│   └── feed/                      # 每日归档（如 2026-04-24.json）
└── README.md
```

---

## 🎨 自定义

### 修改主题颜色
编辑 `templates/index.html.j2` 的 `<style>` 区域，CSS 变量基于 [Catppuccin](https://github.com/catppuccin/catppuccin) 调色板。  
可选主题：替换 `--ctp-*` 变量为 Mocha/Macchiato/Frappé/Latte 对应值。

### 调整抓取频率
修改 `.github/workflows/rss.yml` 中的 `cron`：
```yaml
schedule:
  - cron: '0 * * * *'   # 每小时
```
参考 [crontab guru](https://crontab.guru/) 生成表达式。

### 改变回顾窗口
`scripts/fetch_rss.py` 和 `generate_site.py` 中的 `LOOKBACK_HOURS = 24` 改为你希望的小时数。

### 禁用全文抓取
如果不需要全文，在 `fetch_rss.py` 中注释掉 `full_text = fetch_full_text(link)` 相关行即可。

### 使用外部 RSS 阅读器导入
项目生成的 `sources.opml` 也可作为备份，随时导入其他阅读器。

---

## 🤖 给 AI 助理配置

AI 助理可直接读取 `https://<你的域名>/summary.json`，格式如下：

```json
{
  "generated_at": "2026-04-24T10:00:00+00:00",
  "period_hours": 24,
  "total_articles": 15,
  "articles": [
    {
      "title": "文章标题",
      "link": "https://原文链接",
      "source": "来源名称",
      "published": "2026-04-24T09:30:00+00:00",
      "summary": "摘要内容",
      "content_preview": "正文前500字"
    }
  ]
}
```

在 AI 工具中简单调用该 URL 即可获得最新文章列表。

---

## 🛠 技术栈

- **GitHub Actions** — 定时任务 & CI/CD
- **Python** — feedparser + trafilatura + Jinja2
- **OPML** — 源配置标准格式
- **GitHub Pages** — 静态站点托管
- **Catppuccin** — 现代配色方案

---

## ❓ 常见问题

**Q：为什么第一次运行后页面是空的？**  
A：检查你的 `sources.opml` 是否包含有效的 RSS 源，并观察 Actions 日志是否有报错。部分源可能需要网络可达性。

**Q：能否添加更多源？**  
A：可以，只需在 `sources.opml` 添加新的 `<outline>` 行，工作流下次运行会自动抓取。

**Q：文章数量超过 5 万怎么办？**  
A：脚本会自动清理 30 天前的旧条目，保留最近 5 万条。

**Q：可以托管在私有仓库吗？**  
A：可以，但 GitHub Pages 需要公开仓库或升级到 Pro 版本。你可以将静态页面部署到其他平台（如 Netlify），修改 `rss.yml` 即可。

---

## 📄 许可

MIT License — 随意 Fork、修改、商用。

---

## 🌟 致谢

- [feedparser](https://github.com/kurtmckee/feedparser)
- [trafilatura](https://github.com/adbar/trafilatura)
- [Jinja2](https://github.com/pallets/jinja)
- [Catppuccin](https://github.com/catppuccin)

---

> 让你的信息流永不掉线，构建你自己的智能阅读中枢！
