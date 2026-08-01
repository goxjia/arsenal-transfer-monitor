# Arsenal 转会新闻监控

自动抓取 **Fabrizio Romano** 与 **David Ornstein** 的阿森纳转会消息，过滤后通过 **Bark** 推送到你的 iPhone。
部署在 **GitHub Actions**（美国节点，直连 Telegram API 与 Bark 服务器，**全程免代理**）。

## 数据流

```
Romano   → Telegram 官方频道 @FabrizioRomano   ┐
Ornstein → The Athletic 作者页 (文章流)          ├─→ 关键词过滤(Arsenal) ─→ 去重 ─→ Bark ─→ iPhone
Ornstein → Arsenal 聚合 TG 频道 @arsenalbreaking ┘   (双源冗余，更稳)
```

- Romano：官方公开频道，最一手。
- Ornstein：没有官方 TG 频道，所以用 **The Athletic 文章流 + 聚合频道** 双源覆盖，任一失效仍有另一路。

## 一键部署步骤

### 1. 准备 Bark（iPhone 推送）
1. App Store 搜索 **Bark** 安装并打开。
2. App 主页会显示你的推送地址，形如 `https://api.day.app/XXXXXXXXX`。
3. 复制末尾那段 key（`XXXXXXXXXX`），后面用得到。

### 2. 创建 Telegram Bot
1. 在 Telegram 搜索 **@BotFather**，发 `/newbot`，按提示起名，得到 **Bot Token**（形如 `123456789:AAE...`）。
2. **把 bot 加入要监控的频道**：打开 `@FabrizioRomano` 和 `@arsenalbreaking`，点频道名 → Add to Channel / 添加成员，把你的 bot 加进去（脚本也会自动 `joinChat` 尝试，但大频道可能只允许手动添加）。
   - 注意：若 bot 无法加入 Romano 官方频道，不用担心——`@arsenalbreaking` 聚合频道也会转发 Romano 的独家，且 Ornstein 由 The Athletic 覆盖，系统仍完整。

### 3. 推到 GitHub 并配置 Secrets
1. 把本目录推到一个 GitHub 仓库（公开仓库定时任务无限时长，推荐；私有仓库请把 `monitor.yml` 里的 cron 改成 `*/30 * * * *`）。
2. 仓库 → **Settings → Secrets and variables → Actions → New repository secret**，添加：
   - `TG_BOT_TOKEN` = 第 2 步的 Bot Token
   - `BARK_KEY` = 第 1 步的 Bark key
   - （可选）`BARK_SERVER` = 自建 Bark 服务器地址，留空则用官方 `https://api.day.app`

### 4. 启动
- 仓库 → **Actions** → 左侧 `Arsenal Transfer Monitor` → **Run workflow**（手动跑一次测试）。
- 之后每 15 分钟自动运行。去 iPhone 上看 Bark 是否收到测试期间的 Arsenal 消息。

## 静默时段（免打扰）

默认 **北京时间 23:30 - 次日 08:00** 不推送任何消息。该时段内匹配到的内容会进入「待推送队列」，等 08:00 后下一次运行时统一补推，不会丢失、也不会在深夜打扰你。

- 调整时段：在 Secrets 里加 `QUIET_START` / `QUIET_END`（格式 `HH:MM`，如 `22:00` / `07:30`），不设置则使用默认 23:30 / 08:00。
- 队列上限 `PENDING_CAP`（默认 80 条），超出只保留最近。

## 测试模式（验证管道）

想验证整条管道是否打通、或补推历史消息时，可在 Actions 页面手动触发并勾选：

- **test_mode（测试模式）**：绕过静默时段、忽略去重池，推送近 N 天匹配到的内容（即便现在是深夜也会推，方便确认链路）。
- **backfill_days（回溯天数）**：测试模式回溯天数，默认 7。

触发方式二选一：
1. **Actions 页面**：`Run workflow` → 勾选 test_mode、填 backfill_days → Run。
2. **API**：`POST /repos/<you>/arsenal-transfer-monitor/actions/workflows/monitor.yml/dispatches`，body `{"ref":"main","inputs":{"test_mode":true,"backfill_days":7}}`。

> 说明：Telegram 历史消息依赖 bot 是否在频道内（bot 加入后才有 `channel_post` 更新），若 bot 未加频道，测试模式下 TG 部分可能为空；The Athletic 文章流不受此限制，是测试的主要可信来源。若近 N 天无匹配内容，会推送一条「测试运行成功」回执，确认 iPhone 能收到。

## 调参（直接改 `monitor.py` 顶部）
- `TG_CHANNELS`：监控的 TG 频道列表。
- `ARSENAL_KEYWORDS`：过滤关键词，含任一才推送（默认 arsenal / #afc / gunners）。
- `ATHLETIC_AUTHOR_URL` / `ATHLETIC_FEED_URL`：Ornstein 文章源。

## 说明 / 坑点
- **去重状态**存于 GitHub Artifact（`monitor-state`，保留 30 天），跨运行保留，避免重复推送。若 Artifact 过期，最多重复一次，不影响使用。
- **GitHub Actions 定时精度**：免费定时任务可能延迟几分钟，高峰期偶有遗漏，属正常。
- **Telegram 更新保留**：bot 服务端约保留 24 小时 / 100 条更新，15 分钟频率远低于上限，安全。
- 全程**不需要你的代理订阅**：GitHub Actions 美国 IP 直连 TG API 与 Bark 官方服务器。
