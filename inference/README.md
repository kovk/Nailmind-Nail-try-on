# NailMind Inference

`inference/` 是独立 AI 图片编辑推理服务，部署在 AutoDL/GPU 服务器。业务服务器只通过 HTTP 调用它，不在 `backend/` 内加载 GPU 模型。

## 推荐规格

优先选择：

```text
RTX 4090 / 4090D / 5090
8 vCPU+
32GB RAM+
100GB 数据盘+
CUDA 12.x
```

如果 4090 没货，可以先用 `RTX 6000D 84GB` 跑通链路。不要优先选 3080、3060、1080Ti 或 CPU。

## 接口

```text
GET  /health
POST /v1/tryon/edit
```

`POST /v1/tryon/edit` 使用 `multipart/form-data`：

```text
hand_image       用户手图，必填
style_image      款式图，必填
style_asset_id   预处理素材包 ID，推荐
style_nail_asset 旧版单张透明甲片 PNG，兼容字段
prompt           可选，业务侧补充编辑要求
response_format  png 或 jpeg，默认 png
```

返回图片 bytes，`Content-Type` 为 `image/png` 或 `image/jpeg`。

款式入库时，`backend/` 调用本服务的 `/v1/styles/extract-nails`。生产链路固定为 `SAM3(fingernail) 文本分割 -> 置信度/面积/长宽比/去重门禁 -> Mask 内缩 1px -> TPS 展平 -> 透明 PNG`。款式预处理是离线任务，不再依赖 YOLO；YOLO 仅保留给用户手图的实时甲面定位。素材始终保留原始像素，不使用生成模型重绘款式。生成后的素材目录包含：

```text
thumb.png / index.png / middle.png / ring.png / pinky.png
all.png
preview.jpg
meta.json
```

业务后端将已复核的透明甲片素材随试戴请求传给 GPU 服务。GPU 服务只负责用户手图指甲定位、甲片几何配准和局部融合。

试戴链路优先传 `style_asset_id`，让 GPU 服务直接读取预处理素材包；旧链路传 `style_nail_asset` 也可兼容。不应在用户发起试戴时再临时从完整款式图里硬贴整图。

## 本地联调

本地默认 mock，不需要 GPU：

```bash
cd inference
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

mock 模式会直接返回原始手图，用于验证后端调用、缓存、鉴权和文件落盘。

## AutoDL 启动

AutoDL 开机自启由 `deploy/autodl/startup.sh` 进入守护进程。守护进程每 30 秒检查推理服务和反向 SSH 隧道，任一掉线都会自动恢复。AutoDL 实例上的启动入口应安装到 `/root/.autodl/startup.sh`。

AutoDL 上推荐用 PyTorch/CUDA 镜像：

```bash
cd inference
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-gpu.txt
cp .env.example .env
```

修改 `.env`：

```text
INFERENCE_HOST=0.0.0.0
INFERENCE_PORT=8090
INFERENCE_TOKEN=<自定义密钥>
INFERENCE_MOCK=false
EDITOR_BACKEND=local_inpaint
PRODUCTION_MODE=true
REQUIRE_STYLE_NAIL_ASSET=true
MODEL_DIR=/root/autodl-tmp/models/sdxl-inpaint-fp16
MODEL_ID=diffusers/stable-diffusion-xl-1.0-inpainting-0.1
DEVICE=cuda
TORCH_DTYPE=float16
MAX_IMAGE_SIDE=1024
MODEL_MAX_IMAGE_SIDE=1024
STYLE_ASSET_CANONICAL_WIDTH=256
STYLE_ASSET_CANONICAL_HEIGHT=384
INFERENCE_STEPS=8
GUIDANCE_SCALE=1.4
STRENGTH=0.72
LOCAL_EDIT_STEPS=6
LOCAL_EDIT_GUIDANCE_SCALE=1.15
LOCAL_EDIT_STRENGTH=0.28
LOCAL_EDIT_CROP_PADDING=72
REFERENCE_ADAPTER_DIR=
REFERENCE_ADAPTER_SUBFOLDER=
REFERENCE_ADAPTER_WEIGHT_NAME=
REFERENCE_ADAPTER_SCALE=0.55
REFERENCE_IMAGE_SIZE=512
ALLOW_HEURISTIC_MASK=false
PRELOAD_MODEL_ON_STARTUP=true
NAILSEG_MODEL_PATH=inference/models/nailseg-yolo11s-best.pt
STYLE_ASSET_DIR=inference/outputs/style-assets
PUBLIC_BASE_URL=http://<gpu-host>:8090
MIN_VALID_NAILS=4
```

FLUX.2 Klein 4B 图片编辑配置：

```text
INFERENCE_MOCK=false
EDITOR_BACKEND=flux2_klein
PRODUCTION_MODE=true
REQUIRE_STYLE_NAIL_ASSET=true
PRELOAD_MODEL_ON_STARTUP=true
TORCH_DTYPE=bfloat16
FLUX2_MODEL_ID=black-forest-labs/FLUX.2-klein-4B
FLUX2_MODEL_DIR=
FLUX2_STEPS=4
FLUX2_GUIDANCE_SCALE=1.0
FLUX2_SEED=42
FLUX2_MAX_IMAGE_SIDE=2048
```

Klein 使用手图和已复核甲片素材作为双图参考，只修改手图中的可见指甲。RTX 5090
实测 768x1024、4 步推理平均约 2.5 秒，模型常驻时可以把端到端目标控制在 10 秒内。
不要为每个请求重新加载模型。

启动：

```bash
python main.py
```

生产环境建议用 `tmux`、`supervisor` 或 Docker 常驻。模型会缓存在服务进程内，不要每次请求重新启动服务。

## Docker 启动

```bash
docker build -t nailmind-inference .
docker run --gpus all -p 8090:8090 \
  -e INFERENCE_TOKEN=<自定义密钥> \
  -e INFERENCE_MOCK=false \
  -e EDITOR_BACKEND=local_inpaint \
  -e PRODUCTION_MODE=true \
  -e REQUIRE_STYLE_NAIL_ASSET=true \
  -e ALLOW_HEURISTIC_MASK=false \
  -e MODEL_DIR=/models/sdxl-inpaint-fp16 \
  -e PRELOAD_MODEL_ON_STARTUP=true \
  -v /root/autodl-tmp/models:/models \
  nailmind-inference
