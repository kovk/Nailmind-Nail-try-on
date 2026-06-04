# Nail Mind Trend Agent

独立趋势分析服务一期以“小红书趋势输入 -> 建议生成”为目标。

当前实现：

- 直接复用 `server/api` 的数据库
- 可向数据库写入 `TrendTopic` 和 `TrendRecommendation`
- 不直接修改商品状态，仍需运营在 `/admin/trends/recommendations` 审核

运行：

```bash
cd /Users/kongzhitong/Documents/美甲/server/trend_agent
python main.py
```

可通过环境变量覆盖：

- `DATABASE_URL`
- `TREND_AGENT_IMPORT_DEMO`，默认 `true`
