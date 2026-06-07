# Nail Mind Trend Agent

这个目录用于承接 OpenClaw / MiMo v2.5 Pro 的趋势分析链路。

当前实现：

- 复用 `server/api` 的数据库
- 可向数据库写入 `TrendTopic`、`TrendPost` 和 `TrendRecommendation`
- `main.py` 会直接调用服务器上的 `openclaw` CLI
- 结果与运行日志会落到 `DATA_DIR/logs/trend-agent.log`
- recommendation 会附带候选款式图、名称和来源帖子样本，供运营端直接审核

## 本地运行

```bash
cd /Users/kongzhitong/Documents/美甲/server/trend_agent
python main.py
```

## OpenClaw / MiMo v2.5 Pro 配置

模板文件：

- [.env.openclaw.example](/Users/kongzhitong/Documents/美甲/server/trend_agent/.env.openclaw.example)
- [docker-compose.openclaw.yml](/Users/kongzhitong/Documents/美甲/server/trend_agent/docker-compose.openclaw.yml)

先复制：

```bash
cd /Users/kongzhitong/Documents/美甲/server/trend_agent
cp .env.openclaw.example .env.openclaw
```

然后填写：

```text
OPENCLAW_CLI=/usr/bin/openclaw
OPENCLAW_MODEL=mimo-v2.5-pro
OPENCLAW_USE_GATEWAY=false
OPENCLAW_TIMEOUT_SECONDS=180
OPENCLAW_EXTRA_ARGS=
TREND_AGENT_IMPORT_DEMO=false
TREND_AGENT_ALLOW_RULE_FALLBACK=false
XHS_STORAGE_STATE_PATH=/opt/nailmind/xhs-storage-state.json
```

前提：

- 服务器已经安装 `openclaw`
- `openclaw` 本地配置里已经接入 MiMo 账号
- 当前环境能执行 `openclaw infer model run --model mimo-v2.5-pro ...`

启动：

```bash
cd /Users/kongzhitong/Documents/美甲/server/trend_agent
docker compose -f docker-compose.openclaw.yml up -d
```

## 环境变量

- `OPENCLAW_CLI`
- `OPENCLAW_MODEL`
- `OPENCLAW_USE_GATEWAY`
- `OPENCLAW_TIMEOUT_SECONDS`
- `OPENCLAW_EXTRA_ARGS`
- `DATABASE_URL`
- `DATA_DIR`
- `TREND_AGENT_IMPORT_DEMO`
- `TREND_AGENT_ALLOW_RULE_FALLBACK`
- `XHS_STORAGE_STATE_PATH`
