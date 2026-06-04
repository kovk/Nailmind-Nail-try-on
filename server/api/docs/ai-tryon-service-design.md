# AI 试戴服务设计

本设计以 [JineshRathod/AI-Virtual-Nail-Try-On](https://github.com/JineshRathod/AI-Virtual-Nail-Try-On) 的实现思路为主要参考，但会按 Nail Mind 当前的客户端和 Python 服务结构重组为可上线的服务方案。

## 目标

- 用户上传手部照片后，返回与真实手型、角度、甲床贴合的试戴结果图
- 支持不同款式、甲长、甲型、延长甲片
- 结果可用于收藏、再次试戴、预约同款、保存图片
- 所有任务和结果都与登录用户绑定

## 总体架构

```text
Android Client
    |
    v
Python API Server
    |
    +--> Object Storage
    |
    +--> Job Queue
            |
            v
        AI Worker (Python)
            |
            +--> Hand Landmark Model
            +--> Nail Segmentation Model
            +--> OpenCV Render Pipeline
```

## 服务拆分

### 1. `api-server`（Python）

职责：

- 用户鉴权
- 上传签名、任务创建、任务查询
- 款式素材元数据管理
- 试戴会话持久化
- 将任务投递到队列

建议保留在当前 `server/api` 中。

### 2. `tryon-worker`（Python）

职责：

- 拉取试戴任务
- 下载原图和款式素材
- 执行手部检测、指甲分割、透视贴图、边缘融合
- 产出结果图、mask、调试图
- 回写任务状态和结果

这个部分不要用 Go 直接做。模型推理和 OpenCV 渲染链路更适合 Python。

### 3. `object-storage`

职责：

- 存原始上传图
- 存中间产物：标准化图、mask、关键点 JSON、调试图
- 存最终结果图

本地开发可先用磁盘目录，线上再切 S3/OSS/MinIO。

### 4. `job-queue`

职责：

- 异步执行试戴任务
- 支持重试、失败状态、超时控制

原型期可以先用数据库轮询或内存队列。
正式建议：Redis + Asynq / RabbitMQ / NATS 任选一种。

## 数据模型

### `try_on_jobs`

```text
id
user_id
style_id
source_image_key
status               created | queued | preprocessing | segmenting | rendering | completed | failed
selected_length      natural_short | medium_short | long
selected_shape       squoval | oval | almond
result_image_key
result_preview_key
mask_bundle_key
landmarks_key
debug_bundle_key
error_code
error_message
model_version
renderer_version
created_at
updated_at
completed_at
```

### `try_on_job_events`

用于追踪每一步耗时和失败点：

```text
id
job_id
stage
message
payload_json
created_at
```

### `style_assets`

不要只保存一个 style 名称。试戴能力的上限取决于素材结构。

```text
style_id
base_color
finish_type          solid | french | cat_eye | glitter | ombre | crystal
texture_png_key
alpha_mask_key
specular_map_key
tip_overlay_key
decal_bundle_key
default_shape
default_length
render_params_json
```

## 核心接口

### 1. 创建上传会话

`POST /api/try-on/uploads`

请求：

```json
{
  "contentType": "image/jpeg"
}
```

响应：

```json
{
  "uploadUrl": "https://storage.example.com/...",
  "objectKey": "tryon/source/user-001/2026/06/01/abc.jpg"
}
```

### 2. 创建试戴任务

`POST /api/try-on/jobs`

请求：

```json
{
  "styleId": "rose-mist",
  "sourceImageKey": "tryon/source/user-001/2026/06/01/abc.jpg",
  "selectedLength": "natural_short",
  "selectedShape": "squoval"
}
```

响应：

```json
{
  "id": "tryon-0001",
  "status": "queued"
}
```

### 3. 查询任务状态

`GET /api/try-on/jobs/{jobId}`

响应：

```json
{
  "id": "tryon-0001",
  "status": "rendering",
  "progress": 72,
  "stage": "applying_design",
  "resultImageUrl": null,
  "debug": null
}
```

### 4. 获取已完成结果

`GET /api/try-on/jobs/{jobId}/result`

响应：

```json
{
  "id": "tryon-0001",
  "status": "completed",
  "resultImageUrl": "https://cdn.example.com/tryon/results/...",
  "previewUrl": "https://cdn.example.com/tryon/previews/...",
  "detectedTraits": {
    "handType": "slim",
    "nailBed": "medium_long",
    "skinTone": "warm_neutral"
  },
  "selectedLength": "natural_short",
  "selectedShape": "squoval"
}
```

### 5. 再次渲染

用户只改甲型、甲长但不换手图时，不要重新跑完整分割。

`POST /api/try-on/jobs/{jobId}/rerender`

请求：

```json
{
  "selectedLength": "long",
  "selectedShape": "almond"
}
```

实现上复用已保存的 landmarks、mask、规范化图，仅重走渲染阶段。

## Worker 流程

### 阶段 1：图片预处理

输入：用户原图

处理：

- 读取 EXIF，统一方向
- 缩放到目标尺寸，例如长边 1280
- 基础去噪、曝光归一、肤色范围校验
- 失败时直接返回“照片不合格”

输出：

- normalized image

### 阶段 2：手部关键点检测

建议：

- 首选 `MediaPipe Hands` 或同类轻量 landmark 模型

输出：

- 21 个手部关键点
- 每根手指的主轴方向
- 手掌朝向、左右手判定

用途：

- 后续确定每个指甲的纵向方向
- 解决侧手、弯曲和遮挡时的透视不稳定问题

### 阶段 3：指甲分割

建议：

- 首选自训练 `YOLOv8-seg`
- 备选 `Mask R-CNN` / `SAM + prompt`，但上线复杂度更高

输出：

- 每个指甲的 instance mask
- contour polygon
- 置信度

要求：

- 必须是一指一实例，而不是整手一个大 mask
- 需要标记出拇指、食指、中指、无名指、小指的对应关系

### 阶段 4：几何建模

输入：

- landmark
- 每个指甲 mask / contour

处理：

- 计算每个指甲主轴
- 拟合近端 cuticle 曲线和远端 tip 边界
- 生成局部坐标系：along-axis / cross-axis
- 计算延长甲片区域

输出：

- nail geometry descriptor

```json
{
  "finger": "index",
  "axis": [0.12, -0.98],
  "widthPx": 84,
  "lengthPx": 116,
  "cuticleCurve": [...],
  "tipCurve": [...],
  "quad": [...]
}
```

### 阶段 5：款式渲染

不要直接“整张图生成”。正确做法是结构化渲染：

- 先贴 base color
- 再叠加法式边/猫眼高光/闪粉纹理/贴钻 decal
- 按甲型和甲长重建 tip mask
- 做透视变形
- 做 shading、highlight、cuticle fade、边缘 feather

关键算法：

- perspective warp
- convex hull corner fitting
- alpha compositing
- specular shading
- edge feather / blur
- gap fill

### 阶段 6：结果生成

输出：

- full resolution result
- preview image
- optional debug bundle

调试图建议包含：

- landmark overlay
- segmentation masks
- per-nail warped texture
- final composite

## 推荐模型路线

### 路线 A：首版上线

- `MediaPipe Hands`
- `YOLOv8-seg` 自训练指甲分割
- `OpenCV + NumPy` 渲染

优点：

- 最务实
- 可控
- 可解释
- 易调试

这是推荐路线。

### 路线 B：增强版

- 保留路线 A 的几何与分割主链路
- 在最终结果后增加小型生成式 refinement

用途：

- 光影统一
- 贴花自然化
- 边缘补偿

不要让生成式模型直接负责整张手图重绘，否则身份一致性会崩。

## 款式素材规范

每个款式建议建一个目录：

```text
styles/rose-mist/
├── manifest.json
├── base_color.png
├── french_tip.png
├── glitter_overlay.png
├── specular_map.png
├── decal/
│   ├── gem-01.png
│   └── flower-01.png
└── preview.jpg
```

### `manifest.json`

```json
{
  "id": "rose-mist",
  "name": "玫雾法式",
  "finishType": "french",
  "defaultShape": "squoval",
  "defaultLength": "natural_short",
  "layers": [
    {"type": "base", "asset": "base_color.png"},
    {"type": "tip", "asset": "french_tip.png"},
    {"type": "specular", "asset": "specular_map.png"}
  ],
  "renderParams": {
    "cuticleFade": 0.08,
    "tipOpacity": 0.92,
    "highlightStrength": 0.35
  }
}
```

## 任务状态机

```text
created
  -> queued
  -> preprocessing
  -> segmenting
  -> rendering
  -> completed
  -> failed
```

失败码建议标准化：

- `IMAGE_INVALID`
- `HAND_NOT_FOUND`
- `MULTIPLE_HANDS`
- `NAIL_SEGMENTATION_LOW_CONFIDENCE`
- `STYLE_ASSET_INVALID`
- `RENDER_ERROR`
- `WORKER_TIMEOUT`

## 与当前项目的对接

### 服务端

在当前 Python API 基础上新增：

- `/api/try-on/uploads`
- `/api/try-on/jobs`
- `/api/try-on/jobs/{id}`
- `/api/try-on/jobs/{id}/result`
- `/api/try-on/jobs/{id}/rerender`

当前已有的 `try-on session` 可以逐步迁移为真正的 `job` 模型。

### 客户端

客户端页面流可以保持不变：

- 上传手图页
- 识别中页
- 结果页

但需要接真实状态：

- 上传拿到 `objectKey`
- 创建 job
- 轮询 job 状态
- 完成后展示结果图
- 修改甲型/甲长走 rerender

## 实施阶段

### Phase 1

- 完成异步任务模型
- 接入本地文件存储
- worker 先返回 mock 结果图

### Phase 2

- 接入 `MediaPipe Hands`
- 接入 `YOLOv8-seg`
- 输出真实 mask 和 contour

### Phase 3

- 完成 OpenCV 贴图渲染
- 支持纯色、法式、猫眼三类基础款式

### Phase 4

- 支持延长甲片、甲型切换、重渲染
- 增加 debug bundle 和失败分析

### Phase 5

- 引入 refinement 模块
- 优化真实感、耗时和失败率

## 当前建议

- 算法主链路采用 `YOLOv8-seg + MediaPipe + OpenCV`
- 后端编排继续用 Python API
- 推理与渲染 worker 用 Python
- 先做“拍照上传图片试戴”，不要一开始做实时相机 AR

这是当前最稳、最可交付的路线。
