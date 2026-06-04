from __future__ import annotations

import shutil
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .domain import (
    DEFAULT_STORES,
    DEFAULT_STYLES,
    DEFAULT_TREND_TOPICS,
    HOT_KEYWORDS,
    build_style_code,
    deserialize_traits,
    dumps_json,
    job_result_image_url,
    loads_json,
    serialize_traits,
)
from .models import (
    Booking,
    EventLog,
    Favorite,
    Merchant,
    SessionToken,
    Store,
    StoreStyleListing,
    Style,
    StyleLifecycleRequest,
    StyleMetricsDaily,
    TrendPost,
    TrendRecommendation,
    TrendTopic,
    TryOnJob,
    User,
)
from .security import create_access_token, hash_password, safe_decode_access_token, verify_password


ROLE_CUSTOMER = "customer"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_MERCHANT_ADMIN = "merchant_admin"
ROLE_MERCHANT_STAFF = "merchant_staff"
ADMIN_ROLES = {ROLE_PLATFORM_ADMIN, ROLE_MERCHANT_ADMIN, ROLE_MERCHANT_STAFF}
STYLE_ACTIVE_STATUSES = {"active"}
DEFAULT_ADMIN_EMAIL = "operator@nailmind.app"
DEFAULT_MERCHANT_EMAIL = "merchant@nailmind.app"
DEFAULT_PASSWORD = "123456"

EVENT_TO_METRIC_FIELD = {
    "style_impression": "impressions",
    "style_click": "clicks",
    "style_favorite": "favorites",
    "tryon_start": "tryon_starts",
    "tryon_complete": "tryon_completes",
    "booking_create": "booking_creates",
    "booking_confirm": "booking_confirms",
}

ADMIN_WEB_DIR = Path(__file__).parent / "admin_web"

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.allowed_origins_list == ["*"] else settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if ADMIN_WEB_DIR.exists():
    app.mount("/admin/static", StaticFiles(directory=ADMIN_WEB_DIR), name="admin-static")


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class BookingRequest(BaseModel):
    storeId: str
    styleId: str
    slot: str
    name: str
    phone: str
    note: str = ""


class CreateTryOnJobRequest(BaseModel):
    styleId: str
    sourceImageKey: str | None = None
    selectedLength: str = "natural_short"
    selectedShape: str = "squoval"


class RerenderTryOnJobRequest(BaseModel):
    selectedLength: str | None = None
    selectedShape: str | None = None


class WorkerProgressRequest(BaseModel):
    stage: str
    progress: int


class WorkerCompleteRequest(BaseModel):
    resultImageKey: str
    detectedTraits: dict[str, str] | None = None


class WorkerFailRequest(BaseModel):
    errorCode: str
    errorMessage: str


class TrackEventRequest(BaseModel):
    eventName: str
    styleId: str | None = None
    storeId: str | None = None
    deviceId: str | None = None
    sourcePage: str | None = None
    sourceChannel: str | None = None
    sessionId: str | None = None
    payload: dict[str, Any] | None = None
    occurredAt: datetime | None = None


class AdminStyleCreateRequest(BaseModel):
    code: str | None = None
    name: str
    vibe: str
    price: str
    nailType: str
    skinTone: str
    tags: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    status: str = "draft"


class AdminStyleStatusRequest(BaseModel):
    status: str


class MerchantListingUpdateRequest(BaseModel):
    price: str | None = None
    inventoryCount: int | None = None
    status: str | None = None


class MerchantStoreUpdateRequest(BaseModel):
    slots: list[str] | None = None
    isAcceptingBookings: bool | None = None


class MerchantLifecycleRequestCreate(BaseModel):
    styleId: str
    requestedAction: str
    reason: str = ""
    storeId: str | None = None


class ReviewRequest(BaseModel):
    reviewNote: str = ""


class TrendImportRequest(BaseModel):
    title: str
    clusterLabel: str
    summary: str
    communityHeatScore: float
    targetStyleId: str | None = None
    recommendationType: str
    candidateName: str | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_directories() -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)


def next_numeric_code(prefix: str, latest_id: int | None) -> str:
    next_id = 1 if latest_id is None else latest_id + 1
    return f"{prefix}-{next_id:04d}"


def parse_prefixed_id(value: str, prefix: str) -> int:
    if not value.startswith(prefix):
        raise HTTPException(status_code=404, detail="resource not found")
    try:
        return int(value.removeprefix(prefix))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="resource not found") from exc


def user_response(user: User) -> dict[str, Any]:
    return {
        "name": user.name,
        "email": user.email,
        "preferences": [item for item in user.preferences.split(",") if item],
        "role": user.role,
        "merchantId": user.merchant.code if user.merchant else None,
        "managedStoreId": user.managed_store_code,
    }


def style_to_dict(style: Style) -> dict[str, Any]:
    return {
        "id": style.code,
        "name": style.name,
        "vibe": style.vibe,
        "price": style.price,
        "nailType": style.nail_type,
        "skinTone": style.skin_tone,
        "tags": loads_json(style.tags_json, []),
        "colors": loads_json(style.colors_json, []),
        "status": style.status,
    }


def store_to_dict(store: Store) -> dict[str, Any]:
    return {
        "id": store.code,
        "name": store.name,
        "distance": store.distance,
        "priceBand": store.price_band,
        "score": store.score,
        "slots": loads_json(store.slots_json, []),
        "openHours": store.open_hours,
        "artists": store.artists,
        "works": store.works,
        "isAcceptingBookings": store.is_accepting_bookings,
        "merchantId": store.merchant.code if store.merchant else None,
    }


def listing_to_dict(listing: StoreStyleListing) -> dict[str, Any]:
    return {
        "id": listing.id,
        "storeId": listing.store_code,
        "styleId": listing.style_code,
        "price": listing.price,
        "inventoryCount": listing.inventory_count,
        "status": listing.status,
        "publishedAt": listing.published_at.isoformat() if listing.published_at else None,
    }


def recommendation_to_dict(rec: TrendRecommendation) -> dict[str, Any]:
    return {
        "id": rec.recommendation_code,
        "type": rec.recommendation_type,
        "targetStyleId": rec.target_style_code,
        "targetStoreId": rec.target_store_code,
        "candidateName": rec.candidate_name,
        "triggerReason": rec.trigger_reason,
        "communityEvidence": rec.community_evidence,
        "inAppEvidence": rec.in_app_evidence,
        "confidenceScore": rec.confidence_score,
        "actionText": rec.action_text,
        "prerequisites": rec.prerequisites,
        "candidatePayload": loads_json(rec.candidate_payload_json, None),
        "status": rec.status,
        "createdAt": rec.created_at.isoformat(),
        "reviewedAt": rec.reviewed_at.isoformat() if rec.reviewed_at else None,
    }


def lifecycle_request_to_dict(req: StyleLifecycleRequest) -> dict[str, Any]:
    return {
        "id": req.request_code,
        "requestedByUserId": req.requested_by_user_id,
        "merchantId": req.merchant_id,
        "storeId": req.store_code,
        "styleId": req.style_code,
        "requestedAction": req.requested_action,
        "reason": req.reason,
        "status": req.status,
        "reviewNote": req.review_note,
        "reviewedByUserId": req.reviewed_by_user_id,
        "reviewedAt": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "createdAt": req.created_at.isoformat(),
    }


