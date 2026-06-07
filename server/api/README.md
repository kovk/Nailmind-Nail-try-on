# Nail Mind Python Backend

这个目录现在承载两条链路：

- 面向 App 的 `FastAPI` 主服务
- 对齐 `nail-vista` 的 AI 试戴实现
  - 一级：百炼 `qwen-image-2.0-pro` 多图编辑
  - 结果缓存：`/app/data/results/hand_xx+style_xx+length+shape.png`

## 目录

```text
server/api/
├── app/                      FastAPI 主服务
├── worker/                   旧异步 worker（兼容保留）
├── deploy/                   Docker Compose 远程部署目录
├── Dockerfile                API 镜像
├── docker-compose.yml        API + worker 本地编排
├── import_data.py            Excel 导入脚本
├── batch_generate.py         批量预生成 325 组试戴结果
├── requirements.txt          API 依赖
├── .env.example              基础运行配置模板
└── .env.ai.example           AI / API Key 配置模板
```

## 快速开始

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp .env.ai.example .env.ai
python main.py
```

## 配置文件

现在拆成两个文件：

- [server/api/.env.example](/Users/kongzhitong/Documents/美甲/server/api/.env.example)
  - 只放基础运行配置
- [server/api/.env.ai.example](/Users/kongzhitong/Documents/美甲/server/api/.env.ai.example)
  - 只放 AI、模型和第三方 API key

推荐初始化方式：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
cp .env.example .env
cp .env.ai.example .env.ai
cat .env.ai >> .env
```

## 基础运行配置

至少确认这些变量：

```text
APP_NAME
ADDR
PORT
DATABASE_URL
DATA_DIR
PUBLIC_BASE_URL
ALLOWED_ORIGINS
DEMO_EMAIL
DEMO_PASSWORD
JWT_SECRET
WORKER_TOKEN
```

## AI / API Key 配置

单独放在 [server/api/.env.ai.example](/Users/kongzhitong/Documents/美甲/server/api/.env.ai.example)：

```text
DASHSCOPE_API_KEY
```

关键说明：

- `DASHSCOPE_API_KEY`
  - 用于百炼 `qwen-image-2.0-pro`，是 AI 试戴唯一必填的模型配置。

## Excel 导入

默认数据文件：

- [命题三美甲评测数据（对外版）.xlsx](/Users/kongzhitong/Documents/美甲/命题三美甲评测数据（对外版）.xlsx)

导入脚本会：

1. 读取 `款式图` sheet
2. 读取 `手图` sheet
3. 去重手图 URL
4. 下载或同步增强款式图到 `data/static/styles/`
5. 下载或同步手图到 `data/static/hands/`
6. 建立 `nail_style_assets` 和 `hand_images`

运行方式：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
python import_data.py
```

## AI 试戴接口

当前推荐 App 使用同步试戴接口：

```text
GET    /api/tryon/hand-images
POST   /api/tryon/upload-hand
POST   /api/tryon/try-on
GET    /api/tryon/history
```

请求认证：

```text
Authorization: Bearer <token>
```

### `POST /api/tryon/try-on`

请求体：

```json
{
  "handId": "hand_01",
  "styleId": 1,
  "selectedLength": "natural_short",
  "selectedShape": "squoval"
}
```

返回体：

```json
{
  "result_url": "http://localhost:8080/files/results/hand_01+style_01+natural_short+squoval.png",
  "duration_ms": 842,
  "style_name": "法式简约",
  "source": "bailian-live"
}
```

`source` 只会是：

- `bailian-cached`
- `bailian-live`

## 批量预生成

用于预热 Demo 和做 325 组缓存：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
python batch_generate.py --check
python batch_generate.py --sample 10
python batch_generate.py
```

常用参数：

- `--check`
- `--sample <n>`
- `--hands hand_01,hand_02`
- `--styles 1,2,3`

## 兼容接口

旧版异步 job 接口仍然保留：

```text
POST   /api/try-on/uploads
GET    /api/try-on/jobs
POST   /api/try-on/jobs
GET    /api/try-on/jobs/{jobId}
GET    /api/try-on/jobs/{jobId}/result
GET    /api/try-on/jobs/{jobId}/result-image
POST   /api/try-on/jobs/{jobId}/rerender
```

但新的 Android 客户端已经切到同步试戴接口，不再依赖旧轮询主链路。

## Docker Compose

