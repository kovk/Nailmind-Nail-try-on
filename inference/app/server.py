from __future__ import annotations

import json

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from io import BytesIO
from pathlib import Path

from .config import get_settings
from .editor import TryOnEditor
from .style_asset import extract_style_nail_asset_package


app = FastAPI(title="NailMind Inference", version="0.1.0")
_editor: TryOnEditor | None = None
_settings = get_settings()
Path(_settings.style_asset_dir).mkdir(parents=True, exist_ok=True)
app.mount("/style-assets", StaticFiles(directory=_settings.style_asset_dir), name="style-assets")


def get_editor() -> TryOnEditor:
    global _editor
    if _editor is None:
        _editor = TryOnEditor()
    return _editor


@app.on_event("startup")
def preload_model_if_needed() -> None:
    settings = get_settings()
    if settings.preload_model_on_startup and not settings.inference_mock:
        get_editor().preload()


def require_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.inference_token.strip()
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid inference token")


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "mock": settings.inference_mock,
        "backend": settings.editor_backend,
        "productionMode": settings.production_mode,
        "requireStyleNailAsset": settings.require_style_nail_asset,
        "allowHeuristicMask": settings.allow_heuristic_mask,
        "modelDir": settings.model_dir,
        "flux2ModelDir": settings.flux2_model_dir,
        "flux2ModelId": settings.flux2_model_id,
        "flux2Steps": settings.flux2_steps,
        "flux2GuidanceScale": settings.flux2_guidance_scale,
        "flux2InpaintStrength": settings.flux2_inpaint_strength,
        "flux2InpaintPadding": settings.flux2_inpaint_padding,
        "flux2InpaintEdgeWidth": settings.flux2_inpaint_edge_width,
        "flux2Seed": settings.flux2_seed,
        "flux2MaxImageSide": settings.flux2_max_image_side,
        "preloadModelOnStartup": settings.preload_model_on_startup,
        "nailsegModelPath": settings.nailseg_model_path,
        "nailsegModelExists": Path(settings.nailseg_model_path).exists(),
        "userNailSegmenter": settings.user_nail_segmenter,
        "userNailAllowYoloFallback": settings.user_nail_allow_yolo_fallback,
        "styleAssetSegmenter": settings.style_asset_segmenter,
        "sam3CheckpointPath": settings.sam3_checkpoint_path,
        "sam3CheckpointExists": Path(settings.sam3_checkpoint_path).exists(),
        "sam3AllowYoloFallback": settings.sam3_allow_yolo_fallback,
        "styleAssetDir": settings.style_asset_dir,
        "minValidNails": settings.min_valid_nails,
        "maxImageSide": settings.max_image_side,
        "modelMaxImageSide": settings.model_max_image_side,
        "styleAssetCanonicalSize": [
            settings.style_asset_canonical_width,
            settings.style_asset_canonical_height,
        ],
        "styleAssetMaskErode": settings.style_asset_mask_erode,
        "registrationMode": settings.registration_mode,
        "edgeRepairEnabled": settings.enable_edge_repair,
        "edgeRepairStrength": settings.edge_repair_strength,
        "localEditSteps": settings.local_edit_steps,
        "localEditGuidanceScale": settings.local_edit_guidance_scale,
        "localEditStrength": settings.local_edit_strength,
        "localEditCropPadding": settings.local_edit_crop_padding,
        "referenceAdapterConfigured": bool(settings.reference_adapter_dir.strip()),
        "referenceAdapterDir": settings.reference_adapter_dir,
        "referenceAdapterSubfolder": settings.reference_adapter_subfolder,
        "referenceAdapterWeightName": settings.reference_adapter_weight_name,
        "referenceAdapterScale": settings.reference_adapter_scale,
        "referenceImageSize": settings.reference_image_size,
    }


@app.post("/v1/tryon/edit")
async def edit_tryon(
    hand_image: UploadFile = File(...),
    style_image: UploadFile = File(...),
    style_nail_asset: UploadFile | None = File(default=None),
    style_asset_id: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str = Form(default="png"),
    _: None = Depends(require_token),
) -> Response:
    normalized_format = response_format.lower().replace("image/", "")
    if normalized_format not in {"png", "jpeg", "jpg"}:
        raise HTTPException(status_code=400, detail="only png and jpeg response_format are supported")
    hand_bytes = await hand_image.read()
    style_bytes = await style_image.read()
    asset_bytes = await style_nail_asset.read() if style_nail_asset else None
    if not hand_bytes or not style_bytes:
        raise HTTPException(status_code=400, detail="hand_image and style_image are required")
    try:
        edit_result = get_editor().edit_with_metrics(
            hand_image=hand_bytes,
            style_image=style_bytes,
            style_nail_asset=asset_bytes,
            style_asset_id=style_asset_id,
            prompt=prompt,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    result = edit_result.image_bytes
    metrics_header = json.dumps(edit_result.metrics, ensure_ascii=True, separators=(",", ":"))
    if normalized_format in {"jpeg", "jpg"}:
        image = Image.open(BytesIO(result)).convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=100, subsampling=0)
        return Response(
            content=output.getvalue(),
            media_type="image/jpeg",
            headers={"X-NailMind-Tryon-Metrics": metrics_header},
        )
    return Response(content=result, media_type="image/png", headers={"X-NailMind-Tryon-Metrics": metrics_header})


@app.post("/v1/styles/extract-nails")
async def extract_style_nails(
    request: Request,
    style_image: UploadFile = File(...),
    _: None = Depends(require_token),
) -> JSONResponse:
    style_bytes = await style_image.read()
    if not style_bytes:
        raise HTTPException(status_code=400, detail="style_image is required")
    try:
        result = extract_style_nail_asset_package(style_bytes, public_base_url=str(request.base_url).rstrip("/"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JSONResponse(content=result)
