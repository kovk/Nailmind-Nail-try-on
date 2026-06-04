from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="merchant")
    stores: Mapped[list["Store"]] = relationship(back_populates="merchant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="customer", index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    managed_store_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    preferences: Mapped[str] = mapped_column(Text, default="显白法式,新中式,短甲友好")
    style_preferences: Mapped[str] = mapped_column(Text, default="显白、法式、新中式")
    notifications: Mapped[str] = mapped_column(Text, default="试戴完成、预约提醒、活动通知")
    privacy: Mapped[str] = mapped_column(Text, default="手部照片仅用于试戴与订单关联")
    last_upload_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    merchant: Mapped[Merchant | None] = relationship(back_populates="users")
    favorites: Mapped[list["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    try_on_jobs: Mapped[list["TryOnJob"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    lifecycle_requests: Mapped[list["StyleLifecycleRequest"]] = relationship(back_populates="requested_by_user")


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    vibe: Mapped[str] = mapped_column(String(255))
    price: Mapped[str] = mapped_column(String(50))
    nail_type: Mapped[str] = mapped_column(String(100))
    skin_tone: Mapped[str] = mapped_column(String(100))
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    colors_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    distance: Mapped[str] = mapped_column(String(50))
    price_band: Mapped[str] = mapped_column(String(50))
    score: Mapped[str] = mapped_column(String(20))
    slots_json: Mapped[str] = mapped_column(Text, default="[]")
    open_hours: Mapped[str] = mapped_column(String(100))
    artists: Mapped[int] = mapped_column(Integer, default=0)
    works: Mapped[str] = mapped_column(String(50), default="0")
    is_accepting_bookings: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    merchant: Mapped[Merchant | None] = relationship(back_populates="stores")


class StoreStyleListing(Base):
    __tablename__ = "store_style_listings"
    __table_args__ = (UniqueConstraint("store_code", "style_code", name="uq_store_style_listing"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_code: Mapped[str] = mapped_column(String(100), index=True)
    style_code: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[str] = mapped_column(String(50))
    inventory_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "style_id", name="uq_favorite_user_style"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    style_id: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="favorites")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_confirmation")
    store_id: Mapped[str] = mapped_column(String(100), index=True)
    store_name: Mapped[str] = mapped_column(String(255))
    style_id: Mapped[str] = mapped_column(String(100), index=True)
    style_name: Mapped[str] = mapped_column(String(255))
    slot: Mapped[str] = mapped_column(String(255))
    price: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="bookings")


class TryOnJob(Base):
    __tablename__ = "try_on_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    style_id: Mapped[str] = mapped_column(String(100), index=True)
    style_name: Mapped[str] = mapped_column(String(255))
    source_image_key: Mapped[str] = mapped_column(String(512))
    result_image_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(100), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=5)
    selected_length: Mapped[str] = mapped_column(String(100), default="natural_short")
    selected_shape: Mapped[str] = mapped_column(String(100), default="squoval")
    detected_traits: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by_worker: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="try_on_jobs")


class StyleLifecycleRequest(Base):
    __tablename__ = "style_lifecycle_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    store_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    style_code: Mapped[str] = mapped_column(String(100), index=True)
    requested_action: Mapped[str] = mapped_column(String(50), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requested_by_user: Mapped[User] = relationship(back_populates="lifecycle_requests")


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_name: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    style_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    store_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_page: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TrendTopic(Base):
    __tablename__ = "trend_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="xiaohongshu", index=True)
    title: Mapped[str] = mapped_column(String(255))
    cluster_label: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text, default="")
    community_heat_score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    posts: Mapped[list["TrendPost"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TrendPost(Base):
    __tablename__ = "trend_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("trend_topics.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String(255))
    author: Mapped[str] = mapped_column(String(255))
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    collect_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    extracted_tags_json: Mapped[str] = mapped_column(Text, default="[]")

    topic: Mapped[TrendTopic] = relationship(back_populates="posts")


class TrendRecommendation(Base):
    __tablename__ = "trend_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), index=True)
    target_style_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    target_store_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_reason: Mapped[str] = mapped_column(Text, default="")
    community_evidence: Mapped[str] = mapped_column(Text, default="")
    in_app_evidence: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    action_text: Mapped[str] = mapped_column(Text, default="")
    prerequisites: Mapped[str] = mapped_column(Text, default="")
    candidate_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StyleMetricsDaily(Base):
    __tablename__ = "style_metrics_daily"
    __table_args__ = (UniqueConstraint("style_id", "metric_date", name="uq_style_metrics_daily"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    style_id: Mapped[str] = mapped_column(String(100), index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    favorites: Mapped[int] = mapped_column(Integer, default=0)
    tryon_starts: Mapped[int] = mapped_column(Integer, default=0)
    tryon_completes: Mapped[int] = mapped_column(Integer, default=0)
    booking_creates: Mapped[int] = mapped_column(Integer, default=0)
    booking_confirms: Mapped[int] = mapped_column(Integer, default=0)
    community_heat_score: Mapped[float] = mapped_column(Float, default=0.0)
    in_app_interest_score: Mapped[float] = mapped_column(Float, default=0.0)
    composite_recommendation_score: Mapped[float] = mapped_column(Float, default=0.0)
    health_label: Mapped[str] = mapped_column(String(50), default="insufficient_data")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