本地：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
cp .env.example .env
cat .env.ai.example >> .env
mkdir -p deploy/data deploy/models
docker compose up --build -d
```

远程模板：

- [docker-compose.remote.yml](/Users/kongzhitong/Documents/美甲/server/api/deploy/docker-compose.remote.yml)

## 日志

后端会在 `DATA_DIR/logs/` 下生成：

- `api.log`

日志覆盖：

- 请求路径、状态码、耗时
- AI 试戴成功与失败
- 趋势刷新任务结果

## OpenClaw / MiMo v2.5

OpenClaw 仅用于趋势分析模块，不参与试戴出图。

## 小红书趋势采集

现在运营端支持一条真实趋势链路：

1. 通过 `XhsSkills` 的 `xhs-apis` skill 搜索小红书关键词样本并读取笔记详情
2. 写入 `trend_topics` 和 `trend_posts`
3. 交给 OpenClaw + `mimo-v2.5-pro` 生成 `trend_recommendations`
4. 在运营端显示建议款式名称、主图和通过验证的来源帖子

### 依赖

安装 API 依赖：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
source .venv/bin/activate
pip install -r requirements.txt
```

### XhsSkills

比赛演示环境默认使用 [cv-cat/XhsSkills](https://github.com/cv-cat/XhsSkills) 里的 `xhs-apis` skill 作为小红书结构化采集器。它内部封装了 `Spider_XHS` 的 PC API，但以 skill CLI 方式运行，更适合交给 OpenClaw/运营链路复用。

将项目放在服务器挂载目录，例如：

```bash
cd /opt/nailmind/data
git clone https://github.com/cv-cat/XhsSkills.git XhsSkills
cd XhsSkills/skills/xhs-apis/scripts
pip install -r requirements.txt
npm install
```

然后在 API 环境变量里配置：

```text
XHS_COLLECTOR_BACKEND=xhs_skill
XHS_SKILL_PATH=/app/data/XhsSkills
XHS_COOKIES=登录后的小红书 Cookie
XHS_STORAGE_STATE_PATH=/app/data/xhs-storage-state.json
```

`XHS_COOKIES` 的获取方式：浏览器登录小红书后，打开开发者工具，在任意 Fetch/XHR 请求里复制请求头中的 `cookie` 字段。也可以放 `xhs-storage-state.json` 到 `XHS_STORAGE_STATE_PATH`，后端会自动转换成 Cookie 字符串。

如果要临时回退到旧的浏览器方式，可设置：

```text
XHS_COLLECTOR_BACKEND=playwright
XHS_STORAGE_STATE_PATH=/app/data/xhs-storage-state.json
```

如果要临时回退到直接 import `Spider_XHS` 的旧实现，可设置：

```text
XHS_COLLECTOR_BACKEND=spider_xhs
SPIDER_XHS_PATH=/app/data/Spider_XHS
```

但正式趋势分析只应使用通过详情验证的真实帖子。验证不通过时，系统不会把样本交给 OpenClaw。

### 运营端接口

```text
POST /admin/trends/collect
GET  /admin/trends/recommendations
```

`POST /admin/trends/collect` 请求体示例：

```json
{
  "keywords": ["法式美甲", "猫眼美甲", "新中式美甲"],
  "maxPostsPerKeyword": 6,
  "headless": true
}
```

说明：

- `keywords`：小红书搜索关键词
- `maxPostsPerKeyword`：每个关键词采样帖子数
- `headless`：仅在 `XHS_COLLECTOR_BACKEND=playwright` 时生效

返回后会立即刷新 recommendation 数据；运营端会展示：

- 建议名称
- 建议主图
- 触发原因
- 置信度
- 已验证来源帖子标题和代表图

注意：

- 该接口只能由运营端账号调用。
- 默认运营账号是 `operator@nailmind.app / 123456`。

模板放在：

- [server/trend_agent/.env.openclaw.example](/Users/kongzhitong/Documents/美甲/server/trend_agent/.env.openclaw.example)
- [server/trend_agent/docker-compose.openclaw.yml](/Users/kongzhitong/Documents/美甲/server/trend_agent/docker-compose.openclaw.yml)

如果服务器已经安装并配置好 `openclaw` CLI，使用方式：

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
```

启动：

```bash
cd /Users/kongzhitong/Documents/美甲/server/trend_agent
docker compose -f docker-compose.openclaw.yml up -d
```

## 默认初始化账号

```text
luna@nailmind.app / 123456
operator@nailmind.app / 123456
merchant@nailmind.app / 123456
```

角色约定：

- `luna@nailmind.app`：普通用户 App 联调
- `operator@nailmind.app`：运营后台 / 趋势采集
- `merchant@nailmind.app`：商家后台

这些账号仅用于初始环境联调，正式上线前应替换。

## 设计文档

- AI 试戴服务设计：[docs/ai-tryon-service-design.md](/Users/kongzhitong/Documents/美甲/server/api/docs/ai-tryon-service-design.md)
