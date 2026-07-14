from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import get_settings
from .mask import NailMaskDetector, NailRegion

FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")


def extract_style_nail_asset_package(image_bytes: bytes, public_base_url: str | None = None) -> dict[str, Any]:
    """Extract style nails into a reusable transparent asset package.

    The package is intentionally file-based so backend can store an asset_id and
    inference can load the same five transparent nail references at try-on time.
    """
    settings = get_settings()
    asset_id = hashlib.sha256(image_bytes).hexdigest()[:24]
    asset_dir = Path(settings.style_asset_dir) / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    for stale_name in (*[f"{name}.png" for name in FINGER_NAMES], "all.png", "preview.jpg", "meta.json"):
        (asset_dir / stale_name).unlink(missing_ok=True)

    image = Image.open(BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image).convert("RGBA")

    detector = NailMaskDetector(
        allow_heuristic=False,
        dilate=max(2, settings.mask_dilate // 2),
        blur=max(1, settings.mask_blur // 3),
    )
    detection = detector.detect_style_regions(image.convert("RGB"))
    regions = _select_style_regions(detection.regions)

    nail_entries: list[dict[str, Any]] = []
    valid_areas: list[float] = []
    rejected_regions: list[dict[str, Any]] = []
    for region in regions[: len(FINGER_NAMES)]:
        finger = FINGER_NAMES[len(nail_entries)]
        filename = f"{finger}.png"
        try:
            nail_image, area, geometry = _crop_region_asset(image, detector, region)
        except RuntimeError as exc:
            rejected_regions.append(
                {
                    "center": [round(region.center_x, 2), round(region.center_y, 2)],
                    "reason": str(exc),
                }
            )
            continue
        nail_image.save(asset_dir / filename, format="PNG")
        valid_areas.append(area)
        nail_entries.append(
            {
                "finger": finger,
                "file": filename,
                "url": _asset_url(asset_id, filename, public_base_url),
                "center": [round(region.center_x, 2), round(region.center_y, 2)],
                "size": [round(region.width, 2), round(region.height, 2)],
                "angle": round(region.angle, 2),
                "geometry": geometry,
                "mask_area": round(area, 2),
                "quality_score": _score_region(region, area, image.size),
                "segmentation_confidence": round(region.confidence, 4),
                "segmentation_source": region.source,
            }
        )

    source_nail_count = len(nail_entries)
    status = "ready" if source_nail_count >= settings.min_valid_nails else "needs_review"
    if not nail_entries:
        status = "failed" if settings.production_mode else "needs_review"

    all_asset = _build_all_asset(nail_entries, asset_dir)
    all_asset.save(asset_dir / "all.png", format="PNG")

    preview = _checkerboard_preview(all_asset)
    preview.thumbnail((960, 420), Image.Resampling.LANCZOS)
    preview.save(asset_dir / "preview.jpg", format="JPEG", quality=100, subsampling=0)

    generated_count = 0
    review_required = status != "ready" or source_nail_count < len(FINGER_NAMES)
    warnings = _asset_review_warnings(
        status=status,
        source_nail_count=source_nail_count,
        generated_count=generated_count,
        min_valid_nails=settings.min_valid_nails,
    )
    quality_score = _score_package(nail_entries)
    meta: dict[str, Any] = {
        "schema_version": 5,
        "asset_kind": "source_pixel_tps_nail_package",
        "asset_id": asset_id,
        "status": status,
        "quality_score": quality_score,
        "image_size": [image.width, image.height],
        "canonical_size": [
            int(settings.style_asset_canonical_width),
            int(settings.style_asset_canonical_height),
        ],
        "min_valid_nails": settings.min_valid_nails,
        "source_nail_count": source_nail_count,
        "finger_count": len(nail_entries),
        "generated_count": generated_count,
        "review_required": review_required,
        "warnings": warnings,
        "completion_strategy": None,
        "missing_finger_policy": "runtime_nearest_texture_reuse" if source_nail_count < len(FINGER_NAMES) else None,
        "segmentation_mode": detection.mode,
        "yolo_candidate_count": detection.yolo_candidate_count,
        "sam3_candidate_count": detection.sam3_candidate_count,
        "sam3_refined_count": detection.refined_count,
        "rejected_region_count": len(rejected_regions),
        "rejected_regions": rejected_regions,
        "segmentation_warning": detection.warning,
        "registration_mode": "tps",
        "source_pixels_preserved": True,
        "generative_model_used": False,
        "finger_order_strategy": "dominant_area_then_x_order",
        "nails": nail_entries,
        "all": {"file": "all.png", "url": _asset_url(asset_id, "all.png", public_base_url)},
        "preview_url": _asset_url(asset_id, "preview.jpg", public_base_url),
        "needs_review_reason": _needs_review_reason(status, source_nail_count, settings.min_valid_nails),
    }
    (asset_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "asset_id": asset_id,
        "status": status,
        "quality_score": quality_score,
        "nails": nail_entries,
        "preview_url": meta["preview_url"],
        "meta_url": _asset_url(asset_id, "meta.json", public_base_url),
        "asset_dir": str(asset_dir),
        "meta": meta,
    }


def extract_style_nail_asset(image_bytes: bytes) -> bytes:
    """Backward-compatible helper returning the package's `all.png` bytes."""
    package = extract_style_nail_asset_package(image_bytes)
    asset_dir = Path(package["asset_dir"])
    all_path = asset_dir / "all.png"
    if not all_path.exists():
        raise RuntimeError("STYLE_ASSET_MISSING: 未能生成款式甲面素材。")
    return all_path.read_bytes()


def load_style_asset_images(asset_id: str) -> list[Image.Image]:
    settings = get_settings()
    safe_asset_id = "".join(ch for ch in asset_id if ch.isalnum() or ch in {"-", "_"})
    asset_dir = Path(settings.style_asset_dir) / safe_asset_id
    if not asset_dir.exists():
        raise RuntimeError("STYLE_ASSET_MISSING: 款式甲面素材包不存在。")
    images: list[Image.Image] = []
    for name in FINGER_NAMES:
        path = asset_dir / f"{name}.png"
        if path.exists():
            images.append(Image.open(path).convert("RGBA"))
    if not images:
        fallback = asset_dir / "all.png"
        if fallback.exists():
            images.append(Image.open(fallback).convert("RGBA"))
    if not images:
        raise RuntimeError("STYLE_ASSET_MISSING: 款式甲面素材包为空。")
    return images


def _select_style_regions(regions: list[NailRegion]) -> list[NailRegion]:
    filtered = [
        region
        for region in regions
        if region.width >= 4 and region.height >= 7 and region.height / max(region.width, 1.0) <= 5.8
    ]
    # YOLO can return tiny decoration masks around rhinestones or highlights.
    # Keep the five dominant nail masks first, then order them consistently.
    dominant = sorted(filtered, key=_region_area_hint, reverse=True)[:5]
    return sorted(dominant, key=lambda item: item.center_x)


def _asset_review_warnings(
    *,
    status: str,
    source_nail_count: int,
    generated_count: int,
    min_valid_nails: int,
) -> list[str]:
    warnings: list[str] = []
    if status != "ready":
        warnings.append("素材包未达到直接上线状态，需要人工复核。")
    if source_nail_count < min_valid_nails:
        warnings.append(f"原图仅识别到 {source_nail_count} 片有效甲面，少于上线阈值 {min_valid_nails} 片。")
    elif source_nail_count < len(FINGER_NAMES):
        warnings.append(f"原图识别到 {source_nail_count} 片甲面，未复制或生成缺失甲片。")
    return warnings


def _region_area_hint(region: NailRegion) -> float:
    if region.polygon:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            return abs(float(cv2.contourArea(np.asarray(region.polygon, dtype=np.float32))))
        except Exception:
            pass
    return float(region.width * region.height)


def _crop_region_asset(
    image: Image.Image,
    detector: NailMaskDetector,
    region: NailRegion,
) -> tuple[Image.Image, float, dict[str, Any]]:
    standardized = _standardize_region_asset(image, region)
    if standardized is not None:
        asset, area, geometry = standardized
        return asset, area, geometry
    raise RuntimeError("LOW_QUALITY_ASSET: 真实分割多边形无法完成 TPS 展平。")


def _standardize_region_asset(image: Image.Image, region: NailRegion) -> tuple[Image.Image, float, dict[str, Any]] | None:
    """Perspective-normalize one detected nail into an upright transparent asset.

    The try-on stage needs a reusable nail plate, not an angled crop from a model
    hand. We warp the source mask and texture into a canonical nail canvas so the
    runtime can then warp that canonical plate onto the user's nail geometry.
    """
    if not region.polygon or len(region.polygon) < 4:
        return None
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None

    settings = get_settings()
    polygon = np.asarray(region.polygon, dtype=np.float32)
    if polygon.shape[0] < 4:
        return None
    rect = cv2.minAreaRect(polygon)
    box = cv2.boxPoints(rect).astype(np.float32)
    source_quad = _order_quad_points(box)

    target_w = max(96, int(settings.style_asset_canonical_width))
    target_h = max(144, int(settings.style_asset_canonical_height))
    target_quad = np.asarray(
        [
            [target_w * 0.18, target_h * 0.06],
            [target_w * 0.82, target_h * 0.06],
            [target_w * 0.88, target_h * 0.94],
            [target_w * 0.12, target_h * 0.94],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(source_quad, target_quad)
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    warped = cv2.warpPerspective(
        rgba,
        matrix,
        (target_w, target_h),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    source_mask = np.zeros((image.height, image.width), dtype=np.uint8)
    cv2.fillPoly(source_mask, [polygon.astype(np.int32)], 255)
    erode_pixels = max(0, int(settings.style_asset_mask_erode))
    if erode_pixels:
        source_mask = cv2.erode(
            source_mask,
            np.ones((3, 3), dtype=np.uint8),
            iterations=erode_pixels,
        )
    warped_mask = cv2.warpPerspective(
        source_mask,
        matrix,
        (target_w, target_h),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    nail_shape = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(nail_shape)
    draw.rounded_rectangle(
        (
            int(target_w * 0.14),
            int(target_h * 0.04),
            int(target_w * 0.86),
            int(target_h * 0.96),
        ),
        radius=int(target_w * 0.36),
        fill=255,
    )
    shape_np = np.asarray(nail_shape, dtype=np.uint8)
    tps_result = _tps_flatten(warped, warped_mask, shape_np)
    if tps_result is None:
        return None
    warped, alpha, control_points = tps_result
    # Source photos commonly contain a bright outline or skin pixels at the
    # segmentation boundary. Keep the canonical asset edge crisp; runtime
    # feathering is applied against the user's precise nail mask instead.
    alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=0.55)
    warped[:, :, 3] = alpha

    bbox = Image.fromarray(alpha, mode="L").getbbox()
    if not bbox:
        return None
    pad = max(4, int(min(target_w, target_h) * 0.035))
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(target_w, bbox[2] + pad)
    bottom = min(target_h, bbox[3] + pad)
    asset = Image.fromarray(warped, mode="RGBA").crop((left, top, right, bottom))
    area = float(np.sum(alpha > 8))
    return asset, area, {
        "mode": "canonical_tps",
        "source_quad": [[round(float(x), 2), round(float(y), 2)] for x, y in source_quad],
        "tps_control_points": control_points,
        "canonical_size": [asset.width, asset.height],
        "crop_box": [left, top, right, bottom],
        "source_mask_erode": erode_pixels,
    }


def _tps_flatten(source_rgba, source_mask, target_mask):
    """Warp a segmented source nail onto a canonical nail using inverse TPS.

    RGB values are sampled only from the perspective-normalized source image;
    no color, pattern or decoration is synthesized by this operation.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None

    source_points = _mask_boundary_landmarks(source_mask)
    target_points = _mask_boundary_landmarks(target_mask)
    if source_points is None or target_points is None:
        return None
    weights_x = _solve_tps(target_points, source_points[:, 0])
    weights_y = _solve_tps(target_points, source_points[:, 1])
    height, width = target_mask.shape
    grid_y, grid_x = np.mgrid[0:height, 0:width]
    query = np.column_stack((grid_x.reshape(-1), grid_y.reshape(-1))).astype(np.float64)
    map_x = _evaluate_tps(query, target_points, weights_x).reshape(height, width).astype(np.float32)
    map_y = _evaluate_tps(query, target_points, weights_y).reshape(height, width).astype(np.float32)
    source_float = source_rgba.astype(np.float32)
    source_alpha = source_mask.astype(np.float32) / 255.0
    source_float[:, :, :3] *= source_alpha[:, :, None]
    source_float[:, :, 3] = source_mask.astype(np.float32)
    remapped_premultiplied = cv2.remap(
        source_float,
        map_x,
        map_y,
        interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    remapped_mask = cv2.remap(
        source_mask,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    alpha = np.minimum(remapped_mask, target_mask)
    remapped = np.zeros_like(remapped_premultiplied, dtype=np.float32)
    safe_alpha = remapped_mask.astype(np.float32) / 255.0
    visible = safe_alpha > 1e-4
    remapped[visible, :3] = remapped_premultiplied[visible, :3] / safe_alpha[visible, None]
    remapped[:, :, 3] = alpha
    remapped = np.clip(remapped, 0, 255).astype(np.uint8)
    controls = {
        "source": [[round(float(x), 2), round(float(y), 2)] for x, y in source_points],
        "target": [[round(float(x), 2), round(float(y), 2)] for x, y in target_points],
    }
    return remapped, alpha, controls


def _mask_boundary_landmarks(mask):
    import numpy as np  # type: ignore

    binary = np.asarray(mask) > 16
    ys = np.flatnonzero(binary.any(axis=1))
    if len(ys) < 8:
        return None
    top, bottom = int(ys[0]), int(ys[-1])
    span = bottom - top
    if span < 7:
        return None

    def stable_row(fraction: float):
        target_y = int(round(top + span * fraction))
        for offset in range(0, max(3, span // 8) + 1):
            candidates = (target_y,) if offset == 0 else (target_y - offset, target_y + offset)
            for candidate_y in candidates:
                if candidate_y < top or candidate_y > bottom:
                    continue
                row = np.flatnonzero(binary[candidate_y])
                if len(row) >= 2:
                    return candidate_y, row
        return None

    points: list[tuple[float, float]] = []
    top_row = stable_row(0.03)
    bottom_row = stable_row(0.97)
    if top_row is None or bottom_row is None:
        return None
    points.append((float(top_row[1].mean()), float(top_row[0])))
    sampled_rows: list[tuple[int, Any]] = []
    for fraction in (0.15, 0.35, 0.58, 0.80):
        sampled = stable_row(fraction)
        if sampled is None:
            return None
        sampled_rows.append(sampled)
        y, row = sampled
        points.append((float(row[0]), float(y)))
    points.append((float(bottom_row[1].mean()), float(bottom_row[0])))
    for y, row in reversed(sampled_rows):
        points.append((float(row[-1]), float(y)))
    return np.asarray(points, dtype=np.float64)


def _solve_tps(control_points, values):
    import numpy as np  # type: ignore

    count = len(control_points)
    delta = control_points[:, None, :] - control_points[None, :, :]
    radius_sq = np.sum(delta * delta, axis=2)
    kernel = radius_sq * np.log(radius_sq + 1e-8)
    affine = np.column_stack((np.ones(count), control_points))
    system = np.block([[kernel + np.eye(count) * 1e-5, affine], [affine.T, np.zeros((3, 3))]])
    target = np.concatenate((np.asarray(values, dtype=np.float64), np.zeros(3)))
    return np.linalg.solve(system, target)


def _evaluate_tps(query_points, control_points, weights):
    import numpy as np  # type: ignore

    delta = query_points[:, None, :] - control_points[None, :, :]
    radius_sq = np.sum(delta * delta, axis=2)
    kernel = radius_sq * np.log(radius_sq + 1e-8)
    return kernel @ weights[: len(control_points)] + weights[-3] + query_points @ weights[-2:]


def _order_quad_points(points):
    import numpy as np  # type: ignore

    pts = np.asarray(points, dtype=np.float32)
    ordered = np.zeros((4, 2), dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    ordered[0] = pts[np.argmin(sums)]
    ordered[2] = pts[np.argmax(sums)]
    ordered[1] = pts[np.argmin(diffs)]
    ordered[3] = pts[np.argmax(diffs)]
    return ordered


def _build_all_asset(nails: list[dict[str, Any]], asset_dir: Path) -> Image.Image:
    tile_width, tile_height, gap = 256, 384, 24
    sheet = Image.new("RGBA", (tile_width * 5 + gap * 6, tile_height + gap * 2), (0, 0, 0, 0))
    for index, nail in enumerate(nails[:5]):
        source = Image.open(asset_dir / str(nail["file"])).convert("RGBA")
        source.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        x = gap + index * (tile_width + gap) + (tile_width - source.width) // 2
        y = gap + (tile_height - source.height) // 2
        sheet.alpha_composite(source, (x, y))
    return sheet


def _checkerboard_preview(sheet: Image.Image) -> Image.Image:
    cell = 18
    preview = Image.new("RGB", sheet.size, (250, 250, 250))
    draw = ImageDraw.Draw(preview)
    for y in range(0, sheet.height, cell):
        for x in range(0, sheet.width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(224, 224, 224))
    preview.paste(sheet, mask=sheet.getchannel("A"))
    return preview


def _score_region(region: NailRegion, area: float, image_size: tuple[int, int]) -> float:
    image_area = image_size[0] * image_size[1]
    area_ratio = area / max(image_area, 1)
    size_score = min(1.0, max(0.0, area_ratio / 0.004))
    aspect = region.height / max(region.width, 1.0)
    aspect_score = 1.0 if 1.2 <= aspect <= 4.8 else 0.65
    confidence_score = max(0.0, min(1.0, region.confidence)) if region.confidence else 0.7
    return round(
        max(0.1, min(1.0, size_score * 0.45 + aspect_score * 0.25 + confidence_score * 0.3)),
        3,
    )


def _score_package(nails: list[dict[str, Any]]) -> float:
    if not nails:
        return 0.0
    count_score = min(1.0, len(nails) / 5)
    region_score = sum(float(nail["quality_score"]) for nail in nails) / len(nails)
    return round(count_score * 0.45 + region_score * 0.55, 3)


def _needs_review_reason(status: str, nail_count: int, min_valid_nails: int) -> str | None:
    if status == "ready":
        return None
    if nail_count == 0:
        return "未能识别有效甲面，需要人工上传透明甲片素材。"
    if nail_count < min_valid_nails:
        return f"仅识别到 {nail_count} 片甲面，少于上线要求 {min_valid_nails} 片。"
    return "素材质量不足，需要人工复核。"


def _asset_url(asset_id: str, filename: str, public_base_url: str | None = None) -> str:
    settings = get_settings()
    base = (public_base_url or settings.public_base_url).strip().rstrip("/")
    if base:
        return f"{base}/style-assets/{asset_id}/{filename}"
    return str(Path(settings.style_asset_dir) / asset_id / filename)
