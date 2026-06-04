# Nail Mind Android Client

Jetpack Compose 客户端，当前包含：

- 底部五个主入口：首页、款式、AI试戴、预约、我的
- 关键二级流程：搜索、款式详情、上传手部照片、识别中、试戴结果、收藏、门店详情、预约填写、确认、成功、预约记录、设置
- 品牌化 Material 3 主题：冷调中性色 + 深玫瑰主色，统一圆角和卡片系统
- 真实 API 契约层：认证、首页、款式、收藏、试戴、门店、预约、个人中心、设置

## 打开方式

1. 用 Android Studio 打开目录：`/Users/kongzhitong/Documents/美甲/client/android`
2. 等待 Gradle Sync 完成
3. 运行 `app` 模块到模拟器或真机

## 配置

复制一份本地配置模板：

```bash
cd /Users/kongzhitong/Documents/美甲/client/android
cp local.properties.example local.properties
```

除 `sdk.dir` 外，客户端额外支持这些配置：

```text
NAILMIND_API_BASE_URL=http://10.0.2.2:8080/
NAILMIND_API_MEDIA_BASE_URL=http://10.0.2.2:8080/
NAILMIND_API_TIMEOUT_SECONDS=20
```

说明：

- Android 模拟器访问本机后端时，应使用 `10.0.2.2`
- 真机调试时，把 `NAILMIND_API_BASE_URL` 改成你电脑或测试服务器的实际 IP
- 这些值会编译进 `BuildConfig`

## 结构说明

- `app/src/main/java/com/nailmind/app/MainActivity.kt`
  - 应用入口
- `app/src/main/java/com/nailmind/app/ui/NailMindApp.kt`
  - 全部原型页面、状态和导航
- `app/src/main/java/com/nailmind/app/data/api`
  - Retrofit API 接口、请求响应模型、仓储封装
- `app/src/main/java/com/nailmind/app/data/config/AppConfig.kt`
  - 客户端环境配置入口
- `app/src/main/java/com/nailmind/app/ui/theme`
  - 颜色与 Material 3 主题

## 说明

当前 UI 仍以原型状态管理为主，但客户端需要的后端 API 契约已经完整落在 `data/api`。下一步接 UI 时，应直接把页面中的本地 mock 状态迁移到这些仓储调用上。
