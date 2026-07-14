from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

import requests
from PIL import Image


DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
DEFAULT_MODEL = "qwen-image-2.0-pro"


def image_to_data_uri(path: Path) -> str:
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('utf-8')}"


def remove_light_background(input_path: Path, output_path: Path) -> None:
    """Best-effort alpha cleanup when the model returns a white/pale background."""
    image = Image.open(input_path).convert("RGBA")
    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # Most generated transparent-asset attempts come back on near-white.
            if r > 238 and g > 232 and b > 232:
                pixels[x, y] = (r, g, b, 0)
            elif r > 225 and g > 215 and b > 215:
                pixels[x, y] = (r, g, b, int(a * 0.25))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Use qwen-image-2.0-pro to extract one transparent nail asset.")
    parser.add_argument("--input", required=True, type=Path, help="Style image path.")
    parser.add_argument("--output", required=True, type=Path, help="Output transparent PNG path.")
    parser.add_argument("--raw-output", type=Path, help="Raw model image path before alpha cleanup.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("DASHSCOPE_API_KEY is not set", file=sys.stderr)
        return 2

    raw_output = args.raw_output or args.output.with_name(args.output.stem + "_raw.png")
    prompt = (
        "请把输入图片中的美甲款式预处理成一个可用于虚拟试戴的单片甲片素材。"
        "只输出一片最清晰、最完整、最能代表该款式的甲面，正视角、竖向居中、无手指、无皮肤、无背景、无文字、无边框。"
        "保留原款式的颜色、渐变、纹理、高光、亮片、图案和装饰。"
        "甲片边缘要干净，背景必须为透明 PNG。如果无法真正透明，请使用纯白背景且不要有阴影，方便后处理抠 alpha。"
    )
    payload = {
        "model": args.model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": image_to_data_uri(args.input)},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {"n": 1, "prompt_extend": True, "watermark": False},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = requests.post(DASHSCOPE_API_URL, json=payload, headers=headers, timeout=180)
    try:
        data = response.json()
    except Exception:
        print(f"DashScope returned non-json HTTP {response.status_code}: {response.text[:500]}", file=sys.stderr)
        return 1
    if response.status_code != 200 or "output" not in data:
        print(f"DashScope failed HTTP {response.status_code}: {data}", file=sys.stderr)
        return 1
    image_url = data["output"]["choices"][0]["message"]["content"][0]["image"]
    image_response = requests.get(image_url, timeout=90)
    image_response.raise_for_status()
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_bytes(image_response.content)
    remove_light_background(raw_output, args.output)
    print(args.output)
    print(raw_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