def booking_response(booking: Booking) -> dict[str, Any]:
    return {
        "id": f"booking-{booking.id:03d}",
        "status": booking.status,
        "storeId": booking.store_id,
        "storeName": booking.store_name,
        "styleId": booking.style_id,
        "styleName": booking.style_name,
        "slot": booking.slot,
        "price": booking.price,
        "name": booking.name,
        "phone": booking.phone,
        "note": booking.note,
        "createdAt": booking.created_at.isoformat(),
        "confirmedAt": booking.confirmed_at.isoformat() if booking.confirmed_at else None,
    }


def try_on_job_response(job: TryOnJob) -> dict[str, Any]:
    return {
        "id": job.job_code,
        "userId": f"user-{job.user_id:03d}",
        "styleId": job.style_id,
        "styleName": job.style_name,
        "sourceImageKey": job.source_image_key,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "selectedLength": job.selected_length,
        "selectedShape": job.selected_shape,
        "resultImageKey": job.result_image_key,
        "detectedTraits": deserialize_traits(job.detected_traits),
        "errorCode": job.error_code,
        "errorMessage": job.error_message,
        "createdAt": job.created_at.isoformat(),
        "updatedAt": job.updated_at.isoformat(),
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
    }


def create_session_for_user(db: Session, user: User) -> str:
    token = create_access_token(user.id, user.email)
    db.add(SessionToken(user_id=user.id, token=token))
    db.commit()
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = safe_decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    session_row = db.scalar(select(SessionToken).where(SessionToken.token == token))
    if not session_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin access required")
    return user


def require_platform_admin(user: User = Depends(get_admin_user)) -> User:
    if user.role != ROLE_PLATFORM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="platform admin access required")
    return user


def require_merchant_user(user: User = Depends(get_admin_user)) -> User:
    if user.role not in {ROLE_MERCHANT_ADMIN, ROLE_MERCHANT_STAFF}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="merchant access required")
    return user


