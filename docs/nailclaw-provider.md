# NailClaw Trend Provider

NailClaw 的趋势采集层已经从运营后台和分析逻辑中解耦。业务代码只调用统一入口：

- `collect_nailclaw_trends(keywords, max_posts_per_keyword)`
- `check_nailclaw_status()`

实际数据来源由 `NAILCLAW_SOURCE` 决定。

## 当前 Provider

### `redbook`

默认数据源，使用 `@lucasygu/redbook` CLI 读取小红书搜索结果。后端不会直接嵌入爬虫逻辑，只负责调用 CLI、归一化结果，再交给 NailClaw 分析。

- `REDBOOK_CLI_PATH`: redbook 可执行文件路径，默认可指向 `/app/tools/redbook/node_modules/.bin/redbook`。
- `REDBOOK_COOKIE_SOURCE`: 从浏览器读取登录态，默认 `chrome`。
- `REDBOOK_CHROME_PROFILE`: 可选 Chrome profile 名称。
- `REDBOOK_COOKIE_STRING`: 可选手动 cookie，格式至少包含 `a1` 和 `web_session`。
- `REDBOOK_SORT`: 搜索排序，默认 `popular`。

### `dianping`

备用数据源，支持两种输入：

- `DIANPING_DATA_URL`: 内部 JSON API，返回大众点评门店、套餐、评价样本。
- `DIANPING_DATA_PATH`: 本地 JSON 文件，适合导出数据、mock 数据或离线比赛演示。

字段会被归一化为统一样本：

- `postId`
- `url`
- `title`
- `author`
- `imageUrl`
- `tags`
- `likeCount`
- `collectCount`
- `commentCount`
- `rating`
- `shopName`
- `dealName`
- `reviewText`

## 新增 Provider

在 `server/api/app/services/nailclaw.py` 中新增一个实现 `TrendProvider` 协议的类：

```python
class MyTrendProvider:
    provider_key = "my-source"
    provider_label = "自定义数据源"

    def status(self) -> dict[str, Any]:
        return {"provider": self.provider_key, "configured": True}

    def collect(self, keywords: list[str], max_posts_per_keyword: int) -> list[dict[str, Any]]:
        return [
            {
                "keyword": "美甲",
                "topicTitle": "数据源标题",
                "clusterLabel": "风格聚类",
                "summary": "趋势摘要",
                "communityHeatScore": 1000,
                "posts": [],
            }
        ]
```

然后注册：

```python
PROVIDER_REGISTRY["my-source"] = MyTrendProvider
```

最后配置：

```env
NAILCLAW_SOURCE=my-source
```

## 约束

- Provider 只负责拿数据和归一化，不负责写数据库。
- NailClaw Agent 只负责分析 provider 返回的结构化样本。
- 运营端只读取后端 dashboard，不直接依赖任何爬虫、CLI 或第三方 SDK。
- 如果后续切换大众点评、抖音或其他来源，只需要新增 provider 或切换 `NAILCLAW_SOURCE`。
