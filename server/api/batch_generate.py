from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal  # noqa: E402
from app.main import fetch_binary_source, settings, tryon_result_url  # noqa: E402
from app.models import HandImage, NailStyleAsset, TryOnRecord  # noqa: E402
from app.services import generate_tryon_image, tryon_engine  # noqa: E402


def hand_range_filter(value: int, spec: str) -> bool:
    if not spec:
        return True
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return int(lo) <= value <= int(hi)
    return value == int(spec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch generate try-on result images")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--hands", type=str, default="")
    parser.add_argument("--styles", type=str, default="")
    args = parser.parse_args()

    with SessionLocal() as db:
        hands = db.query(HandImage).order_by(HandImage.id.asc()).all()
        styles = db.query(NailStyleAsset).order_by(NailStyleAsset.sequence_no.asc()).all()

        pairs = []
        for hand in hands:
            hand_no = int(hand.hand_code.split("_")[-1]) if "_" in hand.hand_code else hand.id
            if not hand_range_filter(hand_no, args.hands):
                continue
            for style in styles:
                if not hand_range_filter(style.sequence_no, args.styles):
                    continue
                pairs.append((hand, style))

        pending = []
        for hand, style in pairs:
            filename = f"{hand.hand_code}+style_{style.sequence_no:02d}+natural_short+squoval.png"
            path = settings.results_dir / filename
            if path.exists() and path.stat().st_size > 1000:
                continue
            pending.append((hand, style))

        if args.check:
            print(f"existing={len(pairs) - len(pending)} pending={len(pending)} total={len(pairs)}")
            return

        if args.sample > 0:
            pending = pending[: args.sample]

        success = 0
        for hand, style in pending:
            filename = f"{hand.hand_code}+style_{style.sequence_no:02d}+natural_short+squoval.png"
            path = settings.results_dir / filename
            success_live, _ = (False, "")
            if hand.local_path and style.local_image_path:
                success_live, _ = generate_tryon_image(hand.local_path, style.local_image_path, str(path))
            if not success_live:
                result = tryon_engine.process_tryon(
                    fetch_binary_source(hand.local_path or hand.image_url),
                    fetch_binary_source(style.local_image_path or style.enhanced_url or style.original_url or ""),
                    "natural_short",
                    "squoval",
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(result)
            db.add(
                TryOnRecord(
                    user_id=None,
                    hand_image_id=hand.id,
                    nail_style_asset_id=style.id,
                    result_url=tryon_result_url(filename),
                    source="bailian-live" if success_live else "opencv",
                    duration_ms=0,
                )
            )
            success += 1
            print(f"generated {filename}")
        db.commit()
        print(f"generated {success}/{len(pending)}")


if __name__ == "__main__":
    main()