def require_worker(
    x_worker_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    token = x_worker_token or ""
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if token != settings.worker_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid worker token")


def find_style(db: Session, style_code: str, include_inactive: bool = True) -> Style | None:
    stmt = select(Style).where(Style.code == style_code)
    if not include_inactive:
        stmt = stmt.where(Style.status.in_(tuple(STYLE_ACTIVE_STATUSES)))
    return db.scalar(stmt)


def find_store(db: Session, store_code: str) -> Store | None:
    return db.scalar(select(Store).where(Store.code == store_code))


def match_style(style: Style, query: str) -> bool:
    query = query.strip().lower()
    if not query:
        return True
    fields = [style.name, style.vibe, style.nail_type, style.skin_tone, *loads_json(style.tags_json, [])]
    return any(query in field.lower() for field in fields)


def next_job_code(db: Session) -> str:
    last = db.scalar(select(TryOnJob).order_by(TryOnJob.id.desc()))
    return next_numeric_code("tryon", last.id if last else None)


def next_request_code(db: Session) -> str:
    last = db.scalar(select(StyleLifecycleRequest).order_by(StyleLifecycleRequest.id.desc()))
    return next_numeric_code("req", last.id if last else None)


def next_recommendation_code(db: Session) -> str:
    last = db.scalar(select(TrendRecommendation).order_by(TrendRecommendation.id.desc()))
    return next_numeric_code("rec", last.id if last else None)


def compute_health_label(impressions: int, clicks: int, bookings: int) -> str:
    if impressions < 20 and clicks < 3:
        return "insufficient_distribution"
    ctr = clicks / impressions if impressions else 0
    if impressions >= 20 and ctr < 0.08:
        return "delist_candidate"
    if clicks >= 8 and bookings == 0:
        return "optimize_candidate"
    return "healthy"


def refresh_metric_scores(db: Session, row: StyleMetricsDaily) -> None:
    ctr = row.clicks / row.impressions if row.impressions else 0.0
    favorite_rate = row.favorites / row.clicks if row.clicks else 0.0
    tryon_rate = row.tryon_starts / row.clicks if row.clicks else 0.0
    booking_rate = row.booking_creates / row.clicks if row.clicks else 0.0
    community_heat_confidence = db.scalar(
        select(func.max(TrendRecommendation.confidence_score)).where(TrendRecommendation.target_style_code == row.style_id)
    )
    row.community_heat_score = round(float((community_heat_confidence or 0.0) * 100), 2)
    row.in_app_interest_score = round((ctr * 40 + favorite_rate * 20 + tryon_rate * 20 + booking_rate * 20) * 100, 2)
    row.composite_recommendation_score = round((row.community_heat_score * 0.55) + (row.in_app_interest_score * 0.45), 2)
    row.health_label = compute_health_label(row.impressions, row.clicks, row.booking_creates)
    row.updated_at = utcnow()


def upsert_style_metric(db: Session, style_code: str | None, event_name: str, occurred_at: datetime) -> None:
    if not style_code or event_name not in EVENT_TO_METRIC_FIELD:
        return
    metric_day = occurred_at.date()
    row = db.scalar(select(StyleMetricsDaily).where(StyleMetricsDaily.style_id == style_code, StyleMetricsDaily.metric_date == metric_day))
    if not row:
        row = StyleMetricsDaily(style_id=style_code, metric_date=metric_day)
        db.add(row)
        db.flush()
    field_name = EVENT_TO_METRIC_FIELD[event_name]
    setattr(row, field_name, getattr(row, field_name) + 1)
    refresh_metric_scores(db, row)


def log_event(
    db: Session,
    event_name: str,
    *,
    user_id: int | None = None,
    device_id: str | None = None,
    style_id: str | None = None,
    store_id: str | None = None,
    source_page: str | None = None,
    source_channel: str | None = None,
    session_id: str | None = None,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> str:
    event_time = occurred_at or utcnow()
    event_id = f"evt-{uuid.uuid4().hex[:20]}"
    db.add(
        EventLog(
            event_id=event_id,
            event_name=event_name,
            user_id=user_id,
            device_id=device_id,
            style_id=style_id,
            store_id=store_id,
            source_page=source_page,
            source_channel=source_channel,
            session_id=session_id,
            payload_json=dumps_json(payload) if payload else None,
            occurred_at=event_time,
        )
    )
    upsert_style_metric(db, style_id, event_name, event_time)
    return event_id


def log_impressions(db: Session, user: User | None, styles: list[Style], source_page: str) -> None:
    for style in styles:
        log_event(db, "style_impression", user_id=user.id if user else None, style_id=style.code, source_page=source_page)
    if styles:
        db.commit()


def latest_style_metrics(db: Session, style_code: str) -> StyleMetricsDaily | None:
    return db.scalar(
        select(StyleMetricsDaily)
        .where(StyleMetricsDaily.style_id == style_code)
        .order_by(StyleMetricsDaily.metric_date.desc())
    )


def aggregate_event_counts(db: Session, *, style_id: str | None = None, days: int = 7) -> dict[str, int]:
    since = utcnow() - timedelta(days=days)
    stmt = select(EventLog.event_name, func.count(EventLog.id)).where(EventLog.occurred_at >= since).group_by(EventLog.event_name)
    if style_id:
        stmt = stmt.where(EventLog.style_id == style_id)
    rows = db.execute(stmt).all()
    counts = {name: count for name, count in rows}
    for event_name in EVENT_TO_METRIC_FIELD:
        counts.setdefault(event_name, 0)
    return counts


def build_style_trend_summary(db: Session, style_code: str) -> dict[str, Any]:
    daily_rows = db.scalars(
        select(StyleMetricsDaily)
        .where(StyleMetricsDaily.style_id == style_code, StyleMetricsDaily.metric_date >= date.today() - timedelta(days=6))
        .order_by(StyleMetricsDaily.metric_date.asc())
    ).all()
    counts = aggregate_event_counts(db, style_id=style_code, days=7)
    impressions = counts["style_impression"]
    clicks = counts["style_click"]
    favorites = counts["style_favorite"]
    tryon_starts = counts["tryon_start"]
    tryon_completes = counts["tryon_complete"]
    booking_creates = counts["booking_create"]
    booking_confirms = counts["booking_confirm"]
    latest = latest_style_metrics(db, style_code)
    total_heat = latest.community_heat_score if latest else 0.0
    health_label = latest.health_label if latest else compute_health_label(impressions, clicks, booking_creates)
    return {
        "styleId": style_code,
        "funnel": {
            "impressions": impressions,
            "clicks": clicks,
            "favorites": favorites,
            "tryonStarts": tryon_starts,
            "tryonCompletes": tryon_completes,
            "bookingCreates": booking_creates,
            "bookingConfirms": booking_confirms,
            "clickThroughRate": round(clicks / impressions, 4) if impressions else 0.0,
            "favoriteRate": round(favorites / clicks, 4) if clicks else 0.0,
            "tryonStartRate": round(tryon_starts / clicks, 4) if clicks else 0.0,
            "tryonCompleteRate": round(tryon_completes / tryon_starts, 4) if tryon_starts else 0.0,
            "bookingConversionRate": round(booking_creates / clicks, 4) if clicks else 0.0,
            "dealConversionRate": round(booking_confirms / clicks, 4) if clicks else 0.0,
        },
        "scores": {
            "communityHeatScore": round(total_heat, 2),
            "inAppInterestScore": round(latest.in_app_interest_score if latest else 0.0, 2),
            "compositeRecommendationScore": round(latest.composite_recommendation_score if latest else 0.0, 2),
            "healthLabel": health_label,
        },
        "daily": [
            {
                "date": row.metric_date.isoformat(),
                "impressions": row.impressions,
                "clicks": row.clicks,
                "favorites": row.favorites,
                "tryonStarts": row.tryon_starts,
                "tryonCompletes": row.tryon_completes,
                "bookingCreates": row.booking_creates,
                "bookingConfirms": row.booking_confirms,
                "communityHeatScore": row.community_heat_score,
                "compositeRecommendationScore": row.composite_recommendation_score,
                "healthLabel": row.health_label,
            }
            for row in daily_rows
        ],
    }


def merchant_store_scope(user: User) -> list[str]:
    if user.role == ROLE_PLATFORM_ADMIN:
        return []
    if user.managed_store_code:
        return [user.managed_store_code]
    return []


def require_store_access(user: User, store_code: str) -> None:
    if user.role == ROLE_PLATFORM_ADMIN:
        return
    if user.managed_store_code != store_code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="store access denied")


def get_or_create_listing(db: Session, store_code: str, style_code: str, price: str) -> StoreStyleListing:
    listing = db.scalar(select(StoreStyleListing).where(StoreStyleListing.store_code == store_code, StoreStyleListing.style_code == style_code))
    if listing:
        return listing
    listing = StoreStyleListing(
        store_code=store_code,
        style_code=style_code,
        price=price,
        inventory_count=6,
        status="draft",
        updated_at=utcnow(),
    )
    db.add(listing)
    db.flush()
    return listing


def seed_demo_data(db: Session) -> None:
    merchant = db.scalar(select(Merchant).where(Merchant.code == "nailmind-direct"))
    if not merchant:
        merchant = Merchant(code="nailmind-direct", name="Nail Mind 自营")
        db.add(merchant)
        db.flush()

    for seed_style in DEFAULT_STYLES:
        style = db.scalar(select(Style).where(Style.code == seed_style.code))
        if not style:
            db.add(
                Style(
                    code=seed_style.code,
                    name=seed_style.name,
                    vibe=seed_style.vibe,
                    price=seed_style.price,
                    nail_type=seed_style.nail_type,
                    skin_tone=seed_style.skin_tone,
                    tags_json=dumps_json(seed_style.tags),
                    colors_json=dumps_json(seed_style.colors),
                    status=seed_style.status,
                    updated_at=utcnow(),
                )
            )
    db.flush()

    for seed_store in DEFAULT_STORES:
        store = db.scalar(select(Store).where(Store.code == seed_store.code))
        if not store:
            db.add(
                Store(
                    code=seed_store.code,
                    merchant_id=merchant.id,
                    name=seed_store.name,
                    distance=seed_store.distance,
                    price_band=seed_store.price_band,
                    score=seed_store.score,
                    slots_json=dumps_json(seed_store.slots),
                    open_hours=seed_store.open_hours,
                    artists=seed_store.artists,
                    works=seed_store.works,
                    is_accepting_bookings=True,
                    updated_at=utcnow(),
                )
            )
    db.flush()

    styles = db.scalars(select(Style)).all()
    stores = db.scalars(select(Store)).all()
    for store in stores:
        for style in styles:
            listing = db.scalar(select(StoreStyleListing).where(StoreStyleListing.store_code == store.code, StoreStyleListing.style_code == style.code))
            if not listing:
                db.add(
                    StoreStyleListing(
                        store_code=store.code,
                        style_code=style.code,
                        price=style.price,
                        inventory_count=8,
                        status="active",
                        published_at=utcnow(),
                        updated_at=utcnow(),
                    )
                )

    demo_user = db.scalar(select(User).where(User.email == settings.demo_email.lower()))
    if not demo_user:
        demo_user = User(
            email=settings.demo_email.lower(),
            password_hash=hash_password(settings.demo_password),
            name="Luna",
            role=ROLE_CUSTOMER,
            preferences="显白法式,新中式,短甲友好",
            style_preferences="显白、法式、新中式",
            notifications="试戴完成、预约提醒、活动通知",
            privacy="手部照片仅用于试戴与订单关联",
        )
        db.add(demo_user)
        db.flush()
        db.add_all([Favorite(user_id=demo_user.id, style_id="rose-mist"), Favorite(user_id=demo_user.id, style_id="jade-ink")])

    admin_user = db.scalar(select(User).where(User.email == DEFAULT_ADMIN_EMAIL))
    if not admin_user:
        db.add(
            User(
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_PASSWORD),
                name="运营管理员",
                role=ROLE_PLATFORM_ADMIN,
                preferences="运营,报表",
                style_preferences="运营优先",
                notifications="审核提醒,趋势提醒",
                privacy="仅用于后台演示",
            )
        )

    merchant_user = db.scalar(select(User).where(User.email == DEFAULT_MERCHANT_EMAIL))
    if not merchant_user:
        db.add(
            User(
                email=DEFAULT_MERCHANT_EMAIL,
                password_hash=hash_password(DEFAULT_PASSWORD),
                name="静安店店长",
                role=ROLE_MERCHANT_ADMIN,
                merchant_id=merchant.id,
                managed_store_code="s1",
                preferences="到店转化,档期利用",
                style_preferences="门店热销",
                notifications="订单提醒,审核提醒",
                privacy="仅用于后台演示",
            )
        )
    db.flush()

    if db.scalar(select(func.count(TrendTopic.id))) == 0:
        for idx, topic_seed in enumerate(DEFAULT_TREND_TOPICS, start=1):
            topic = TrendTopic(
                topic_key=topic_seed.topic_key,
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
                    post_id=f"{topic_seed.topic_key}-post",
                    url=f"https://www.xiaohongshu.com/explore/{topic_seed.topic_key}",
                    title=topic_seed.title,
                    author="trend-bot",
                    like_count=int(topic_seed.community_heat_score * 10),
                    collect_count=int(topic_seed.community_heat_score * 6),
                    comment_count=int(topic_seed.community_heat_score * 2),
                    extracted_tags_json=dumps_json(topic_seed.cluster_label.split()),
                )
            )
            candidate_payload = None
            if topic_seed.recommendation_type == "launch_candidate":
                style = db.scalar(select(Style).where(Style.code == topic_seed.target_style_code))
                if style:
                    candidate_payload = dumps_json(style_to_dict(style))
            db.add(
                TrendRecommendation(
                    recommendation_code=f"rec-{idx:04d}",
                    recommendation_type=topic_seed.recommendation_type,
                    target_style_code=topic_seed.target_style_code,
                    candidate_name=topic_seed.candidate_name or topic_seed.title,
                    trigger_reason=topic_seed.summary,
                    community_evidence=f"{topic_seed.evidence_count} 篇高互动小红书笔记集中讨论“{topic_seed.cluster_label}”。",
                    in_app_evidence="将结合站内点击、收藏、试戴和预约转化判断是否上架/加推。",
                    confidence_score=round(min(topic_seed.community_heat_score / 100, 0.99), 2),
                    action_text="提交给运营审核后再执行，不自动改商品状态。",
                    prerequisites="确认门店库存与技师可做能力后生效。",
                    candidate_payload_json=candidate_payload,
                    status="pending",
                )
            )

    if db.scalar(select(func.count(StyleMetricsDaily.id))) == 0:
        for idx, style in enumerate(db.scalars(select(Style).order_by(Style.code)).all(), start=1):
            row = StyleMetricsDaily(
                style_id=style.code,
                metric_date=date.today() - timedelta(days=1),
                impressions=20 * idx,
                clicks=6 * idx,
                favorites=2 * idx,
                tryon_starts=2 * idx,
                tryon_completes=max(idx, 1),
                booking_creates=max(idx - 1, 0),
                booking_confirms=max(idx - 2, 0),
                community_heat_score=70 + idx * 5,
            )
            refresh_metric_scores(db, row)
            db.add(row)

    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    ensure_directories()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/admin", response_class=HTMLResponse)
