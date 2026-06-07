from __future__ import annotations

import sqlite3
from pathlib import Path


BAD_CODES = {"rec-0001", "rec-0002", "rec-0003", "rec-0004", "rec-0005"}
BAD_PHRASES = ("当前笔记暂时无法浏览",)


def main() -> None:
    db_path = Path("/opt/nailmind/data/nailmind.db")
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM trend_recommendations
            WHERE recommendation_code IN (?, ?, ?, ?, ?)
               OR candidate_name LIKE ?
               OR trigger_reason LIKE ?
               OR community_evidence LIKE ?
            """,
            (
                *sorted(BAD_CODES),
                f"%{BAD_PHRASES[0]}%",
                f"%{BAD_PHRASES[0]}%",
                f"%{BAD_PHRASES[0]}%",
            ),
        )
        deleted = cur.rowcount
        conn.commit()
        print(f"deleted={deleted}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
