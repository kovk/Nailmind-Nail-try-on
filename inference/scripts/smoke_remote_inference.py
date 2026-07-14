from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the NailMind inference HTTP contract.")
    parser.add_argument("--base-url", default=os.getenv("TRYON_INFERENCE_BASE_URL", ""))
    parser.add_argument("--token", default=os.getenv("TRYON_INFERENCE_TOKEN", ""))
    parser.add_argument("--hand", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--asset")
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    if not args.base_url:
        raise SystemExit("missing --base-url or TRYON_INFERENCE_BASE_URL")

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    handles = []
    try:
        hand = Path(args.hand).open("rb")
        style = Path(args.style).open("rb")
        handles.extend([hand, style])
        files = {
            "hand_image": (Path(args.hand).name, hand, "application/octet-stream"),
            "style_image": (Path(args.style).name, style, "application/octet-stream"),
        }
        if args.asset:
            asset = Path(args.asset).open("rb")
            handles.append(asset)
            files["style_nail_asset"] = (Path(args.asset).name, asset, "image/png")

        started = time.perf_counter()
        response = requests.post(
            f"{args.base_url.rstrip('/')}/v1/tryon/edit",
            headers=headers,
            files=files,
            data={"response_format": "png"},
            timeout=args.timeout,
        )
        elapsed = time.perf_counter() - started
    finally:
        for handle in handles:
            handle.close()

    summary = {
        "status": response.status_code,
        "elapsedSeconds": round(elapsed, 3),
        "contentType": response.headers.get("content-type"),
        "bytes": len(response.content),
        "metrics": response.headers.get("X-NailMind-Tryon-Metrics"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    response.raise_for_status()
    if not summary["contentType"] or not str(summary["contentType"]).startswith("image/"):
        raise RuntimeError("inference response is not an image")
    Path(args.output).write_bytes(response.content)


if __name__ == "__main__":
    main()
