from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1] / "api"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'nailmind.db'}")

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.domain import dumps_json, loads_json  # noqa: E402
from app.models import TrendRecommendation, TrendTopic  # noqa: E402
from app.services.trend_intel import OpenClawCliAnalyzer, build_candidate_payload  # noqa: E402


DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
LOG_DIR = DATA_DIR / "logs"
TREND_AGENT_ALLOW_RULE_FALLBACK = os.getenv("TREND_AGENT_ALLOW_RULE_FALLBACK", "false").lower() == "true"


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nailmind.trend-agent")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(message)s")

    file_handler = TimedRotatingFileHandler(LOG_DIR / "trend-agent.log", when="midnight", backupCount=14, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


LOGGER = setup_logger()
def log_event(event: str, **fields: Any) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def heuristic_summary(title: str, summary: str, heat: float) -> dict[str, Any]:
    recommendation_type = "launch_candidate" if heat >= 85 else "boost_candidate" if heat >= 70 else "deprioritize_candidate"
    action = "建议运营审核后上新" if recommendation_type == "launch_candidate" else "建议排进首页加推位" if recommendation_type == "boost_candidate" else "建议继续观察，不立即投入资源"
    confidence = round(min(max(heat / 100, 0.35), 0.99), 2)
    return {
        "recommendation_type": recommendation_type,
        "candidate_name": title,
        "trigger_reason": summary,
        "community_evidence": f"社区热度 {heat:.1f}，讨论集中在 {title} 相关风格。",
        "in_app_evidence": "待与站内点击、收藏、试戴和预约数据合并复核。",
        "confidence_score": confidence,
        "action_text": action,
        "prerequisites": "确认门店技师可做、材料充足、定价带合理后执行。",
    }


def extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts = [extract_text(item) for item in payload]
        return "\n".join(part for part in parts if part)
    if isinstance(payload, dict):
        for key in ("output_text", "text", "response", "content", "message"):
            if key in payload:
                return extract_text(payload[key])
        if "outputs" in payload:
            return extract_text(payload["outputs"])
        if "output" in payload:
            return extract_text(payload["output"])
        if "choices" in payload and payload["choices"]:
            return extract_text(payload["choices"][0])
    return ""


def extract_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in model output")
    return json.loads(text[start : end + 1])


def build_recommendations() -> int:
    analyzer = OpenClawCliAnalyzer()
    Base.metadata.create_all(bind=engine)
    created = 0
    with SessionLocal() as db:
        db.commit()

        topics = db.query(TrendTopic).order_by(TrendTopic.community_heat_score.desc()).all()
        for topic in topics:
            existing = db.query(TrendRecommendation).filter(TrendRecommendation.trigger_reason == topic.summary).first()
            if existing:
                continue
            posts = []
            for post in topic.posts[:5]:
                meta = loads_json(post.extracted_tags_json, {})
                posts.append(
                    {
                        "postId": post.post_id,
                        "url": post.url,
                        "title": post.title,
                        "author": post.author,
                        "imageUrl": meta.get("imageUrl") if isinstance(meta, dict) else None,
                        "tags": meta.get("tags", []) if isinstance(meta, dict) else [],
                        "likeCount": post.like_count,
                        "collectCount": post.collect_count,
                        "commentCount": post.comment_count,
                    }
                )
            try:
                summary = analyzer.summarize(
                    title=topic.title,
                    cluster_label=topic.cluster_label,
                    summary=topic.summary,
                    heat=topic.community_heat_score,
                    evidence_count=topic.evidence_count,
                    posts=posts,
                )
            except Exception as exc:
                log_event("openclaw_cli_failed", topicKey=topic.topic_key, error=str(exc))
                if not TREND_AGENT_ALLOW_RULE_FALLBACK:
                    continue
                summary = heuristic_summary(topic.title, topic.summary, topic.community_heat_score)
                summary["candidate_payload"] = build_candidate_payload(topic.title, topic.cluster_label, topic.summary, posts)

            db.add(
                TrendRecommendation(
                    recommendation_code=f"rec-cli-{topic.id:04d}",
                    recommendation_type=summary["recommendation_type"],
                    target_style_code=None,
                    candidate_name=summary["candidate_name"],
                    trigger_reason=summary["trigger_reason"],
                    community_evidence=summary["community_evidence"],
                    in_app_evidence=summary["in_app_evidence"],
                    confidence_score=summary["confidence_score"],
                    action_text=summary["action_text"],
                    prerequisites=summary["prerequisites"],
                    candidate_payload_json=dumps_json(summary.get("candidate_payload")),
                    status="pending",
                )
            )
            created += 1
        db.commit()
    return created


if __name__ == "__main__":
    created = build_recommendations()
    log_event("trend_agent_completed", created=created)
    print(f"trend-agent created {created} recommendation(s)")