def admin_index() -> HTMLResponse:
    index_file = ADMIN_WEB_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body><h1>Nail Mind Admin</h1><p>admin web not found</p></body></html>")


@app.post("/api/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    if len(payload.password) < 6 or not payload.name.strip():
        raise HTTPException(status_code=400, detail="name, email and password(>=6) are required")
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        role=ROLE_CUSTOMER,
        preferences="显白,法式",
        style_preferences="显白、法式",
        notifications="试戴完成、预约提醒、活动通知",
        privacy="手部照片仅用于试戴与订单关联",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session_for_user(db, user)
    return {"token": token, "user": user_response(user)}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    token = create_session_for_user(db, user)
    return {"token": token, "user": user_response(user)}


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"user": user_response(user)}


@app.post("/api/auth/logout")
def logout(
    authorization: Annotated[str | None, Header()] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip()
    session_row = db.scalar(select(SessionToken).where(SessionToken.token == token, SessionToken.user_id == user.id))
    if session_row:
        db.delete(session_row)
        db.commit()
    return {"status": "logged_out"}


@app.get("/api/home")
def home(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(Style).where(Style.status.in_(tuple(STYLE_ACTIVE_STATUSES))).order_by(Style.code)).all()
    top_items = items[:3]
    log_impressions(db, user, top_items, "home")
    payload = [style_to_dict(style) for style in top_items]
    return {"hotKeywords": HOT_KEYWORDS, "recommended": payload, "hot": payload}


@app.get("/api/styles")
def styles(tag: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(Style).where(Style.status.in_(tuple(STYLE_ACTIVE_STATUSES))).order_by(Style.code)).all()
    if tag:
        items = [style for style in items if match_style(style, tag)]
    log_impressions(db, user, items, "styles")
    return {"items": [style_to_dict(style) for style in items]}


@app.get("/api/styles/search")
def style_search(q: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    query = q.strip() or HOT_KEYWORDS[0]
    items = db.scalars(select(Style).where(Style.status.in_(tuple(STYLE_ACTIVE_STATUSES))).order_by(Style.code)).all()
    result = [style for style in items if match_style(style, query)] or items
    log_event(db, "search_submit", user_id=user.id, source_page="styles_search", payload={"query": query, "resultCount": len(result)})
    db.commit()
    log_impressions(db, user, result, "styles_search")
    return {"query": query, "items": [style_to_dict(style) for style in result]}


@app.get("/api/styles/{style_id}")
def style_detail(style_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, style_id, include_inactive=False)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    favorited = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.style_id == style_id)) is not None
    log_event(db, "style_click", user_id=user.id, style_id=style_id, source_page="style_detail")
    db.commit()
    return {"style": style_to_dict(style), "userCases": "1.2k+", "canFavorite": True, "canTryOn": True, "favorited": favorited}


@app.get("/api/favorites")
def favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    favorite_ids = {row.style_id for row in db.scalars(select(Favorite).where(Favorite.user_id == user.id)).all()}
    items = db.scalars(select(Style).where(Style.code.in_(favorite_ids)).order_by(Style.code)).all() if favorite_ids else []
    return {"items": [style_to_dict(style) for style in items]}


@app.post("/api/favorites/{style_id}")
def add_favorite(style_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not find_style(db, style_id, include_inactive=False):
        raise HTTPException(status_code=404, detail="style not found")
    existing = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.style_id == style_id))
    if not existing:
        db.add(Favorite(user_id=user.id, style_id=style_id))
    log_event(db, "style_favorite", user_id=user.id, style_id=style_id, source_page="favorites")
    db.commit()
    return {"styleId": style_id, "favorited": True}


