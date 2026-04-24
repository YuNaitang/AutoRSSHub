# RSS 阅读器 - 云端自动化

基于 GitHub Actions 的 RSS 自动抓取、去重、全文整理与静态页面发布系统。
每小时自动抓取一次，输出可读网页 + AI 助理专用 JSON 端点。

## 快速开始

### 1. 使用此模板创建仓库

- 将此仓库文件复制到你的新仓库
- 或将 `.github/workflows/`、`scripts/`、`templates/`、`sources.txt` 拉入已有仓库

### 2. 配置 RSS 源

编辑 `sources.txt`，每行一个 RSS/Atom 源 URL：

```text
https://example.com/feed.xml
https://another.blog/rss