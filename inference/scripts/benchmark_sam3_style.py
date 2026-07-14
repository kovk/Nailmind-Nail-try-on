from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from sam3.model.sam3_image_processor import Sam3Processor
from sam3.model_builder import build_sam3_image_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark SAM 3 fingernail segmentation on one style image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prompt", default="fingernail")
    parser.add_argument("--min-score", type=float, default=0.25)
    parser.add_argument("--max-masks", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(args.image).convert("RGB")
    image_np = np.asarray(image)

    started = time.perf_counter()
    model = build_sam3_image_model(
        checkpoint_path=args.checkpoint,
        load_from_HF=False,
        device="cuda",
        eval_mode=True,
    )
    processor = Sam3Processor(model)
    load_seconds = time.perf_counter() - started

    inference_started = time.perf_counter()
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        state = processor.set_image(image)
        result = processor.set_text_prompt(state=state, prompt=args.prompt)
    inference_seconds = time.perf_counter() - inference_started

    masks = result["masks"].detach().float().cpu().numpy()
    scores = result["scores"].detach().float().cpu().numpy().reshape(-1)
    boxes = result["boxes"].detach().float().cpu().numpy() if "boxes" in result else None
    while masks.ndim > 3 and masks.shape[1] == 1:
        masks = masks[:, 0]

    candidates: list[tuple[float, np.ndarray, list[float] | None]] = []
    for index, score in enumerate(scores):
        if index >= len(masks) or float(score) < args.min_score:
            continue
        mask = masks[index] > 0.0
        area_ratio = float(mask.mean())
        if area_ratio < 0.00002 or area_ratio > 0.04:
            continue
        box = boxes[index].tolist() if boxes is not None and index < len(boxes) else None
        candidates.append((float(score), mask, box))
    candidates.sort(key=lambda item: item[0], reverse=True)
    candidates = candidates[: args.max_masks]

    overlay = image.convert("RGBA")
    overlay_pixels = np.asarray(overlay).copy()
    colors = ((237, 72, 128), (73, 168, 255), (77, 196, 138), (255, 176, 59), (157, 108, 255))
    items: list[dict[str, object]] = []
    for index, (score, mask, box) in enumerate(candidates):
        alpha = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        rgba = Image.fromarray(image_np, mode="RGB").convert("RGBA")
        rgba.putalpha(alpha)
        filename = f"nail-{index + 1:02d}.png"
        rgba.getbbox() and rgba.crop(alpha.getbbox()).save(output_dir / filename, format="PNG")
        color = colors[index % len(colors)]
        overlay_pixels[mask, :3] = (
            overlay_pixels[mask, :3].astype(np.float32) * 0.48 + np.asarray(color, dtype=np.float32) * 0.52
        ).astype(np.uint8)
        items.append(
            {
                "file": filename,
                "score": round(score, 5),
                "area_ratio": round(float(mask.mean()), 7),
                "box": box,
            }
        )

    overlay = Image.fromarray(overlay_pixels, mode="RGBA")
    draw = ImageDraw.Draw(overlay)
    draw.text((20, 20), f"SAM 3: {args.prompt} | masks={len(items)}", fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    overlay.save(output_dir / "overlay.png", format="PNG")
    report = {
        "prompt": args.prompt,
        "mask_count": len(items),
        "model_load_seconds": round(load_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "items": items,
    }
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
