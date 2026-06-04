# Nail Mind Python Backend

这个目录现在是完整的 Python 后端服务，结构为：

- `FastAPI` API 服务
- 独立 `tryon-worker`
- SQLite 持久化
- 本地文件存储
- `docker-compose` 部署

## 目录

```text
server/api/
├── app/                 FastAPI 主服务
├── worker/              AI 试戴 worker
├── Dockerfile           API 镜像
├── docker-compose.yml   API + worker 编排
├── requirements.txt     API 依赖
└── .env.example         运行配置模板
```

## 运行方式

本地直接运行 API：

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 配置

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
cp .env.example .env
```

主要配置项：

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
JWT_ALGORITHM
JWT_EXPIRE_MINUTES
WORKER_TOKEN
API_BASE_URL
POLL_INTERVAL_SECONDS
MODEL_DIR
YOLO_MODEL_PATH
ENABLE_FALLBACK_RENDERER
```

## 主要接口

```text
GET    /health
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me
POST   /api/auth/logout
GET    /api/home
GET    /api/styles
GET    /api/styles/search?q=法式
GET    /api/styles/{styleId}
GET    /api/favorites
POST   /api/favorites/{styleId}
DELETE /api/favorites/{styleId}
POST   /api/events
POST   /api/try-on/uploads
GET    /api/try-on/jobs
POST   /api/try-on/jobs
GET    /api/try-on/jobs/{jobId}
GET    /api/try-on/jobs/{jobId}/result
GET    /api/try-on/jobs/{jobId}/result-image
POST   /api/try-on/jobs/{jobId}/rerender
GET    /api/stores
GET    /api/stores/{storeId}
GET    /api/stores/{storeId}/slots
GET    /api/bookings
POST   /api/bookings
GET    /api/bookings/{bookingId}
POST   /api/bookings/{bookingId}/confirm
GET    /api/profile
GET    /api/settings
```

除 `POST /api/auth/register`、`POST /api/auth/login` 和 `GET /health` 外，其余接口都需要：

```text
Authorization: Bearer <token>
```

## Docker Compose

```bash
cd /Users/kongzhitong/Documents/美甲/server/api
cp .env.example .env
mkdir -p deploy/data deploy/models
docker compose up --build -d
```

Compose 会启动：

- `nailmind-api`
- `nailmind-tryon-worker`

如果你已经有 YOLO 指甲分割模型，把权重放到：

```text
server/api/deploy/models/nail-seg.pt
```

如果你直接使用 `JineshRathod/AI-Virtual-Nail-Try-On` 仓库里的原始权重文件名，也可以直接放：

```text
server/api/deploy/models/best.pt
```

worker 会优先读取 `YOLO_MODEL_PATH`，如果该路径不存在，会自动回退尝试 `/models/best.pt`。

worker 会优先走：

- `MediaPipe Hands`
- `YOLOv8-seg`
- 渲染管线

如果没有模型权重，会按 `ENABLE_FALLBACK_RENDERER=true` 回退到规则渲染模式。

## 当前实现状态

- 用户、会话、收藏、预约、试戴任务已接入数据库
- 上传图和结果图走文件存储
- worker 已实现任务领取、进度回写、完成回写、失败回写
- 视觉管线已接 `MediaPipe` 和 `YOLO` 的模型入口
- 没有权重文件时仍可完整跑通上传到结果回传链路

## 演示账号

```text
luna@nailmind.app / 123456
```

## 后台入口

- 后台 Web：`http://121.40.171.199:8080/admin`
- 运营账号：`operator@nailmind.app / 123456`
- 商家账号：`merchant@nailmind.app / 123456`
- 原始埋点事件：`GET /admin/analytics/events`

## 设计文档

- AI 试戴服务设计：[docs/ai-tryon-service-design.md](/Users/kongzhitong/Documents/美甲/server/api/docs/ai-tryon-service-design.md)