@app.delete("/api/favorites/{style_id}")
def remove_favorite(style_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    existing = db.scalar(select(Favorite).where(Favorite.user_id == user.id, Favorite.style_id == style_id))
    if existing:
        db.delete(existing)
        db.commit()
    return {"styleId": style_id, "favorited": False}


@app.post("/api/events")
def track_event(payload: TrackEventRequest, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    event_id = log_event(
        db,
        payload.eventName,
        user_id=user.id if user else None,
        device_id=payload.deviceId,
        style_id=payload.styleId,
        store_id=payload.storeId,
        source_page=payload.sourcePage,
        source_channel=payload.sourceChannel,
        session_id=payload.sessionId,
        payload=payload.payload,
        occurred_at=payload.occurredAt,
    )
    db.commit()
    return {"eventId": event_id}


@app.post("/api/try-on/uploads")
def tryon_upload(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    suffix = Path(file.filename or "upload.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="only .jpg, .jpeg and .png files are supported")
    object_key = f"user-{user.id:03d}/{int(utcnow().timestamp() * 1_000_000)}{suffix}"
    target = settings.uploads_dir / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    user.last_upload_key = object_key
    db.add(user)
    db.commit()
    return {"objectKey": object_key, "fileName": file.filename}


@app.get("/api/try-on/jobs")
def tryon_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    jobs = db.scalars(select(TryOnJob).where(TryOnJob.user_id == user.id).order_by(TryOnJob.created_at.desc())).all()
    return {"items": [try_on_job_response(job) for job in jobs]}


@app.post("/api/try-on/jobs")
def create_tryon_job(payload: CreateTryOnJobRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, payload.styleId, include_inactive=False)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    source_key = payload.sourceImageKey or user.last_upload_key
    if not source_key:
        raise HTTPException(status_code=400, detail="sourceImageKey is required")
    if not (settings.uploads_dir / source_key).exists():
        raise HTTPException(status_code=400, detail="source image not found")
    job = TryOnJob(
        job_code=next_job_code(db),
        user_id=user.id,
        style_id=style.code,
        style_name=style.name,
        source_image_key=source_key,
        status="queued",
        stage="queued",
        progress=5,
        selected_length=payload.selectedLength,
        selected_shape=payload.selectedShape,
        updated_at=utcnow(),
    )
    db.add(job)
    log_event(db, "tryon_start", user_id=user.id, style_id=style.code, source_page="tryon")
    db.commit()
    db.refresh(job)
    return try_on_job_response(job)


@app.get("/api/try-on/jobs/{job_code}")
def get_tryon_job(job_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code, TryOnJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    return try_on_job_response(job)


@app.get("/api/try-on/jobs/{job_code}/result")
def get_tryon_result(job_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code, TryOnJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    payload = try_on_job_response(job)
    if job.status == "completed":
        payload["resultImageUrl"] = job_result_image_url(job.job_code)
    return payload


@app.get("/api/try-on/jobs/{job_code}/result-image")
def get_tryon_result_image(job_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code, TryOnJob.user_id == user.id))
    if not job or not job.result_image_key:
        raise HTTPException(status_code=404, detail="result image not found")
    path = settings.results_dir / job.result_image_key
    if not path.exists():
        raise HTTPException(status_code=404, detail="result image not found")
    return FileResponse(path, media_type="image/png")


@app.post("/api/try-on/jobs/{job_code}/rerender")
def rerender_tryon_job(job_code: str, payload: RerenderTryOnJobRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code, TryOnJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    if payload.selectedLength:
        job.selected_length = payload.selectedLength
    if payload.selectedShape:
        job.selected_shape = payload.selectedShape
    job.status = "queued"
    job.stage = "queued"
    job.progress = 5
    job.error_code = None
    job.error_message = None
    job.completed_at = None
    job.updated_at = utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return try_on_job_response(job)


@app.get("/api/stores")
def stores(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    active_styles = {style.code for style in db.scalars(select(Style).where(Style.status.in_(tuple(STYLE_ACTIVE_STATUSES)))).all()}
    store_rows = db.scalars(select(Store).order_by(Store.code)).all()
    visible = []
    for store in store_rows:
        listing_count = db.scalar(
            select(func.count(StoreStyleListing.id)).where(
                StoreStyleListing.store_code == store.code,
                StoreStyleListing.style_code.in_(active_styles),
                StoreStyleListing.status == "active",
            )
        )
        if listing_count:
            visible.append(store)
    return {"items": [store_to_dict(store) for store in visible]}


@app.get("/api/stores/{store_id}")
def store_detail(store_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    store = find_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    return store_to_dict(store)


@app.get("/api/stores/{store_id}/slots")
def store_slots(store_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    store = find_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    return {"storeId": store.code, "slots": loads_json(store.slots_json, [])}


@app.get("/api/bookings")
def bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())).all()
    return {"items": [booking_response(booking) for booking in items]}


@app.post("/api/bookings")
def create_booking(payload: BookingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, payload.styleId, include_inactive=False)
    store = find_store(db, payload.storeId)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    slots = loads_json(store.slots_json, [])
    if payload.slot not in slots:
        raise HTTPException(status_code=400, detail="slot is not available for the selected store")
    listing = db.scalar(
        select(StoreStyleListing).where(
            StoreStyleListing.store_code == store.code,
            StoreStyleListing.style_code == style.code,
            StoreStyleListing.status == "active",
        )
    )
    if not listing or listing.inventory_count <= 0:
        raise HTTPException(status_code=400, detail="selected style is not available at this store")
    booking = Booking(
        user_id=user.id,
        status="pending_confirmation",
        store_id=store.code,
        store_name=store.name,
        style_id=style.code,
        style_name=style.name,
        slot=payload.slot,
        price=listing.price,
        name=payload.name,
        phone=payload.phone,
        note=payload.note,
    )
    db.add(booking)
    listing.inventory_count = max(listing.inventory_count - 1, 0)
    listing.updated_at = utcnow()
    log_event(db, "booking_create", user_id=user.id, style_id=style.code, store_id=store.code, source_page="booking")
    db.commit()
    db.refresh(booking)
    return booking_response(booking)


@app.get("/api/bookings/{booking_code}")
def get_booking(booking_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    booking_id = parse_prefixed_id(booking_code, "booking-")
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id))
    if not booking:
        raise HTTPException(status_code=404, detail="booking not found")
    return booking_response(booking)


@app.post("/api/bookings/{booking_code}/confirm")
def confirm_booking(booking_code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    booking_id = parse_prefixed_id(booking_code, "booking-")
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id))
    if not booking:
        raise HTTPException(status_code=404, detail="booking not found")
    booking.status = "confirmed"
    booking.confirmed_at = utcnow()
    db.add(booking)
    log_event(db, "booking_confirm", user_id=user.id, style_id=booking.style_id, store_id=booking.store_id, source_page="booking_detail")
    db.commit()
    db.refresh(booking)
    return booking_response(booking)


@app.get("/api/profile")
def profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    favorites_count = db.query(Favorite).filter(Favorite.user_id == user.id).count()
    booking_count = db.query(Booking).filter(Booking.user_id == user.id).count()
    tryon_count = db.query(TryOnJob).filter(TryOnJob.user_id == user.id).count()
    return {"profile": user_response(user), "favoritesCount": favorites_count, "bookingCount": booking_count, "tryOnCount": tryon_count}


@app.get("/api/settings")
def user_settings(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "stylePreferences": user.style_preferences,
        "notifications": user.notifications,
        "privacy": user.privacy,
    }


@app.post("/admin/auth/login")
def admin_login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash) or user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=401, detail="invalid admin credentials")
    token = create_session_for_user(db, user)
    return {"token": token, "user": user_response(user)}


@app.get("/admin/auth/me")
def admin_me(user: User = Depends(get_admin_user)) -> dict[str, Any]:
    return {"user": user_response(user)}


@app.post("/admin/auth/logout")
def admin_logout(
    authorization: Annotated[str | None, Header()] = None,
    user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = authorization.removeprefix("Bearer ").strip()
    session_row = db.scalar(select(SessionToken).where(SessionToken.token == token, SessionToken.user_id == user.id))
    if session_row:
        db.delete(session_row)
        db.commit()
    return {"status": "logged_out"}


@app.get("/admin/styles")
def admin_styles(user: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(Style).order_by(Style.code)).all()
    return {"items": [style_to_dict(style) for style in items], "role": user.role}


@app.post("/admin/styles")
def admin_create_style(payload: AdminStyleCreateRequest, _: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    code = payload.code or build_style_code(payload.name)
    if find_style(db, code):
        raise HTTPException(status_code=409, detail="style code already exists")
    style = Style(
        code=code,
        name=payload.name,
        vibe=payload.vibe,
        price=payload.price,
        nail_type=payload.nailType,
        skin_tone=payload.skinTone,
        tags_json=dumps_json(payload.tags),
        colors_json=dumps_json(payload.colors),
        status=payload.status,
        updated_at=utcnow(),
    )
    db.add(style)
    db.commit()
    db.refresh(style)
    return {"style": style_to_dict(style)}


@app.get("/admin/styles/{style_id}")
def admin_style_detail(style_id: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    listings = db.scalars(select(StoreStyleListing).where(StoreStyleListing.style_code == style_id).order_by(StoreStyleListing.store_code)).all()
    return {
        "style": style_to_dict(style),
        "listings": [listing_to_dict(item) for item in listings],
        "analytics": build_style_trend_summary(db, style_id),
    }


@app.post("/admin/styles/{style_id}/status")
def admin_update_style_status(style_id: str, payload: AdminStyleStatusRequest, _: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    style.status = payload.status
    style.updated_at = utcnow()
    db.add(style)
    db.commit()
    return {"style": style_to_dict(style)}


@app.get("/admin/stores")
def admin_stores(_: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(Store).order_by(Store.code)).all()
    payload = []
    for store in items:
        listings = db.query(StoreStyleListing).filter(StoreStyleListing.store_code == store.code).count()
        pending = db.query(StyleLifecycleRequest).filter(StyleLifecycleRequest.store_code == store.code, StyleLifecycleRequest.status == "pending").count()
        store_payload = store_to_dict(store)
        store_payload["listingCount"] = listings
        store_payload["pendingRequestCount"] = pending
        payload.append(store_payload)
    return {"items": payload}


@app.get("/admin/stores/{store_id}")
def admin_store_detail(store_id: str, user: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_store_access(user, store_id)
    store = find_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    listings = db.scalars(select(StoreStyleListing).where(StoreStyleListing.store_code == store_id).order_by(StoreStyleListing.style_code)).all()
    bookings = db.scalars(select(Booking).where(Booking.store_id == store_id).order_by(Booking.created_at.desc()).limit(10)).all()
    return {
        "store": store_to_dict(store),
        "listings": [listing_to_dict(item) for item in listings],
        "recentBookings": [booking_response(item) for item in bookings],
    }


@app.get("/admin/requests")
def admin_requests(user: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    stmt = select(StyleLifecycleRequest).order_by(StyleLifecycleRequest.created_at.desc())
    if user.role in {ROLE_MERCHANT_ADMIN, ROLE_MERCHANT_STAFF} and user.managed_store_code:
        stmt = stmt.where(StyleLifecycleRequest.store_code == user.managed_store_code)
    items = db.scalars(stmt).all()
    return {"items": [lifecycle_request_to_dict(item) for item in items]}


def apply_lifecycle_request(db: Session, req: StyleLifecycleRequest) -> None:
    style = find_style(db, req.style_code)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    listing = None
    if req.store_code:
        store = find_store(db, req.store_code)
        if not store:
            raise HTTPException(status_code=404, detail="store not found")
        listing = get_or_create_listing(db, req.store_code, req.style_code, style.price)
    if req.requested_action == "launch":
        style.status = "active"
        if listing:
            listing.status = "active"
            listing.published_at = listing.published_at or utcnow()
    elif req.requested_action == "delist":
        if listing:
            listing.status = "inactive"
        else:
            style.status = "inactive"
    else:
        raise HTTPException(status_code=400, detail="unsupported request action")
    style.updated_at = utcnow()


@app.post("/admin/requests/{request_id}/approve")
def approve_request(request_id: str, payload: ReviewRequest, user: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    req = db.scalar(select(StyleLifecycleRequest).where(StyleLifecycleRequest.request_code == request_id))
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    apply_lifecycle_request(db, req)
    req.status = "approved"
    req.review_note = payload.reviewNote
    req.reviewed_by_user_id = user.id
    req.reviewed_at = utcnow()
    db.add(req)
    db.commit()
    return {"request": lifecycle_request_to_dict(req)}


@app.post("/admin/requests/{request_id}/reject")
def reject_request(request_id: str, payload: ReviewRequest, user: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    req = db.scalar(select(StyleLifecycleRequest).where(StyleLifecycleRequest.request_code == request_id))
    if not req:
        raise HTTPException(status_code=404, detail="request not found")
    req.status = "rejected"
    req.review_note = payload.reviewNote
    req.reviewed_by_user_id = user.id
    req.reviewed_at = utcnow()
    db.add(req)
    db.commit()
    return {"request": lifecycle_request_to_dict(req)}


@app.get("/admin/analytics/overview")
def admin_analytics_overview(_: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    counts = aggregate_event_counts(db, days=7)
    style_rows = db.scalars(select(Style).order_by(Style.code)).all()
    style_snapshots = []
    for style in style_rows:
        summary = build_style_trend_summary(db, style.code)
        style_snapshots.append(
            {
                "styleId": style.code,
                "styleName": style.name,
                "healthLabel": summary["scores"]["healthLabel"],
                "compositeRecommendationScore": summary["scores"]["compositeRecommendationScore"],
                "impressions": summary["funnel"]["impressions"],
                "clicks": summary["funnel"]["clicks"],
            }
        )
    return {
        "windowDays": 7,
        "funnel": {
            "impressions": counts["style_impression"],
            "clicks": counts["style_click"],
            "favorites": counts["style_favorite"],
            "tryonStarts": counts["tryon_start"],
            "tryonCompletes": counts["tryon_complete"],
            "bookingCreates": counts["booking_create"],
            "bookingConfirms": counts["booking_confirm"],
        },
        "rates": {
            "clickThroughRate": round(counts["style_click"] / counts["style_impression"], 4) if counts["style_impression"] else 0.0,
            "favoriteRate": round(counts["style_favorite"] / counts["style_click"], 4) if counts["style_click"] else 0.0,
            "tryonStartRate": round(counts["tryon_start"] / counts["style_click"], 4) if counts["style_click"] else 0.0,
            "tryonCompleteRate": round(counts["tryon_complete"] / counts["tryon_start"], 4) if counts["tryon_start"] else 0.0,
            "bookingConversionRate": round(counts["booking_create"] / counts["style_click"], 4) if counts["style_click"] else 0.0,
            "dealConversionRate": round(counts["booking_confirm"] / counts["style_click"], 4) if counts["style_click"] else 0.0,
        },
        "styleSnapshots": style_snapshots,
    }


@app.get("/admin/analytics/events")
def admin_analytics_events(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    event_name: str | None = None,
    style_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 500))
    stmt = select(EventLog).order_by(EventLog.occurred_at.desc()).limit(safe_limit)
    if event_name:
        stmt = stmt.where(EventLog.event_name == event_name)
    if style_id:
        stmt = stmt.where(EventLog.style_id == style_id)
    items = db.scalars(stmt).all()
    return {
        "items": [
            {
                "eventId": item.event_id,
                "eventName": item.event_name,
                "userId": item.user_id,
                "deviceId": item.device_id,
                "styleId": item.style_id,
                "storeId": item.store_id,
                "sourcePage": item.source_page,
                "sourceChannel": item.source_channel,
                "sessionId": item.session_id,
                "payload": loads_json(item.payload_json, None),
                "occurredAt": item.occurred_at.isoformat(),
            }
            for item in items
        ]
    }


@app.get("/admin/analytics/styles/{style_id}")
def admin_style_analytics(style_id: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    style = find_style(db, style_id)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    return {"style": style_to_dict(style), "analytics": build_style_trend_summary(db, style_id)}


@app.get("/admin/trends/recommendations")
def admin_recommendations(_: User = Depends(get_admin_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    items = db.scalars(select(TrendRecommendation).order_by(TrendRecommendation.created_at.desc())).all()
    return {"items": [recommendation_to_dict(item) for item in items]}


def apply_recommendation(db: Session, rec: TrendRecommendation) -> Style:
    style = find_style(db, rec.target_style_code) if rec.target_style_code else None
    candidate_payload = loads_json(rec.candidate_payload_json, None)
    if rec.recommendation_type == "launch_candidate":
        if not style:
            payload = candidate_payload or {
                "name": rec.candidate_name or "社区候选款",
                "vibe": "社区热度候选",
                "price": "￥268",
                "nailType": "方圆甲",
                "skinTone": "自然肤色",
                "tags": ["社区爆款"],
                "colors": ["#E8D7D1", "#B88D86"],
            }
            style = Style(
                code=build_style_code(rec.candidate_name or f"trend-{rec.recommendation_code}"),
                name=payload["name"],
                vibe=payload["vibe"],
                price=payload["price"],
                nail_type=payload["nailType"],
                skin_tone=payload["skinTone"],
                tags_json=dumps_json(payload.get("tags", [])),
                colors_json=dumps_json(payload.get("colors", [])),
                status="active",
                updated_at=utcnow(),
            )
            db.add(style)
            db.flush()
            rec.target_style_code = style.code
        else:
            style.status = "active"
            style.updated_at = utcnow()
    elif rec.recommendation_type == "boost_candidate":
        if not style:
            raise HTTPException(status_code=400, detail="recommendation has no target style")
        style.status = "active"
        style.updated_at = utcnow()
    elif rec.recommendation_type in {"deprioritize_candidate", "delist_candidate"}:
        if not style:
            raise HTTPException(status_code=400, detail="recommendation has no target style")
        style.status = "inactive" if rec.recommendation_type == "delist_candidate" else "draft"
        style.updated_at = utcnow()
    else:
        raise HTTPException(status_code=400, detail="unsupported recommendation type")
    if rec.target_store_code and style:
        listing = get_or_create_listing(db, rec.target_store_code, style.code, style.price)
        listing.status = "active" if rec.recommendation_type in {"launch_candidate", "boost_candidate"} else "inactive"
        listing.published_at = listing.published_at or utcnow()
    return style


@app.post("/admin/trends/recommendations/{recommendation_id}/approve")
def approve_recommendation(recommendation_id: str, payload: ReviewRequest, user: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    rec = db.scalar(select(TrendRecommendation).where(TrendRecommendation.recommendation_code == recommendation_id))
    if not rec:
        raise HTTPException(status_code=404, detail="recommendation not found")
    style = apply_recommendation(db, rec)
    rec.status = "approved"
    rec.reviewed_by_user_id = user.id
    rec.reviewed_at = utcnow()
    rec.action_text = f"{rec.action_text} 审核备注：{payload.reviewNote}".strip()
    db.add(rec)
    db.commit()
    return {"recommendation": recommendation_to_dict(rec), "style": style_to_dict(style)}


@app.post("/admin/trends/recommendations/{recommendation_id}/reject")
def reject_recommendation(recommendation_id: str, payload: ReviewRequest, user: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    rec = db.scalar(select(TrendRecommendation).where(TrendRecommendation.recommendation_code == recommendation_id))
    if not rec:
        raise HTTPException(status_code=404, detail="recommendation not found")
    rec.status = "rejected"
    rec.reviewed_by_user_id = user.id
    rec.reviewed_at = utcnow()
    rec.action_text = f"{rec.action_text} 审核备注：{payload.reviewNote}".strip()
    db.add(rec)
    db.commit()
    return {"recommendation": recommendation_to_dict(rec)}


@app.post("/admin/trends/import")
def admin_import_trend(payload: TrendImportRequest, _: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    topic_key = build_style_code(f"{payload.clusterLabel}-{payload.title}")[:40]
    topic = TrendTopic(
        topic_key=topic_key,
        platform="xiaohongshu",
        title=payload.title,
        cluster_label=payload.clusterLabel,
        summary=payload.summary,
        community_heat_score=payload.communityHeatScore,
        evidence_count=1,
        last_seen_at=utcnow(),
    )
    db.add(topic)
    db.flush()
    db.add(
        TrendRecommendation(
            recommendation_code=next_recommendation_code(db),
            recommendation_type=payload.recommendationType,
            target_style_code=payload.targetStyleId,
            candidate_name=payload.candidateName or payload.title,
            trigger_reason=payload.summary,
            community_evidence="人工导入的小红书主题，待运营确认。",
            in_app_evidence="站内数据将在下一轮聚合中补齐。",
            confidence_score=round(min(payload.communityHeatScore / 100, 0.99), 2),
            action_text="人工导入后待审核。",
            prerequisites="需要运营确认门店供给。",
        )
    )
    db.commit()
    return {"topicKey": topic.topic_key}


@app.get("/admin/merchants/me/dashboard")
def merchant_dashboard(user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.managed_store_code:
        raise HTTPException(status_code=400, detail="merchant user is not bound to a store")
    store = find_store(db, user.managed_store_code)
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    booking_count = db.query(Booking).filter(Booking.store_id == store.code).count()
    pending_requests = db.query(StyleLifecycleRequest).filter(StyleLifecycleRequest.store_code == store.code, StyleLifecycleRequest.status == "pending").count()
    listings = db.query(StoreStyleListing).filter(StoreStyleListing.store_code == store.code).count()
    return {
        "store": store_to_dict(store),
        "summary": {
            "bookingCount": booking_count,
            "pendingRequestCount": pending_requests,
            "listingCount": listings,
        },
    }


@app.get("/admin/merchants/me/listings")
def merchant_listings(user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.managed_store_code:
        return {"items": []}
    listings = db.scalars(select(StoreStyleListing).where(StoreStyleListing.store_code == user.managed_store_code).order_by(StoreStyleListing.style_code)).all()
    return {"items": [listing_to_dict(item) for item in listings]}


@app.patch("/admin/merchants/me/listings/{listing_id}")
def merchant_update_listing(listing_id: int, payload: MerchantListingUpdateRequest, user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    listing = db.get(StoreStyleListing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="listing not found")
    require_store_access(user, listing.store_code)
    if payload.price is not None:
        listing.price = payload.price
    if payload.inventoryCount is not None:
        listing.inventory_count = payload.inventoryCount
    if payload.status is not None:
        listing.status = payload.status
    listing.updated_at = utcnow()
    db.add(listing)
    db.commit()
    return {"listing": listing_to_dict(listing)}


@app.patch("/admin/merchants/me/store")
def merchant_update_store(payload: MerchantStoreUpdateRequest, user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.managed_store_code:
        raise HTTPException(status_code=400, detail="merchant user is not bound to a store")
    store = find_store(db, user.managed_store_code)
    if not store:
        raise HTTPException(status_code=404, detail="store not found")
    if payload.slots is not None:
        store.slots_json = dumps_json(payload.slots)
    if payload.isAcceptingBookings is not None:
        store.is_accepting_bookings = payload.isAcceptingBookings
    store.updated_at = utcnow()
    db.add(store)
    db.commit()
    return {"store": store_to_dict(store)}


@app.get("/admin/merchants/me/bookings")
def merchant_bookings(user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.managed_store_code:
        return {"items": []}
    bookings = db.scalars(select(Booking).where(Booking.store_id == user.managed_store_code).order_by(Booking.created_at.desc())).all()
    return {"items": [booking_response(item) for item in bookings]}


@app.get("/admin/merchants/me/requests")
def merchant_requests(user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not user.managed_store_code:
        return {"items": []}
    items = db.scalars(
        select(StyleLifecycleRequest)
        .where(StyleLifecycleRequest.store_code == user.managed_store_code)
        .order_by(StyleLifecycleRequest.created_at.desc())
    ).all()
    return {"items": [lifecycle_request_to_dict(item) for item in items]}


@app.post("/admin/merchants/me/requests")
def merchant_create_request(payload: MerchantLifecycleRequestCreate, user: User = Depends(require_merchant_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    store_code = payload.storeId or user.managed_store_code
    if not store_code:
        raise HTTPException(status_code=400, detail="storeId is required")
    require_store_access(user, store_code)
    style = find_style(db, payload.styleId)
    if not style:
        raise HTTPException(status_code=404, detail="style not found")
    req = StyleLifecycleRequest(
        request_code=next_request_code(db),
        requested_by_user_id=user.id,
        merchant_id=user.merchant_id,
        store_code=store_code,
        style_code=payload.styleId,
        requested_action=payload.requestedAction,
        reason=payload.reason,
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"request": lifecycle_request_to_dict(req)}


@app.post("/internal/try-on/jobs/claim")
def worker_claim_job(_: None = Depends(require_worker), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.status == "queued").order_by(TryOnJob.created_at.asc()))
    if not job:
        return {"job": None}
    style = find_style(db, job.style_id)
    if not style:
        job.status = "failed"
        job.error_code = "STYLE_NOT_FOUND"
        job.error_message = "style not found"
        db.add(job)
        db.commit()
        return {"job": None}
    job.status = "processing"
    job.stage = "preparing"
    job.progress = 15
    job.claimed_by_worker = True
    job.updated_at = utcnow()
    result_image_key = f"{job.job_code}.png"
    db.add(job)
    db.commit()
    return {
        "job": {
            "id": job.job_code,
            "styleId": style.code,
            "styleName": style.name,
            "sourceImagePath": str(settings.uploads_dir / job.source_image_key),
            "resultImagePath": str(settings.results_dir / result_image_key),
            "resultImageKey": result_image_key,
            "selectedLength": job.selected_length,
            "selectedShape": job.selected_shape,
            "styleColors": loads_json(style.colors_json, []),
        }
    }


@app.post("/internal/try-on/jobs/{job_code}/progress")
def worker_progress(job_code: str, payload: WorkerProgressRequest, _: None = Depends(require_worker), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    job.status = "processing"
    job.stage = payload.stage
    job.progress = payload.progress
    job.updated_at = utcnow()
    db.add(job)
    db.commit()
    return {"status": "ok"}


@app.post("/internal/try-on/jobs/{job_code}/complete")
def worker_complete(job_code: str, payload: WorkerCompleteRequest, _: None = Depends(require_worker), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    job.status = "completed"
    job.stage = "completed"
    job.progress = 100
    job.result_image_key = payload.resultImageKey
    job.detected_traits = serialize_traits(payload.detectedTraits)
    job.completed_at = utcnow()
    job.updated_at = utcnow()
    db.add(job)
    log_event(db, "tryon_complete", user_id=job.user_id, style_id=job.style_id, source_page="tryon_worker")
    db.commit()
    return {"status": "ok"}


@app.post("/internal/try-on/jobs/{job_code}/fail")
def worker_fail(job_code: str, payload: WorkerFailRequest, _: None = Depends(require_worker), db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.scalar(select(TryOnJob).where(TryOnJob.job_code == job_code))
    if not job:
        raise HTTPException(status_code=404, detail="try-on job not found")
    job.status = "failed"
    job.stage = "failed"
    job.error_code = payload.errorCode
    job.error_message = payload.errorMessage
    job.updated_at = utcnow()
    db.add(job)
    db.commit()
    return {"status": "ok"}


@app.post("/internal/trends/run")
def run_trend_refresh(_: None = Depends(require_worker), db: Session = Depends(get_db)) -> dict[str, Any]:
    created = 0
    styles = {style.code: style for style in db.scalars(select(Style)).all()}
    for topic in db.scalars(select(TrendTopic).order_by(TrendTopic.community_heat_score.desc())).all():
        target_style = next((code for code, style in styles.items() if topic.cluster_label in style.vibe or topic.cluster_label in style.name), None)
        if not target_style and topic.community_heat_score >= 80:
            target_style = None
            rec_type = "launch_candidate"
        else:
            rec_type = "boost_candidate" if topic.community_heat_score >= 80 else "deprioritize_candidate"
        existing = db.scalar(select(TrendRecommendation).where(TrendRecommendation.trigger_reason == topic.summary))
        if existing:
            continue
        db.add(
            TrendRecommendation(
                recommendation_code=next_recommendation_code(db),
                recommendation_type=rec_type,
                target_style_code=target_style,
                candidate_name=topic.title,
                trigger_reason=topic.summary,
                community_evidence=f"{topic.platform} 主题 {topic.title} 当前热度 {topic.community_heat_score}",
                in_app_evidence="根据近 7 日站内漏斗自动补齐。",
                confidence_score=round(min(topic.community_heat_score / 100, 0.99), 2),
                action_text="生成后待运营审核。",
                prerequisites="确认门店供给和价格带。",
            )
        )
        db.flush()
        created += 1
    db.commit()
    return {"created": created}
