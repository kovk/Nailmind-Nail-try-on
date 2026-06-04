from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .config import get_settings


@dataclass(frozen=True)
class SeedStyle:
    code: str
    name: str
    vibe: str
    price: str
    nail_type: str
    skin_tone: str
    tags: list[str]
    colors: list[str]
    status: str = "active"


@dataclass(frozen=True)
class SeedStore:
    code: str
    merchant_code: str
    name: str
    distance: str
    price_band: str
    score: str
    slots: list[str]
    open_hours: str
    artists: int
    works: str


@dataclass(frozen=True)
class SeedTrendTopic:
    topic_key: str
    title: str
    cluster_label: str
    summary: str
    community_heat_score: float
    evidence_count: int
    target_style_code: str | None
    recommendation_type: str
    candidate_name: str | None = None


HOT_KEYWORDS = ["法式", "显白", "新中式", "短甲", "猫眼"]

DEFAULT_STYLES: list[SeedStyle] = [
    SeedStyle("rose-mist", "玫雾法式", "显白, 通勤, 细闪", "￥228", "方圆甲", "黄一白到自然肤色", ["推荐", "显白", "法式"], ["#F8C7D6", "#FFEEF4", "#9B6474"]),
    SeedStyle("tea-amber", "茶珀猫眼", "温柔, 气质, 轻奢", "￥268", "杏仁甲", "自然肤色到暖肤", ["热门", "猫眼", "秋冬"], ["#DFA36E", "#7F4C2E", "#FFE2C3"]),
    SeedStyle("jade-ink", "青玉新中式", "新中式, 高级, 清透", "￥288", "椭圆甲", "冷白皮到自然肤色", ["新中式", "收藏高", "节日"], ["#5F8A81", "#DCEFE7", "#1F403A"]),
]

DEFAULT_STORES: list[SeedStore] = [
    SeedStore("s1", "nailmind-direct", "Nail Mind 静安店", "1.2km", "￥198-￥398", "4.9", ["今天 19:00", "明天 11:30", "明天 14:00"], "10:00 - 22:00", 6, "480+"),
    SeedStore("s2", "nailmind-direct", "Nail Mind 徐汇店", "2.7km", "￥228-￥468", "4.8", ["今天 20:00", "明天 10:00", "明天 16:30"], "10:00 - 22:00", 5, "360+"),
    SeedStore("s3", "nailmind-direct", "Nail Mind 浦东店", "4.3km", "￥188-￥328", "4.7", ["明天 09:30", "明天 13:00", "周二 18:30"], "10:00 - 21:30", 4, "250+"),
]

DEFAULT_TREND_TOPICS: list[SeedTrendTopic] = [
    SeedTrendTopic(
        "xh-rose-french",
        "通勤显白奶玫法式",
        "显白法式",
        "小红书近期通勤显白法式笔记互动显著上升，用户偏好低饱和奶玫底色加极细闪。",
        91.0,
        26,
        "rose-mist",
        "boost_candidate",
    ),
    SeedTrendTopic(
        "xh-jade-modern",
        "新中式青玉晕染",
        "新中式",
        "节气和婚礼场景带动新中式玉石纹样热度上升，收藏和咨询集中在高质感青绿色系。",
        86.0,
        19,
        "jade-ink",
        "launch_candidate",
    ),
    SeedTrendTopic(
        "xh-heavy-cat-eye",
        "重闪猫眼降温",
        "猫眼",
        "重闪高饱和猫眼内容仍有曝光，但转化讨论偏弱，用户更偏向轻奢低调款式。",
        57.0,
        11,
        "tea-amber",
        "deprioritize_candidate",
    ),
]


def dumps_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads_json(value: str | None, default):
    if not value:
        return default
    return json.loads(value)


def serialize_traits(value: dict | None) -> str | None:
    return dumps_json(value) if value else None


def deserialize_traits(value: str | None) -> dict | None:
    return loads_json(value, None)


def job_result_image_url(job_code: str) -> str:
    settings = get_settings()
    return f"{settings.public_base_url.rstrip('/')}/api/try-on/jobs/{job_code}/result-image"


def build_style_code(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "style"
