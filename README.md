# Nail Mind

项目已经按客户端和服务端拆开，根目录只保留总览。

## 目录结构

```text
/Users/kongzhitong/Documents/美甲
├── client/
│   └── android/    Android Jetpack Compose 客户端原型
└── server/
    └── api/        Python/FastAPI 后端服务
```

## 入口

- Android 客户端说明：`/Users/kongzhitong/Documents/美甲/client/android/README.md`
- Python 后端说明：`/Users/kongzhitong/Documents/美甲/server/api/README.md`
- AI 试戴服务设计：`/Users/kongzhitong/Documents/美甲/server/api/docs/ai-tryon-service-design.md`

## 当前状态

- `client/android` 已预留真实环境配置，并补齐了完整 API 契约层。
- `server/api` 已重构为 Python/FastAPI 后端，并带独立试戴 worker 与 `docker-compose` 部署。

## 配置文件

- Android 客户端模板：`/Users/kongzhitong/Documents/美甲/client/android/local.properties.example`
- 后端服务模板：`/Users/kongzhitong/Documents/美甲/server/api/.env.example`
