from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'nailmind.db'}")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.domain import DEFAULT_TREND_TOPICS, dumps_json  # noqa: E402
from app.models import TrendPost, TrendRecommendation, TrendTopic  # noqa: E402


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MockOpenClawAnalyzer:
    def summarize(self, title: str, summary: str, heat: float) -> tuple[str, str, float]:
        recommendation_type = "launch_candidate" if heat >= 85 else "boost_candidate" if heat >= 70 else "deprioritize_candidate"
        action = "建议运营审核后上架" if recommendation_type == "launch_candidate" else "建议加推" if recommendation_type == "boost_candidate" else "建议降权观察"
        confidence = round(min(heat / 100, 0.99), 2)
        return recommendation_type, action, confidence


def run(import_demo: bool = True) -> int:
    analyzer = MockOpenClawAnalyzer()
    created = 0
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for idx, topic_seed in enumerate(DEFAULT_TREND_TOPICS, start=1):
            existing = db.query(TrendTopic).filter(TrendTopic.topic_key == topic_seed.topic_key).first()
            if existing:
                continue
            topic = TrendTopic(
                topic_key=topic_seed.topic_key,
                platform="xiaohongshu",
                title=topic_seed.title,
                cluster_label=topic_seed.cluster_label,
                summary=topic_seed.summary,
                community_heat_score=topic_seed.community_heat_score,
                evidence_count=topic_seed.evidence_count,
                last_seen_at=utcnow(),
            )
            db.add(topic)
            db.flush()
            db.add(
                TrendPost(
                    topic_id=topic.id,
                    post_id=f"agent-{idx:04d}",
                    url=f"https://www.xiaohongshu.com/explore/{topic_seed.topic_key}",
                    title=topic_seed.title,
                    author="mock-openclaw",
                    like_count=int(topic_seed.community_heat_score * 11),
                    collect_count=int(topic_seed.community_heat_score * 7),
                    comment_count=int(topic_seed.community_heat_score * 3),
                    extracted_tags_json=dumps_json([topic_seed.cluster_label, "agent"]),
                )
            )
            recommendation_type, action_text, confidence = analyzer.summarize(topic_seed.title, topic_seed.summary, topic_seed.community_heat_score)
            db.add(
                TrendRecommendation(
                    recommendation_code=f"rec-agent-{idx:04d}",
                    recommendation_type=recommendation_type,
                    target_style_code=topic_seed.target_style_code,
                    candidate_name=topic_seed.candidate_name or topic_seed.title,
                    trigger_reason=topic_seed.summary,
                    community_evidence=f"独立 trend-agent 从小红书主题 {topic_seed.title} 生成。",
                    in_app_evidence="待后台结合站内数据复核。",
                    confidence_score=confidence,
                    action_text=action_text,
                    prerequisites="人工审核后执行。",
                    candidate_payload_json=None,
                    status="pending",
                )
            )
            created += 1
        db.commit()
    return created


if __name__ == "__main__":
    import_demo = os.getenv("TREND_AGENT_IMPORT_DEMO", "true").lower() == "true"
    created = run(import_demo=import_demo)
    print(f"trend-agent created {created} topic(s)")