```

## 后端接入

在业务服务器 `backend/api` 的环境变量中配置：

```text
TRYON_INFERENCE_BASE_URL=http://<autodl-host>:8090
TRYON_INFERENCE_TOKEN=<同一个密钥>
TRYON_INFERENCE_TIMEOUT_SECONDS=12
```

配置后，`backend` 只在缓存未命中时调用 GPU 推理。缓存命中仍直接返回本地结果图。后端不压缩手图、款式图或结果图，上传原图会按原始像素进入推理链路。

`MAX_IMAGE_SIDE` 只用于用户手图 YOLO 甲面定位的内部推理尺度，不改变输出图片分辨率。款式图预处理使用 SAM3，不使用该 YOLO 尺度。`MODEL_MAX_IMAGE_SIDE` 只限制局部编辑模型的 crop 输入尺寸；最终结果仍融合回原图尺寸。当前可用生产链路是 `local_inpaint`：先用素材包完成 TPS / perspective 配准，再只对甲面 mask 附近的局部 crop 做模型修复，避免整张手图被重绘。高质量目标链路是 `reference_local_edit`：在 `local_inpaint` 基础上加载 IP-Adapter / Reference Adapter，把款式透明甲片素材作为图像参考输入模型。

`reference_local_edit` 不会静默降级。如果没有配置 `REFERENCE_ADAPTER_DIR` 或权重加载失败，请求会直接返回 `REFERENCE_ADAPTER_MISSING` / `REFERENCE_ADAPTER_LOAD_FAILED`，避免线上继续输出低质量贴图。

如果要把历史款式库的甲面素材全部提前生成：

```bash
cd backend/api
python scripts/precompute_style_nail_assets.py
```

## 指甲分割模型训练

当前数据集已按 Kaggle `NailSegmentationDatasetV2` 结构支持转换：

```text
datasets/nail-seg-raw/NailSegmentationDatasetV2/
  train/images
  train/masks
  val/images
  val/masks
  test/images
  test/masks
```

先转换成 YOLO segmentation 格式：

```bash
python3 inference/scripts/prepare_nailseg_yolo.py \
  --raw-root datasets/nail-seg-raw/NailSegmentationDatasetV2 \
  --out-root datasets/nail-yolo \
  --overwrite
```

转换后目录：

```text
datasets/nail-yolo/
  data.yaml
  images/train
  images/val
  images/test
  labels/train
  labels/val
  labels/test
```

AutoDL 上训练：

```bash
cd /root/autodl-tmp/nailmind
/root/miniconda3/bin/python -m pip install ultralytics
YOLO_CONFIG_DIR=/root/autodl-tmp/ultralytics \
  /root/miniconda3/bin/yolo segment train \
  model=yolo11s-seg.yaml \
  data=datasets/nail-yolo/data.yaml \
  epochs=120 \
  imgsz=896 \
  batch=12 \
  device=0 \
  project=runs/nailseg \
  name=yolo11s-seg-nail-scratch \
  workers=8 \
  pretrained=False \
  patience=30 \
  close_mosaic=10
