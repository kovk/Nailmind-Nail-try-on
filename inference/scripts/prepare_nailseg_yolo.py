from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert binary nail masks to YOLO segmentation labels.")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("datasets/nail-seg-raw/NailSegmentationDatasetV2"),
        help="Raw dataset root with train/val/test images and masks folders.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("datasets/nail-yolo"),
        help="Output YOLO segmentation dataset root.",
    )
    parser.add_argument("--splits", nargs="+", default=["train", "val", "test"], help="Dataset splits to convert.")
    parser.add_argument("--min-area-px", type=int, default=80, help="Drop tiny mask components below this area.")
    parser.add_argument(
        "--approx-epsilon-ratio",
        type=float,
        default=0.004,
        help="Contour simplification ratio relative to contour perimeter.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Delete output directory before conversion.")
    return parser.parse_args()


def normalize_polygon(points: np.ndarray, width: int, height: int) -> list[float]:
    normalized: list[float] = []
    for x, y in points.reshape(-1, 2):
        normalized.append(float(np.clip(x / width, 0.0, 1.0)))
        normalized.append(float(np.clip(y / height, 0.0, 1.0)))
    return normalized


def mask_to_yolo_lines(mask_path: Path, *, min_area_px: int, approx_epsilon_ratio: float) -> list[str]:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"Cannot read mask: {mask_path}")

    height, width = mask.shape[:2]
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    lines: list[str] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area_px:
            continue
        epsilon = max(1.0, cv2.arcLength(contour, closed=True) * approx_epsilon_ratio)
        polygon = cv2.approxPolyDP(contour, epsilon, closed=True)
        if polygon.shape[0] < 3:
            continue
        coords = normalize_polygon(polygon, width, height)
        # Class 0 is nail. Keep six decimals to avoid bloated labels.
        line = "0 " + " ".join(f"{value:.6f}" for value in coords)
        lines.append(line)
    return lines


def convert_split(raw_root: Path, out_root: Path, split: str, *, min_area_px: int, approx_epsilon_ratio: float) -> tuple[int, int]:
    image_dir = raw_root / split / "images"
    mask_dir = raw_root / split / "masks"
    out_image_dir = out_root / "images" / split
    out_label_dir = out_root / "labels" / split
    out_image_dir.mkdir(parents=True, exist_ok=True)
    out_label_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    for image_path in sorted(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTS):
        mask_path = mask_dir / f"{image_path.stem}.png"
        if not mask_path.exists():
            skipped += 1
            continue
        lines = mask_to_yolo_lines(mask_path, min_area_px=min_area_px, approx_epsilon_ratio=approx_epsilon_ratio)
        if not lines:
            skipped += 1
            continue
        shutil.copy2(image_path, out_image_dir / image_path.name)
        (out_label_dir / f"{image_path.stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        converted += 1
    return converted, skipped


def write_data_yaml(out_root: Path) -> None:
    dataset_path = out_root.as_posix()
    (out_root / "data.yaml").write_text(
        "\n".join(
            [
                f"path: {dataset_path}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "",
                "names:",
                "  0: nail",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    if not args.raw_root.exists():
        raise SystemExit(f"Raw dataset root not found: {args.raw_root}")
    if args.out_root.exists() and args.overwrite:
        shutil.rmtree(args.out_root)
    args.out_root.mkdir(parents=True, exist_ok=True)

    for split in args.splits:
        converted, skipped = convert_split(
            args.raw_root,
            args.out_root,
            split,
            min_area_px=args.min_area_px,
            approx_epsilon_ratio=args.approx_epsilon_ratio,
        )
        print(f"{split}: converted={converted} skipped={skipped}")
    write_data_yaml(args.out_root)
    print(f"wrote {args.out_root / 'data.yaml'}")


if __name__ == "__main__":
    main()
