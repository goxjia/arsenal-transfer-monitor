# 部署清单（5 分钟 · 全免费 · 免代理）

> 结论先说：本项目**不需要翻墙代理、不需要花钱**。
> 代码、工作流、依赖、文档、单元测试都已完成。你只需亲手做下面 3 步（涉及你的手机 / Telegram 账号 / GitHub 账号，AI 无法代劳）。

---

## ✅ AI 已经替你做好的

- `monitor.py` — 主脚本（拉 TG 频道 + 抓 The Athletic + 过滤 Arsenal + 去重 + 推 Bark）
- `.github/workflows/monitor.yml` — GitHub Actions 每 15 分钟定时跑
- `requirements.txt` / `.gitignore` — 依赖与忽略项
- `README.md` — 完整说明
- 已通过语法检查 + 解析/过滤逻辑单测

---

## 📱 第 1 步：iPhone 装 Bark（约 1 分钟）

1. App Store 搜索 **Bark** 并安装（免费、无内购）。
2. 打开 App，首页会显示你的设备 Key，形如 `https://api.day.app/XXXXXXXX`。
3. 记下 `XXXXXXXX` 这一段（后面用）。公共服务器国内可直接访问，无需任何配置。

> 想更私密可后续自托管 Bark（Docker 一条命令），但公共服务器对当前需求已足够。

---

## 🤖 第 2 步：Telegram 建 Bot（约 2 分钟）

1. 在 Telegram 搜索 **@BotFather**，发 `/newbot`。
2. 按提示取一个名字和用户名（如 `ArsenalMonitorBot`），得到 **Bot Token**：`123456789:AAxxx...`。
3. 把 bot 加进频道：
   - 打开 `@FabrizioRomano` 频道 → 成员 → 添加管理员（或把 bot 拉进频道）。
   - 打开 `@arsenalbreaking` 频道 → 同样操作。
   - ⚠️ 大频道（如 Romano 官方）可能不允许随意加 bot——**加不进也没关系**：`@arsenalbreaking` 聚合频道会转发 Romano 独家，Ornstein 由 The Athletic 覆盖，三源冗余，系统仍然完整。
4. 记下 **Bot Token**（后面用）。

---

## 🐙 第 3 步：推到 GitHub + 配密钥（约 2 分钟）

1. 在 GitHub 新建一个**公开**仓库（公开仓库 Actions 定时无限时长；私有仓库也行，只是有每月额度）。
2. 把整个 `arsenal-transfer-monitor/` 目录 push 上去：
   ```bash
   cd arsenal-transfer-monitor
   git init
   git add .
   git commit -m "init arsenal transfer monitor"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```
3. 仓库页面 → **Settings → Secrets and variables → Actions → New repository secret**，添加两条：
   - `TG_BOT_TOKEN` = 第 2 步拿到的 Bot Token
   - `BARK_KEY` = 第 1 步拿到的 Bark Key
4. （可选）若改用自建 Bark 服务器，再加一条 `BARK_SERVER` = `https://你的地址`；不加则用公共服务器。

---

## 🚀 第 4 步：跑一次验证

1. 仓库 → **Actions** 标签页 → 找到 `Arsenal Transfer Monitor` → **Run workflow**。
2. 等 1–2 分钟，看日志：应出现「拉取频道 / 解析文章 / 命中 Arsenal / 推送 Bark」等行。
3. 拿起 iPhone，Bark 应弹出一条 Arsenal 相关通知。
4. 之后每 15 分钟自动跑，转会窗口消息实时推到手机。

---

## 🔧 常见坑

- **bot 加不进 Romano 官方频道**：忽略，依赖 `@arsenalbreaking` + The Athletic 即可。
- **GitHub Actions 最长 15 分钟跑一次**：转会高潮期可能有几分钟延迟，属正常。
- **The Athletic 偶尔改页面结构**：脚本已做 RSS 优先 + HTML 兜底，若失效再回来调解析器。
- **Bark 公共服务器限流**：个人使用量级完全够；若想更稳可自托管（加 `BARK_SERVER`）。