```

本项目首版已在 AutoDL RTX 5090 上完成一次训练：

```text
model: YOLO11s-seg
epochs: 120
imgsz: 896
train time: 3.391 hours
val images: 677
val instances: 3102
box mAP50: 0.986
mask mAP50: 0.979
mask mAP50-95: 0.788
speed: 2.1ms inference / image
```

远端权重路径：

```text
/root/autodl-tmp/nailmind/runs/segment/runs/nailseg/yolo11s-seg-nail-scratch/weights/best.pt
```

本地已拉取到：

```text
inference/models/nailseg-yolo11s-best.pt
```

后续推理服务应优先使用这个 YOLO segmentation mask，再进入几何贴图和 AI 边缘融合。这个数据集能做第一版，但它包含单甲、甲片模板和真实手图混合样本；上线前还需要补一批你们 App 真实上传手图做二次微调，否则复杂姿势和低清手图仍会漏检。

## 压测

```bash
python scripts/benchmark_tryon.py \
  --url http://127.0.0.1:8090/v1/tryon/edit \
  --hand /path/to/hand.png \
  --style /path/to/style.png \
  --runs 5 \
  --token <自定义密钥>
```

输出会包含 `mean / p50 / p90 / p99`，用于判断是否接近 10s。

## 当前实现

- `mock`：直接返回标准化手图，只能用于联调，生产模式会拒绝启动这类请求。
- `mask_only`：返回指甲 mask 叠加图，只能用于检查定位，生产模式会拒绝启动这类请求。
- `overlay` / `nail_overlay`：使用 YOLOv11-seg 分割用户指甲，把预处理透明甲片素材逐指贴合到目标甲面。
- `local_inpaint`：先使用预抠甲面资产按目标手图甲面角度贴合，再裁出甲面局部区域，让局部编辑模型只修复 mask 内的纹理、边缘、反光和光影。它主要负责自然融合，不真正理解款式图。
- `reference_local_edit` / `reference_inpaint` / `ip_adapter_inpaint`：在 `local_inpaint` 基础上加载参考图适配器，把款式甲片素材合成参考图并传入 `ip_adapter_image`。它才是“局部编辑模型理解款式”的生产目标。
- `hybrid_overlay`：旧版整图缩放后融合，不推荐生产使用，容易带来清晰度下降。
- `sdxl_inpaint`：使用 SDXL inpaint 对指甲 mask 区域进行局部图片编辑。
- `flux2_klein`：使用 FLUX.2 Klein 4B 双图编辑，第一张图为用户手图，第二张图为已复核甲片素材；固定种子和 4 步推理，优先保证手部一致性与低延迟。

上线配置必须满足：

- `PRODUCTION_MODE=true`
- `REQUIRE_STYLE_NAIL_ASSET=true`
- `ALLOW_HEURISTIC_MASK=false`
- 款式入库后由 `backend/` 调用大模型 API 生成透明五甲片资产；生成失败就进入人工复核，不允许把整张款式图当资产。

当前线上主链路是 `local_inpaint`：它不重绘整只手，流程为“用户指甲 YOLO mask -> 读取款式透明甲片素材包 -> 单片几何配准 -> alpha feather -> 光照匹配 -> 高光保留 -> 裁剪甲面局部 -> SDXL inpaint 修边”。`REGISTRATION_MODE=perspective` 使用稳定透视配准；`REGISTRATION_MODE=tps` 会尝试 OpenCV Thin Plate Spline，运行环境不支持或样本点失败时自动回退到 `perspective_fallback`，并写入响应指标。`ENABLE_EDGE_REPAIR=true` 只修复甲面边界，不重绘手部、皮肤或背景。

如果需要让模型真正理解款式图，应切换到 `EDITOR_BACKEND=reference_local_edit`，并配置参考适配器权重。该模式会在局部 crop inpaint 时传入由透明甲片素材合成的参考图，适合复杂法式边、猫眼、钻饰、渐变等款式；但速度会比 `local_inpaint` 慢，需要在 AutoDL 上实测。

生产链路禁止：

- 没有 `style_asset_id` 时临时拿整张款式图硬贴。
- 未检测到有效手部或有效指甲少于 `MIN_VALID_NAILS` 时继续生成。
- 用整图大模型重绘手、皮肤、背景或改变手指数量。

如果后续换 FLUX Kontext 或自研模型，只需要替换 `app/editor.py` 中的模型实现，后端和 App 接口不变。
