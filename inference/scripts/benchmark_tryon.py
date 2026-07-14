from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import requests


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark NailMind inference /v1/tryon/edit.")
    parser.add_argument("--url", default="http://127.0.0.1:8090/v1/tryon/edit")
    parser.add_argument("--hand", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--token", default="")
    parser.add_argument("--output-dir", default="benchmark-results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    durations: list[float] = []

    for run_index in range(args.runs):
        started = time.perf_counter()
        with Path(args.hand).open("rb") as hand_file, Path(args.style).open("rb") as style_file:
            response = requests.post(
                args.url,
                headers=headers,
                data={"response_format": "png"},
                files={
                    "hand_image": (Path(args.hand).name, hand_file, "application/octet-stream"),
                    "style_image": (Path(args.style).name, style_file, "application/octet-stream"),
                },
                timeout=120,
            )
        elapsed = time.perf_counter() - started
        response.raise_for_status()
        result_path = output_dir / f"tryon-{run_index + 1:02d}.png"
        result_path.write_bytes(response.content)
        durations.append(elapsed)
        print(f"run={run_index + 1} duration={elapsed:.2f}s output={result_path}")

    print(
        "summary "
        f"runs={len(durations)} "
        f"mean={statistics.mean(durations):.2f}s "
        f"p50={percentile(durations, 0.50):.2f}s "
        f"p90={percentile(durations, 0.90):.2f}s "
        f"p99={percentile(durations, 0.99):.2f}s"
    )


if __name__ == "__main__":
    main()
