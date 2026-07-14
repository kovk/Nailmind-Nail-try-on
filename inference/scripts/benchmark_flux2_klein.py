from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline
from PIL import Image, ImageOps


DEFAULT_PROMPT = (
    "Image 1 is the base hand photograph. Image 2 is the nail-art reference. "
    "Edit only the visible fingernails in image 1. Transfer the exact colors, patterns, "
    "gloss, french-tip layout, and decorations from image 2 to every visible fingernail. "
    "Keep the exact finger count, hand anatomy, pose, skin texture, skin tone, jewelry, "
    "lighting, background, camera angle, framing, and resolution of image 1 unchanged. "
    "Do not add or remove fingers. Do not change finger length or nail positions. "
    "The result must look like a realistic professional manicure photograph."
)


def load_rgb(path: str) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark FLUX.2 Klein multi-reference nail editing.")
    parser.add_argument("--hand", required=True, help="Base hand photograph (image 1).")
    parser.add_argument("--style", required=True, help="Nail-art reference (image 2).")
    parser.add_argument("--output-dir", default="flux2-klein-results")
    parser.add_argument("--model", default="black-forest-labs/FLUX.2-klein-4B")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hand = load_rgb(args.hand)
    style = load_rgb(args.style)

    torch.set_float32_matmul_precision("high")
    torch.backends.cuda.matmul.allow_tf32 = True

    load_started = time.perf_counter()
    pipe = Flux2KleinPipeline.from_pretrained(args.model, torch_dtype=torch.bfloat16)
    pipe.to("cuda")
    load_seconds = time.perf_counter() - load_started

    durations: list[float] = []
    outputs: list[str] = []
    for index in range(max(1, args.runs)):
        generator = torch.Generator(device="cuda").manual_seed(args.seed + index)
        torch.cuda.synchronize()
        started = time.perf_counter()
        result = pipe(
            prompt=args.prompt,
            image=[hand, style],
            height=args.height,
            width=args.width,
            num_inference_steps=args.steps,
            guidance_scale=1.0,
            generator=generator,
        ).images[0]
        torch.cuda.synchronize()
        duration = time.perf_counter() - started
        output_path = output_dir / f"flux2-klein-{index + 1:02d}.png"
        result.save(output_path)
        durations.append(duration)
        outputs.append(str(output_path))
        print(f"run={index + 1} seed={args.seed + index} inference={duration:.3f}s output={output_path}")

    metrics = {
        "model": args.model,
        "load_seconds": round(load_seconds, 3),
        "runs": len(durations),
        "steps": args.steps,
        "width": args.width,
        "height": args.height,
        "inference_seconds": [round(value, 3) for value in durations],
        "mean_inference_seconds": round(sum(durations) / len(durations), 3),
        "max_cuda_memory_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
        "outputs": outputs,
    }
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
