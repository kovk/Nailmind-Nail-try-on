from __future__ import annotations

import json
import os
import re
import shlex
import sqlite3
import sys
import subprocess
import base64
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib import error as urllib_error
from urllib import request as urllib_request


OPENCLAW_CLI = os.getenv("OPENCLAW_CLI", "openclaw")
OPENCLAW_MODEL = os.getenv("OPENCLAW_MODEL", "mimo-v2.5-pro")
OPENCLAW_TIMEOUT_SECONDS = int(os.getenv("OPENCLAW_TIMEOUT_SECONDS", "180"))
OPENCLAW_USE_GATEWAY = os.getenv("OPENCLAW_USE_GATEWAY", "false").lower() == "true"
OPENCLAW_EXTRA_ARGS = shlex.split(os.getenv("OPENCLAW_EXTRA_ARGS", ""))
XHS_STORAGE_STATE_PATH = os.getenv("XHS_STORAGE_STATE_PATH", "")
XHS_SKILL_PATH = os.getenv("XHS_SKILL_PATH", "")
SPIDER_XHS_PATH = os.getenv("SPIDER_XHS_PATH", "")
XHS_COOKIES = os.getenv("XHS_COOKIES", "")
XHS_COLLECTOR_BACKEND = os.getenv("XHS_COLLECTOR_BACKEND", "xhs_skill")
XHS_ACCOUNT_MATRIX_DB_PATH = os.getenv("XHS_ACCOUNT_MATRIX_DB_PATH", "/app/data/XHS_ALL_IN_ONE/data/spider_xhs.db")
XHS_ACCOUNT_MATRIX_ENV_PATH = os.getenv("XHS_ACCOUNT_MATRIX_ENV_PATH", "/app/data/XHS_ALL_IN_ONE/data/runtime.env")
XHS_ACCOUNT_MATRIX_API_BASE = os.getenv("XHS_ACCOUNT_MATRIX_API_BASE", "http://172.17.0.1:8090/api").rstrip("/")
XHS_ACCOUNT_MATRIX_USERNAME = os.getenv("XHS_ACCOUNT_MATRIX_USERNAME", "operator")
XHS_ACCOUNT_MATRIX_PASSWORD = os.getenv("XHS_ACCOUNT_MATRIX_PASSWORD", "")
XHS_ACCOUNT_MATRIX_PASSWORD_FILE = os.getenv(
    "XHS_ACCOUNT_MATRIX_PASSWORD_FILE",
    "/app/data/XHS_ALL_IN_ONE/data/operator-password.txt",
)
XHS_ACCOUNT_MATRIX_PROJECT_PATH = os.getenv("XHS_ACCOUNT_MATRIX_PROJECT_PATH", "/app/data/XHS_ALL_IN_ONE")
XHS_BASE_URL = "https://www.xiaohongshu.com"
MAX_REASONABLE_ENGAGEMENT_COUNT = 200000
UNUSABLE_XHS_TEXTS = (
    "当前笔记暂时无法浏览",
    "笔记暂时无法浏览",
    "暂时无法浏览",
    "内容暂时无法查看",
    "内容无法查看",
    "页面不存在",
)
UNUSABLE_XHS_AUTHORS = ("我", "用户已注销", "小红书用户", "作者已隐藏")


def parse_metric_text(text: str | None) -> int:
    if not text:
        return 0
    normalized = text.strip().replace(",", "").replace("点赞", "").replace("赞", "").replace("收藏", "").replace("评论", "")
    normalized = normalized.replace("w", "万").replace("W", "万").replace("+", "")
    if not normalized:
        return 0
    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return 0
    value = float(match.group(1))
    if "万" in normalized:
        value *= 10000
    elif normalized.lower().endswith("k"):
        value *= 1000
    return min(int(value), MAX_REASONABLE_ENGAGEMENT_COUNT)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def is_unusable_xhs_text(text: str | None) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    return any(token in normalized for token in UNUSABLE_XHS_TEXTS)


def sanitize_image_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized = url.strip()
    if not normalized or normalized.startswith("data:"):
        return None
    if normalized.startswith("//"):
        return f"https:{normalized}"
    return normalized if normalized.startswith("http://") or normalized.startswith("https://") else None


def is_placeholder_image(url: str | None) -> bool:
    normalized = (url or "").lower()
    if not normalized:
        return True
    return any(token in normalized for token in ("fe_api", "favicon", "logo", "default", "placeholder"))


def looks_like_nail_title(title: str | None, keyword: str | None = None) -> bool:
    normalized = normalize_text(title)
    if is_unusable_xhs_text(normalized):
        return False
    lower = normalized.lower()
    if keyword and normalize_text(keyword) in normalized:
        return True
    if "美甲" in normalized or "甲" in normalized or "法式" in normalized or "猫眼" in normalized or "晕染" in normalized:
        return True
    if re.fullmatch(r"[a-z0-9 .!~_\-]+", lower):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]{2,}", normalized))


def is_valid_xhs_author(author: str | None) -> bool:
    normalized = normalize_text(author)
    if not normalized:
        return False
    return normalized not in UNUSABLE_XHS_AUTHORS


def best_post_title(post: dict[str, Any], fallback: str) -> str:
    title = normalize_text(post.get("title"))
    return title if not is_unusable_xhs_text(title) else fallback


def select_representative_post(posts: list[dict[str, Any]], keyword: str, cluster_label: str) -> dict[str, Any]:
    fallback = normalize_text(cluster_label) or normalize_text(keyword) or "社区热门款"

    def sort_key(post: dict[str, Any]) -> tuple[int, int, int]:
        title = normalize_text(post.get("title"))
        return (
            0 if looks_like_nail_title(title, keyword) else 1,
            0 if sanitize_image_url(post.get("imageUrl")) else 1,
            -score_post(post),
        )

    if not posts:
        return {"title": fallback, "imageUrl": None, "author": "", "tags": [keyword]}
    selected = sorted(posts, key=sort_key)[0]
    selected["title"] = best_post_title(selected, fallback)
    return selected


def trend_post_meta(post_payload: dict[str, Any]) -> dict[str, Any]:
    if not post_payload:
        return {"tags": [], "imageUrl": None, "keyword": None, "sourceNoteId": None}
    if "imageUrl" in post_payload or "tags" in post_payload:
        return {
            "tags": post_payload.get("tags", []),
            "imageUrl": sanitize_image_url(post_payload.get("imageUrl")),
            "keyword": post_payload.get("keyword"),
            "sourceNoteId": post_payload.get("sourceNoteId"),
        }
    if isinstance(post_payload, list):
        return {"tags": post_payload, "imageUrl": None, "keyword": None, "sourceNoteId": None}
    return {"tags": [], "imageUrl": None, "keyword": None, "sourceNoteId": None}


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


def top_tags_from_posts(posts: list[dict[str, Any]], limit: int = 4) -> list[str]:
    counter: Counter[str] = Counter()
    for post in posts:
        for tag in post.get("tags", []):
            if tag:
                counter[tag] += 1
    return [tag for tag, _ in counter.most_common(limit)]


def score_post(post: dict[str, Any]) -> int:
    return int(post.get("likeCount", 0)) + int(post.get("collectCount", 0)) * 2 + int(post.get("commentCount", 0)) * 3


def is_valid_nail_post(post: dict[str, Any], keyword: str | None = None) -> bool:
    title = normalize_text(post.get("title"))
    if is_unusable_xhs_text(title):
        return False
    if not looks_like_nail_title(title, keyword):
        return False
    image_url = sanitize_image_url(post.get("imageUrl"))
    if image_url and is_placeholder_image(image_url):
        return False
    return True


def is_verified_xhs_post(post: dict[str, Any], keyword: str | None = None) -> bool:
    if not is_valid_nail_post(post, keyword):
        return False
    if not is_valid_xhs_author(post.get("author")):
        return False
    if not str(post.get("url") or "").startswith(f"{XHS_BASE_URL}/explore/"):
        return False
    image_url = sanitize_image_url(post.get("imageUrl"))
    if not image_url:
        return False
    return True


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def load_xhs_cookies_from_storage_state(path: str | None = None) -> str:
    state_path = path or XHS_STORAGE_STATE_PATH
    if not state_path:
        return ""
    storage_file = Path(state_path)
    if not storage_file.exists():
        return ""
    try:
        payload = json.loads(storage_file.read_text(encoding="utf-8"))
    except Exception:
        return ""
    cookies = []
    for cookie in payload.get("cookies", []):
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain") or "")
        name = cookie.get("name")
        value = cookie.get("value")
        if "xiaohongshu.com" in domain and name and value is not None:
            cookies.append(f"{name}={value}")
    return "; ".join(cookies)


def _read_env_value(path: str, key: str) -> str:
    env_file = Path(path)
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _cookie_header_from_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    if not stripped.startswith("{"):
        return stripped
    try:
        cookies = json.loads(stripped)
    except json.JSONDecodeError:
        return ""
    if not isinstance(cookies, dict):
        return ""
    return "; ".join(f"{key}={cookie_value}" for key, cookie_value in cookies.items() if cookie_value is not None)


def cookie_header_to_playwright_cookies(cookie_header: str) -> list[dict[str, Any]]:
    cookies: list[dict[str, Any]] = []
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or value is None:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".xiaohongshu.com",
                "path": "/",
                "httpOnly": name in {"web_session", "webId", "gid"},
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies


def load_xhs_cookies_from_account_matrix(
    db_path: str | None = None,
    env_path: str | None = None,
) -> str:
    """Read the latest XHS PC cookie saved by XHS_ALL_IN_ONE.

    The account matrix owns login; Nail Mind only consumes its encrypted cookie
    for trend collection, then continues through XhsSkills/OpenClaw.
    """
    database = Path(db_path or XHS_ACCOUNT_MATRIX_DB_PATH)
    if not database.exists():
        return ""
    secret = os.getenv("XHS_ACCOUNT_MATRIX_SECRET_KEY") or _read_env_value(env_path or XHS_ACCOUNT_MATRIX_ENV_PATH, "SECRET_KEY")
    if not secret:
        return ""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return ""
    query = """
        select cv.encrypted_cookies
        from account_cookie_versions cv
        join platform_accounts pa on pa.id = cv.platform_account_id
        where pa.platform = 'xhs'
          and coalesce(pa.sub_type, 'pc') = 'pc'
          and pa.status in ('active', 'healthy', 'unknown')
        order by cv.created_at desc, cv.id desc
        limit 1
    """
    try:
        with sqlite3.connect(str(database)) as connection:
            row = connection.execute(query).fetchone()
    except sqlite3.Error:
        return ""
    if not row or not row[0]:
        return ""
    try:
        raw = Fernet(_derive_fernet_key(secret)).decrypt(str(row[0]).encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
    return _cookie_header_from_text(raw)


def resolve_xhs_cookie_value(explicit_cookies: str | None = None) -> str:
    return (
        explicit_cookies
        or XHS_COOKIES
        or load_xhs_cookies_from_account_matrix()
        or load_xhs_cookies_from_storage_state()
    )


def extract_note_card_url(card: dict[str, Any]) -> str:
    note_card = card.get("note_card") or card.get("noteCard") or card
    note_id = first_present(card.get("id"), card.get("note_id"), note_card.get("note_id"), note_card.get("id"))
    xsec_token = first_present(card.get("xsec_token"), card.get("xsecToken"), note_card.get("xsec_token"), note_card.get("xsecToken"))
    url = f"{XHS_BASE_URL}/explore/{note_id}" if note_id else ""
    if xsec_token:
        url = f"{url}?xsec_token={xsec_token}&xsec_source=pc_search"
    return url


def extract_image_url_from_note(note: dict[str, Any]) -> str | None:
    image_list = first_present(note.get("image_list"), note.get("imageList"), note.get("images_list"), note.get("images")) or []
    for image in image_list:
        if not isinstance(image, dict):
            continue
        candidates = [
            image.get("url_default"),
            image.get("url_pre"),
            image.get("url"),
            image.get("trace_id"),
        ]
        info_list = image.get("info_list") or image.get("infoList") or []
        for info in info_list:
            if isinstance(info, dict):
                candidates.extend([info.get("url"), info.get("image_scene")])
        for candidate in candidates:
            safe = sanitize_image_url(candidate)
            if safe and not is_placeholder_image(safe):
                return safe
    cover = note.get("cover") or {}
    if isinstance(cover, dict):
        return sanitize_image_url(first_present(cover.get("url"), cover.get("url_default"), cover.get("url_pre")))
    return None


def extract_interaction_count(note: dict[str, Any], *keys: str) -> int:
    interact = note.get("interact_info") or note.get("interactInfo") or {}
    for key in keys:
        value = first_present(note.get(key), interact.get(key))
        if value is None:
            continue
        if isinstance(value, int):
            return min(value, MAX_REASONABLE_ENGAGEMENT_COUNT)
        parsed = parse_metric_text(str(value))
        if parsed:
            return parsed
    return 0


def normalize_spider_xhs_note(card: dict[str, Any], detail: dict[str, Any], keyword: str) -> dict[str, Any] | None:
    note = detail
    items = detail.get("data", {}).get("items") if isinstance(detail.get("data"), dict) else None
    if items and isinstance(items, list) and items:
        note = (items[0] or {}).get("note_card") or items[0]
    elif "note_card" in detail:
        note = detail.get("note_card") or detail
    elif "noteCard" in detail:
        note = detail.get("noteCard") or detail

    card_note = card.get("note_card") or card.get("noteCard") or card
    user = note.get("user") or note.get("user_info") or note.get("userInfo") or card_note.get("user") or {}
    title = normalize_text(first_present(note.get("title"), card_note.get("display_title"), card_note.get("title"), card_note.get("desc")))
    desc = normalize_text(first_present(note.get("desc"), note.get("description"), card_note.get("desc")))
    author = normalize_text(first_present(user.get("nickname"), user.get("nick_name"), user.get("name"), card_note.get("nickname")))
    url = extract_note_card_url(card)
    image_url = extract_image_url_from_note(note) or extract_image_url_from_note(card_note)
    tags = [keyword]
    for tag in note.get("tag_list") or note.get("tagList") or []:
        if isinstance(tag, dict):
            tag_name = normalize_text(first_present(tag.get("name"), tag.get("tag_name"), tag.get("title")))
            if tag_name:
                tags.append(tag_name)
    post = {
        "postId": url.rstrip("/").split("/")[-1].split("?")[0] if url else "",
        "url": url,
        "title": title or desc,
        "imageUrl": image_url or "",
        "author": author,
        "likeCount": extract_interaction_count(note, "liked_count", "likedCount", "like_count", "likeCount"),
        "collectCount": extract_interaction_count(note, "collected_count", "collectedCount", "collect_count", "collectCount"),
        "commentCount": extract_interaction_count(note, "comment_count", "commentCount"),
        "tags": list(dict.fromkeys(tag for tag in tags if tag)),
        "publishedAt": normalize_text(first_present(note.get("time"), note.get("last_update_time"), note.get("publish_time"))),
    }
    post["verified"] = is_verified_xhs_post(post, keyword)
    return post if post["verified"] else None


def _json_http_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 90,
) -> Any:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib_request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"账号矩阵接口失败 {exc.code}: {detail[:300]}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"账号矩阵接口不可用: {exc}") from exc
    return json.loads(text) if text else None


def _sse_http_request(
    url: str,
    *,
    payload: dict[str, Any],
    token: str,
    timeout: int = 180,
) -> list[dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    events: list[dict[str, Any]] = []
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            buffer: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").rstrip("\n")
                if line.startswith("data:"):
                    buffer.append(line[5:].strip())
                elif not line and buffer:
                    data = "\n".join(buffer).strip()
                    buffer = []
                    if data:
                        try:
                            events.append(json.loads(data))
                        except json.JSONDecodeError:
                            continue
            if buffer:
                data = "\n".join(buffer).strip()
                if data:
                    try:
                        events.append(json.loads(data))
                    except json.JSONDecodeError:
                        pass
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"账号矩阵数据抓取失败 {exc.code}: {detail[:300]}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"账号矩阵数据抓取不可用: {exc}") from exc
    return events


def account_matrix_token() -> str:
    password = XHS_ACCOUNT_MATRIX_PASSWORD
    if not password and XHS_ACCOUNT_MATRIX_PASSWORD_FILE:
        password_file = Path(XHS_ACCOUNT_MATRIX_PASSWORD_FILE)
        if password_file.exists():
            password = password_file.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("XHS_ACCOUNT_MATRIX_PASSWORD is required to use account matrix collection")
    response = _json_http_request(
        f"{XHS_ACCOUNT_MATRIX_API_BASE}/auth/login",
        method="POST",
        payload={"username": XHS_ACCOUNT_MATRIX_USERNAME, "password": password},
        timeout=30,
    )
    token = response.get("access_token") if isinstance(response, dict) else ""
    if not token:
        raise RuntimeError("账号矩阵登录失败：未返回 access_token")
    return token


def latest_account_matrix_pc_account_id(token: str) -> int:
    response = _json_http_request(f"{XHS_ACCOUNT_MATRIX_API_BASE}/accounts?platform=xhs", token=token, timeout=30)
    items = response.get("items") if isinstance(response, dict) else []
    for account in items or []:
        if account.get("sub_type") == "pc" and account.get("status") in {"active", "healthy", "unknown"}:
            return int(account["id"])
    raise RuntimeError("请先在运营端账号矩阵完成小红书 PC 账号登录，再执行趋势采集")


def normalize_account_matrix_note(item: dict[str, Any], detail: dict[str, Any] | None, keyword: str) -> dict[str, Any] | None:
    detail = detail or {}
    image_urls = detail.get("image_urls") or item.get("image_urls") or []
    image_url = ""
    if isinstance(image_urls, list) and image_urls:
        image_url = sanitize_image_url(str(image_urls[0])) or ""
    image_url = image_url or sanitize_image_url(detail.get("cover_url") or item.get("cover_url")) or ""
    url = normalize_text(detail.get("note_url") or item.get("note_url"))
    title = normalize_text(first_present(detail.get("title"), item.get("title"), detail.get("content"), item.get("content")))
    author = normalize_text(first_present(detail.get("author_name"), item.get("author_name")))
    post = {
        "postId": normalize_text(detail.get("note_id") or item.get("note_id") or url.rstrip("/").split("/")[-1].split("?")[0]),
        "url": url,
        "title": title,
        "imageUrl": image_url,
        "author": author,
        "likeCount": extract_interaction_count(detail, "likes", "liked_count", "likedCount") or extract_interaction_count(item, "likes", "liked_count", "likedCount"),
        "collectCount": extract_interaction_count(detail, "collects", "collected_count", "collectedCount") or extract_interaction_count(item, "collects", "collected_count", "collectedCount"),
        "commentCount": extract_interaction_count(detail, "comments", "comment_count", "commentCount") or extract_interaction_count(item, "comments", "comment_count", "commentCount"),
        "tags": list(dict.fromkeys([keyword, *[normalize_text(tag) for tag in detail.get("tags", []) if tag]])),
        "publishedAt": normalize_text(str(first_present(detail.get("timestamp"), item.get("timestamp")) or "")),
    }
    post["verified"] = is_verified_xhs_post(post, keyword)
    return post if post["verified"] else None


def normalize_account_matrix_library_note(item: dict[str, Any], keyword: str) -> dict[str, Any] | None:
    raw = item.get("raw_json") if isinstance(item.get("raw_json"), dict) else {}
    image_url = sanitize_image_url(item.get("cover_url")) or ""
    asset_urls = item.get("asset_urls") if isinstance(item.get("asset_urls"), list) else []
    if not image_url and asset_urls:
        image_url = sanitize_image_url(asset_urls[0]) or ""
    url = normalize_text(raw.get("note_url") or raw.get("url") or item.get("note_url"))
    note_id = normalize_text(item.get("note_id") or raw.get("note_id") or url.rstrip("/").split("/")[-1].split("?")[0])
    post = {
        "postId": note_id,
        "url": url or f"{XHS_BASE_URL}/explore/{note_id}",
        "title": normalize_text(item.get("title") or raw.get("title")),
        "imageUrl": image_url,
        "author": normalize_text(item.get("author_name") or raw.get("author_name")),
        "likeCount": extract_interaction_count(raw, "likes", "liked_count", "likedCount"),
        "collectCount": extract_interaction_count(raw, "collects", "collected_count", "collectedCount"),
        "commentCount": extract_interaction_count(raw, "comments", "comment_count", "commentCount"),
        "tags": [keyword, *[normalize_text(tag.get("name")) for tag in item.get("tags", []) if isinstance(tag, dict)]],
        "publishedAt": normalize_text(item.get("created_at")),
    }
    post["verified"] = is_verified_xhs_post(post, keyword)
    return post if post["verified"] else None


def collect_account_matrix_library_notes(token: str, keyword: str, max_posts: int) -> list[dict[str, Any]]:
    query = quote(keyword)
    response = _json_http_request(
        f"{XHS_ACCOUNT_MATRIX_API_BASE}/notes?platform=xhs&q={query}&has_assets=true&page=1&page_size={min(max(max_posts * 3, 20), 100)}",
        token=token,
        timeout=30,
    )
    items = response.get("items") if isinstance(response, dict) else []
    posts = [post for item in items or [] if (post := normalize_account_matrix_library_note(item, keyword))]
    return sorted(posts, key=lambda item: int(item.get("likeCount") or 0), reverse=True)[:max_posts]


def collect_xiaohongshu_notes_with_account_matrix(
    keywords: list[str],
    max_posts_per_keyword: int = 8,
) -> list[dict[str, Any]]:
    token = account_matrix_token()
    account_id = latest_account_matrix_pc_account_id(token)
    results: list[dict[str, Any]] = []
    for keyword in [item.strip() for item in keywords if item.strip()]:
        crawl_payload = {
            "account_id": account_id,
            "mode": "search",
            "keyword": keyword,
            "page": 1,
            "pages": max(1, min(20, (max_posts_per_keyword + 19) // 20 or 1)),
            "max_notes": max_posts_per_keyword,
            "time_sleep": 1.0,
            "fetch_comments": False,
            "sort_type_choice": 2,
            "note_type": 0,
            "note_time": 0,
            "note_range": 0,
            "pos_distance": 0,
            "geo": "",
        }
        events = _sse_http_request(
            f"{XHS_ACCOUNT_MATRIX_API_BASE}/xhs/crawl/data",
            payload=crawl_payload,
            token=token,
            timeout=max(180, max_posts_per_keyword * 20),
        )
        enriched_posts: list[dict[str, Any]] = []
        errors: list[str] = []
        for event in events:
            if event.get("type") == "error":
                errors.append(normalize_text(event.get("message")))
                continue
            if event.get("type") != "item":
                continue
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            if item.get("status") != "success":
                if item.get("error"):
                    errors.append(normalize_text(item.get("error")))
                continue
            note = item.get("note") if isinstance(item.get("note"), dict) else {}
            post = normalize_account_matrix_note(note, note, keyword)
            if post:
                enriched_posts.append(post)
        enriched_posts = sorted(enriched_posts, key=lambda item: item.get("likeCount", 0), reverse=True)[:max_posts_per_keyword]
        if not enriched_posts:
            enriched_posts = collect_account_matrix_library_notes(token, keyword, max_posts_per_keyword)
        if not enriched_posts:
            project_path = Path(XHS_ACCOUNT_MATRIX_PROJECT_PATH)
            if project_path.exists():
                try:
                    direct_results = collect_xiaohongshu_notes_with_spider_xhs(
                        keywords=[keyword],
                        max_posts_per_keyword=max_posts_per_keyword,
                        spider_path=str(project_path),
                    )
                    if direct_results:
                        results.extend(direct_results)
                        continue
                except RuntimeError as exc:
                    errors.append(normalize_text(str(exc)))
        if not enriched_posts:
            browser_results = collect_xiaohongshu_notes_with_browser(
                keywords=[keyword],
                max_posts_per_keyword=max_posts_per_keyword,
                headless=True,
            )
            if browser_results:
                results.extend(browser_results)
                continue
        if not enriched_posts:
            if errors:
                raise RuntimeError(f"账号矩阵数据抓取未获得可用帖子：{'; '.join(errors[:3])}")
            continue
        heat_score = min(99.0, round(sum(score_post(item) for item in enriched_posts) / max(len(enriched_posts), 1), 2))
        usable_titles = [item["title"] for item in enriched_posts[:3]]
        representative_post = select_representative_post(enriched_posts, keyword, keyword)
        results.append(
            {
                "keyword": keyword,
                "topicTitle": representative_post["title"] if representative_post.get("title") else keyword,
                "clusterLabel": keyword,
                "summary": f"{keyword} 高热真实笔记集中在：{'；'.join(usable_titles)}",
                "communityHeatScore": heat_score,
                "posts": enriched_posts,
            }
        )
    return results


def resolve_xhs_skill_script(skill_path: str | None = None) -> Path:
    raw_root = skill_path or XHS_SKILL_PATH
    if not raw_root:
        raise RuntimeError("XHS_SKILL_PATH is required for xhs_skill collection")
    root = Path(raw_root)
    if root.name == "xhs-apis":
        script = root / "scripts" / "xhs_api_tool.py"
    elif (root / "scripts" / "xhs_api_tool.py").exists():
        script = root / "scripts" / "xhs_api_tool.py"
    else:
        script = root / "skills" / "xhs-apis" / "scripts" / "xhs_api_tool.py"
    if not script.exists():
        raise RuntimeError(f"XhsSkills xhs_api_tool.py does not exist: {script}")
    return script


def call_xhs_skill(script: Path, namespace: str, method: str, payload: dict[str, Any]) -> Any:
    import tempfile

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        params_path = handle.name
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "call", namespace, method, "--params-file", params_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    finally:
        try:
            Path(params_path).unlink()
        except OSError:
            pass
    output = (completed.stdout or "").strip()
    if not output:
        raise RuntimeError((completed.stderr or "XhsSkills returned empty output").strip())
    try:
        response = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"XhsSkills returned non-JSON output: {output[:300]}") from exc
    if completed.returncode != 0 or response.get("error"):
        raise RuntimeError(str(response.get("error") or completed.stderr or "XhsSkills call failed"))
    return response.get("result")


def xhs_skill_result_tuple(result: Any, method: str) -> tuple[bool, str, Any]:
    if isinstance(result, list) and len(result) >= 3:
        return bool(result[0]), str(result[1]), result[2]
    if isinstance(result, tuple) and len(result) >= 3:
        return bool(result[0]), str(result[1]), result[2]
    raise RuntimeError(f"Unexpected XhsSkills result for {method}: {str(result)[:300]}")


def collect_xiaohongshu_notes_with_xhs_skill(
    keywords: list[str],
    max_posts_per_keyword: int = 8,
    cookies: str | None = None,
    skill_path: str | None = None,
) -> list[dict[str, Any]]:
    cookie_value = resolve_xhs_cookie_value(cookies)
    if not cookie_value:
        raise RuntimeError("请先在运营端账号矩阵完成小红书 PC 账号登录，再执行趋势采集")
    script = resolve_xhs_skill_script(skill_path)

    results: list[dict[str, Any]] = []
    for keyword in [item.strip() for item in keywords if item.strip()]:
        raw_search = call_xhs_skill(
            script,
            "pc",
            "search_some_note",
            {
                "query": keyword,
                "require_num": max_posts_per_keyword * 2,
                "cookies_str": cookie_value,
                "sort_type_choice": 2,
            },
        )
        success, msg, cards = xhs_skill_result_tuple(raw_search, "search_some_note")
        if not success:
            raise RuntimeError(f"XhsSkills search failed for {keyword}: {msg}")
        enriched_posts: list[dict[str, Any]] = []
        for card in cards or []:
            url = extract_note_card_url(card)
            if not url:
                continue
            raw_detail = call_xhs_skill(script, "pc", "get_note_info", {"url": url, "cookies_str": cookie_value})
            detail_success, detail_msg, detail = xhs_skill_result_tuple(raw_detail, "get_note_info")
            if not detail_success:
                continue
            post = normalize_spider_xhs_note(card, detail or {}, keyword)
            if post:
                enriched_posts.append(post)
            if len(enriched_posts) >= max_posts_per_keyword:
                break
        if not enriched_posts:
            continue
        heat_score = min(99.0, round(sum(score_post(item) for item in enriched_posts) / max(len(enriched_posts), 1), 2))
        usable_titles = [item["title"] for item in enriched_posts[:3]]
        representative_post = select_representative_post(enriched_posts, keyword, keyword)
        results.append(
            {
                "keyword": keyword,
                "topicTitle": representative_post["title"] if representative_post.get("title") else keyword,
                "clusterLabel": keyword,
                "summary": f"{keyword} 高热真实笔记集中在：{'；'.join(usable_titles)}",
                "communityHeatScore": heat_score,
                "posts": enriched_posts,
            }
        )
    return results


def collect_xiaohongshu_notes_with_spider_xhs(
    keywords: list[str],
    max_posts_per_keyword: int = 8,
    cookies: str | None = None,
    spider_path: str | None = None,
) -> list[dict[str, Any]]:
    cookie_value = resolve_xhs_cookie_value(cookies)
    project_path = spider_path or SPIDER_XHS_PATH
    if not cookie_value:
        raise RuntimeError("请先在运营端账号矩阵完成小红书 PC 账号登录，再执行趋势采集")
    if not project_path:
        raise RuntimeError("SPIDER_XHS_PATH is required for Spider_XHS collection")
    project = Path(project_path)
    if not project.exists():
        raise RuntimeError(f"Spider_XHS path does not exist: {project}")
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    node_modules = project / "node_modules"
    if node_modules.exists():
        existing_node_path = os.environ.get("NODE_PATH")
        paths = [str(node_modules)]
        if existing_node_path:
            paths.append(existing_node_path)
        os.environ["NODE_PATH"] = os.pathsep.join(paths)
    try:
        from apis.xhs_pc_apis import XHS_Apis
    except Exception as exc:
        raise RuntimeError(f"failed to import Spider_XHS APIs: {exc}") from exc

    api = XHS_Apis()
    results: list[dict[str, Any]] = []
    original_cwd = Path.cwd()
    try:
        os.chdir(project)
        for keyword in [item.strip() for item in keywords if item.strip()]:
            success, msg, cards = api.search_some_note(keyword, max_posts_per_keyword * 2, cookie_value, sort_type_choice=2)
            if not success:
                raise RuntimeError(f"Spider_XHS search failed for {keyword}: {msg}")
            enriched_posts: list[dict[str, Any]] = []
            for card in cards:
                url = extract_note_card_url(card)
                if not url:
                    continue
                success, msg, detail = api.get_note_info(url, cookie_value)
                if not success:
                    continue
                post = normalize_spider_xhs_note(card, detail or {}, keyword)
                if post:
                    enriched_posts.append(post)
                if len(enriched_posts) >= max_posts_per_keyword:
                    break
            if not enriched_posts:
                continue
            heat_score = min(99.0, round(sum(score_post(item) for item in enriched_posts) / max(len(enriched_posts), 1), 2))
            usable_titles = [item["title"] for item in enriched_posts[:3]]
            representative_post = select_representative_post(enriched_posts, keyword, keyword)
            results.append(
                {
                    "keyword": keyword,
                    "topicTitle": representative_post["title"] if representative_post.get("title") else keyword,
                    "clusterLabel": keyword,
                    "summary": f"{keyword} 高热真实笔记集中在：{'；'.join(usable_titles)}",
                    "communityHeatScore": heat_score,
                    "posts": enriched_posts,
                }
            )
    finally:
        os.chdir(original_cwd)
    return results


def check_xhs_collection_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "accountMatrixReachable": False,
        "accountId": None,
        "hasCookie": False,
        "spiderReady": False,
        "loginHealthy": False,
        "status": "unavailable",
        "message": "",
    }
    try:
        token = account_matrix_token()
        status["accountMatrixReachable"] = True
        status["accountId"] = latest_account_matrix_pc_account_id(token)
    except Exception as exc:
        status["message"] = f"账号矩阵不可用或未登录：{normalize_text(str(exc))}"
        return status

    cookie_value = resolve_xhs_cookie_value()
    status["hasCookie"] = bool(cookie_value)
    if not cookie_value:
        status["status"] = "missing_cookie"
        status["message"] = "账号矩阵没有可用的小红书 PC Cookie，请先登录账号矩阵。"
        return status

    project = Path(XHS_ACCOUNT_MATRIX_PROJECT_PATH)
    if not project.exists():
        status["status"] = "missing_spider"
        status["message"] = f"Spider_XHS 运行目录不存在：{project}"
        return status
    if str(project) not in sys.path:
        sys.path.insert(0, str(project))
    node_modules = project / "node_modules"
    if node_modules.exists():
        existing_node_path = os.environ.get("NODE_PATH")
        paths = [str(node_modules)]
        if existing_node_path:
            paths.append(existing_node_path)
        os.environ["NODE_PATH"] = os.pathsep.join(paths)
    try:
        from apis.xhs_pc_apis import XHS_Apis
    except Exception as exc:
        status["status"] = "spider_import_failed"
        status["message"] = f"Spider_XHS 接口加载失败：{normalize_text(str(exc))}"
        return status

    status["spiderReady"] = True
    original_cwd = Path.cwd()
    try:
        os.chdir(project)
        success, message, payload = XHS_Apis().get_user_self_info(cookies_str=cookie_value)
    finally:
        os.chdir(original_cwd)
    if success:
        status["loginHealthy"] = True
        status["status"] = "healthy"
        data = payload.get("data") if isinstance(payload, dict) else {}
        basic = data.get("basic_info") if isinstance(data, dict) else {}
        nickname = basic.get("nickname") if isinstance(basic, dict) else ""
        status["message"] = f"小红书 PC 登录态有效{f'：{nickname}' if nickname else ''}"
        return status
    status["status"] = "expired" if "登录已过期" in normalize_text(message) else "unhealthy"
    status["message"] = normalize_text(message) or "小红书登录态不可用，请重新登录账号矩阵。"
    return status


def collect_xiaohongshu_notes_with_browser(
    keywords: list[str],
    max_posts_per_keyword: int = 8,
    headless: bool = True,
    storage_state_path: str | None = None,
    cookies: str | None = None,
) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright is not installed; run `playwright install chromium` after installing requirements") from exc

    storage_state = storage_state_path or XHS_STORAGE_STATE_PATH
    cookie_value = resolve_xhs_cookie_value(cookies)
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"] if headless else [],
        )
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1440, "height": 1600},
            "locale": "zh-CN",
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if storage_state and Path(storage_state).exists():
            context_kwargs["storage_state"] = storage_state
        context = browser.new_context(**context_kwargs)
        if cookie_value and "storage_state" not in context_kwargs:
            context.add_cookies(cookie_header_to_playwright_cookies(cookie_value))
        page = context.new_page()
        detail_page = context.new_page()
        for keyword in [item.strip() for item in keywords if item.strip()]:
            search_url = f"{XHS_BASE_URL}/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
            page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
            body_text = normalize_text(page.locator("body").inner_text(timeout=10000))
            if "登录后查看搜索结果" in body_text and not cookie_value and not context_kwargs.get("storage_state"):
                raise RuntimeError("小红书搜索需要登录态：请先在账号矩阵完成 PC 账号登录")
            cards = page.evaluate(
                """
                () => {
                  const seen = new Set();
                  const roots = Array.from(document.querySelectorAll('section, div, article'));
                  const posts = [];
                  for (const root of roots) {
                    const anchor = root.matches('a[href*="/explore/"], a[href*="/discovery/item/"]')
                      ? root
                      : root.querySelector('a[href*="/explore/"], a[href*="/discovery/item/"]');
                    if (!anchor) continue;
                    const href = anchor.href || anchor.getAttribute('href');
                    if (!href || seen.has(href)) continue;
                    const imageNode = root.querySelector('img');
                    const titleNode = root.querySelector('img[alt]') || root.querySelector('h3') || root.querySelector('[class*=title]') || anchor;
                    const authorNode = root.querySelector('[class*=author], [class*=user], [class*=name], [class*=nickname]');
                    const metricText = Array.from(root.querySelectorAll('[class*=like], [class*=collect], [class*=comment], span'))
                      .map(node => (node.textContent || '').trim())
                      .filter(Boolean)
                      .join(' | ');
                    const title = (titleNode?.getAttribute?.('alt') || titleNode?.textContent || '').trim();
                    const imageUrl = imageNode?.src || imageNode?.getAttribute?.('src') || '';
                    if (!title || !imageUrl) continue;
                    seen.add(href);
                    posts.push({
                      url: href.startsWith('http') ? href : `https://www.xiaohongshu.com${href}`,
                      title,
                      imageUrl,
                      author: (authorNode?.textContent || '').trim(),
                      metricText,
                    });
                    if (posts.length >= 30) break;
                  }
                  return posts;
                }
                """,
            )
            enriched_posts: list[dict[str, Any]] = []
            for index, card in enumerate(cards):
                detail = {
                    "postId": str(card["url"]).rstrip("/").split("/")[-1].split("?")[0],
                    "url": card["url"],
                    "title": normalize_text(card["title"]),
                    "imageUrl": sanitize_image_url(card.get("imageUrl")) or "",
                    "author": normalize_text(card.get("author") or ""),
                    "likeCount": parse_metric_text(card.get("metricText")),
                    "collectCount": 0,
                    "commentCount": 0,
                    "tags": [keyword],
                    "publishedAt": None,
                    "rank": index + 1,
                    "verified": False,
                }
                try:
                    detail_page.goto(card["url"], wait_until="domcontentloaded", timeout=30000)
                    detail_page.wait_for_timeout(2000)
                    detail_meta = detail_page.evaluate(
                        """
                        () => {
                          const textOf = (selectors) => {
                            for (const selector of selectors) {
                              const node = document.querySelector(selector);
                              const text = (node?.textContent || '').trim();
                              if (text) return text;
                            }
                            return '';
                          };
                          const images = Array.from(document.querySelectorAll('img'))
                            .map(img => img.src || img.getAttribute('src') || '')
                            .filter(Boolean);
                          const tags = Array.from(document.querySelectorAll('a[href*="search_result"], [class*=tag], [class*=topic]'))
                            .map(node => (node.textContent || '').replace(/^#/, '').trim())
                            .filter(Boolean)
                            .slice(0, 8);
                          return {
                            title: textOf(['h1', '[class*=title]']),
                            author: textOf(['[class*=author]', '[class*=user]', '[class*=nickname]']),
                            likeText: textOf(['[class*=like]', 'button span']),
                            collectText: textOf(['[class*=collect]']),
                            commentText: textOf(['[class*=comment]']),
                            publishedAt: textOf(['time', '[class*=date]', '[class*=publish]']),
                            imageUrl: images.find(url => !url.startsWith('data:')) || '',
                            tags,
                          };
                        }
                        """,
                    )
                    if detail_meta.get("title") and not is_unusable_xhs_text(detail_meta.get("title")):
                        detail["title"] = normalize_text(detail_meta["title"])
                    if detail_meta.get("author"):
                        detail["author"] = normalize_text(detail_meta["author"])
                    safe_image_url = sanitize_image_url(detail_meta.get("imageUrl"))
                    if safe_image_url and not is_placeholder_image(safe_image_url):
                        detail["imageUrl"] = safe_image_url
                    detail["likeCount"] = max(detail["likeCount"], parse_metric_text(detail_meta.get("likeText")))
                    detail["collectCount"] = parse_metric_text(detail_meta.get("collectText"))
                    detail["commentCount"] = parse_metric_text(detail_meta.get("commentText"))
                    detail["tags"] = list(dict.fromkeys([keyword, *[normalize_text(tag) for tag in detail_meta.get("tags", []) if normalize_text(tag)]]))
                    detail["publishedAt"] = normalize_text(detail_meta.get("publishedAt"))
                except Exception:
                    pass
                detail["verified"] = is_verified_xhs_post(detail, keyword)
                if not detail["verified"]:
                    continue
                enriched_posts.append(detail)
                if len(enriched_posts) >= max_posts_per_keyword:
                    break
            if not enriched_posts:
                continue
            enriched_posts = sorted(enriched_posts, key=lambda item: int(item.get("likeCount") or 0), reverse=True)[:max_posts_per_keyword]
            heat_score = min(
                99.0,
                round(
                    sum(score_post(item) or max_posts_per_keyword - idx for idx, item in enumerate(enriched_posts[:8]))
                    / max(len(enriched_posts), 1),
                    2,
                ),
            )
            usable_titles = [item["title"] for item in enriched_posts[:3]]
            representative_post = select_representative_post(enriched_posts, keyword, keyword)
            results.append(
                {
                    "keyword": keyword,
                    "topicTitle": representative_post["title"] if representative_post.get("title") else keyword,
                    "clusterLabel": keyword,
                    "summary": f"{keyword} 高热真实笔记集中在：{'；'.join(usable_titles)}",
                    "communityHeatScore": heat_score,
                    "posts": enriched_posts,
                }
            )
        context.close()
        browser.close()
    return results


def build_candidate_payload(topic_title: str, cluster_label: str, summary: str, posts: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(posts, key=lambda item: int(item.get("likeCount") or 0), reverse=True)
    tags = top_tags_from_posts(posts) or [cluster_label] if cluster_label else []
    fallback_name = normalize_text(cluster_label) or (tags[0] if tags else "社区热门款")
    lead = select_representative_post(ranked, fallback_name, cluster_label) if ranked else {}
    display_name = normalize_text(topic_title)
    if is_unusable_xhs_text(display_name) or not looks_like_nail_title(display_name, cluster_label):
        display_name = fallback_name
    source_posts = [
        {
            "postId": item.get("postId"),
            "url": item.get("url"),
            "title": best_post_title(item, fallback_name),
            "author": item.get("author"),
            "imageUrl": sanitize_image_url(item.get("imageUrl")),
            "likeCount": item.get("likeCount", 0),
            "collectCount": item.get("collectCount", 0),
            "commentCount": item.get("commentCount", 0),
            "verified": bool(item.get("verified")),
        }
        for item in ranked[:5]
    ]
    vibe = normalize_text(summary)
    if is_unusable_xhs_text(vibe):
        vibe = f"{fallback_name} 近期在小红书互动活跃，适合运营复核后评估上新。"
    return {
        "name": display_name[:15],
        "vibe": vibe[:80],
        "price": "",
        "nailType": "",
        "skinTone": "",
        "tags": tags[:4],
        "colors": [],
        "imageUrl": sanitize_image_url(lead.get("imageUrl")),
        "sourcePosts": source_posts,
        "clusterLabel": cluster_label,
    }


def heuristic_recommendation_type(title: str, cluster_label: str, heat: float) -> str:
    haystack = f"{title} {cluster_label}".lower()
    if any(keyword in haystack for keyword in ("降温", "过时", "翻车", "避雷")):
        return "deprioritize_candidate"
    if heat >= 80:
        return "launch_candidate"
    if heat >= 45:
        return "boost_candidate"
    return "deprioritize_candidate"


def fallback_recommendation(
    title: str,
    cluster_label: str,
    summary: str,
    heat: float,
    evidence_count: int,
    posts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = build_candidate_payload(title, cluster_label, summary, posts or [])
    recommendation_type = heuristic_recommendation_type(title, cluster_label, heat)
    top_post = (posts or [{}])[0] if posts else {}
    tags = payload.get("tags", [])
    tag_text = "、".join(tags[:3]) if tags else (cluster_label or "社区趋势")
    lead_author = top_post.get("author") or "小红书用户"
    lead_title = best_post_title(select_representative_post(posts or [], cluster_label, cluster_label), payload["name"])
    trigger_reason = normalize_text(summary)[:60] if summary and not is_unusable_xhs_text(summary) else f"{tag_text} 相关内容近期互动上升。"
    community_evidence = f"{evidence_count} 篇高互动笔记聚焦“{cluster_label or payload['name']}”，代表样本包括《{lead_title}》。"
    return {
        "recommendation_type": recommendation_type,
        "candidate_name": payload["name"],
        "trigger_reason": trigger_reason,
        "community_evidence": community_evidence,
        "in_app_evidence": "请结合站内曝光、收藏、试戴完成率和预约转化复核后执行。",
        "confidence_score": max(0.35, min(0.92, round(0.45 + min(heat, 100) / 200, 2))),
        "action_text": f"建议运营围绕 {tag_text} 做选款、上新或加推，并保留人工审核。",
        "prerequisites": f"建议先确认技师可做性、库存和主图质量；样本作者参考：{lead_author}。",
        "candidate_payload": payload,
    }


class OpenClawCliAnalyzer:
    def summarize(
        self,
        title: str,
        cluster_label: str,
        summary: str,
        heat: float,
        evidence_count: int,
        posts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        candidate_payload = build_candidate_payload(title, cluster_label, summary, posts or [])
        evidence_text = "\n".join(
            f"- {item.get('title', '')}｜作者 {item.get('author', '')}｜赞 {item.get('likeCount', 0)}｜藏 {item.get('collectCount', 0)}｜评 {item.get('commentCount', 0)}"
            for item in (posts or [])[:5]
        )
        prompt = f"""
你是 Nail Mind 的美甲运营分析助手。请基于小红书趋势输入，输出一段 JSON，不要输出额外解释。

字段要求：
- recommendation_type: 只能是 launch_candidate / boost_candidate / deprioritize_candidate / delist_candidate
- candidate_name: 建议命名，15 字以内
- trigger_reason: 1 句中文，解释为什么值得关注
- community_evidence: 1 句中文，概括社区侧证据
- in_app_evidence: 1 句中文，说明要联动哪些站内指标复核
- confidence_score: 0 到 1 的数字
- action_text: 1 句中文，面向运营动作
- prerequisites: 1 句中文，说明执行前提
- candidate_payload: JSON object，必须包含 name、vibe、price、nailType、skinTone、tags、colors、imageUrl

输入：
- 标题：{title}
- 风格聚类：{cluster_label}
- 摘要：{summary}
- 社区热度：{heat}
- 高互动笔记数：{evidence_count}
- 样本笔记：
{evidence_text or "- 暂无样本"}
        """.strip()
        command = [OPENCLAW_CLI, "infer", "model", "run", "--json", "--model", OPENCLAW_MODEL, "--prompt", prompt]
        command.append("--gateway" if OPENCLAW_USE_GATEWAY else "--local")
        command.extend(OPENCLAW_EXTRA_ARGS)
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=OPENCLAW_TIMEOUT_SECONDS,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "openclaw failed").strip())
        raw_output = completed.stdout.strip()
        if not raw_output:
            raise RuntimeError("openclaw returned empty output")
        last_line = raw_output.splitlines()[-1]
        try:
            payload = json.loads(last_line)
            text = extract_text(payload) or last_line
        except json.JSONDecodeError:
            text = last_line
        try:
            parsed = extract_json_block(text)
        except Exception:
            return fallback_recommendation(
                title=title,
                cluster_label=cluster_label,
                summary=summary,
                heat=heat,
                evidence_count=evidence_count,
                posts=posts,
            )
        generated_payload = parsed.get("candidate_payload") or {}
        merged_payload = {
            **candidate_payload,
            **generated_payload,
            "imageUrl": sanitize_image_url(generated_payload.get("imageUrl")) or candidate_payload.get("imageUrl"),
            "sourcePosts": candidate_payload.get("sourcePosts", []),
        }
        candidate_name = normalize_text(parsed.get("candidate_name") or title)
        if is_unusable_xhs_text(candidate_name):
            candidate_name = candidate_payload["name"]
        trigger_reason = normalize_text(parsed["trigger_reason"])
        if is_unusable_xhs_text(trigger_reason):
            trigger_reason = fallback_recommendation(
                title=title,
                cluster_label=cluster_label,
                summary=summary,
                heat=heat,
                evidence_count=evidence_count,
                posts=posts,
            )["trigger_reason"]
        community_evidence = normalize_text(parsed["community_evidence"])
        if is_unusable_xhs_text(community_evidence):
            community_evidence = fallback_recommendation(
                title=title,
                cluster_label=cluster_label,
                summary=summary,
                heat=heat,
                evidence_count=evidence_count,
                posts=posts,
            )["community_evidence"]
        return {
            "recommendation_type": parsed["recommendation_type"],
            "candidate_name": candidate_name,
            "trigger_reason": trigger_reason,
            "community_evidence": community_evidence,
            "in_app_evidence": parsed["in_app_evidence"],
            "confidence_score": float(parsed["confidence_score"]),
            "action_text": parsed["action_text"],
            "prerequisites": parsed["prerequisites"],
            "candidate_payload": merged_payload,
        }


def collect_xiaohongshu_notes(
    keywords: list[str],
    max_posts_per_keyword: int = 8,
    headless: bool = True,
    storage_state_path: str | None = None,
) -> list[dict[str, Any]]:
    if XHS_COLLECTOR_BACKEND == "xhs_skill":
        return collect_xiaohongshu_notes_with_account_matrix(
            keywords=keywords,
            max_posts_per_keyword=max_posts_per_keyword,
        )
    if XHS_COLLECTOR_BACKEND == "spider_xhs":
        return collect_xiaohongshu_notes_with_spider_xhs(
            keywords=keywords,
            max_posts_per_keyword=max_posts_per_keyword,
        )

    return collect_xiaohongshu_notes_with_browser(
        keywords=keywords,
        max_posts_per_keyword=max_posts_per_keyword,
        headless=headless,
        storage_state_path=storage_state_path,
    )


__all__ = [
    "OpenClawCliAnalyzer",
    "build_candidate_payload",
    "collect_xiaohongshu_notes",
    "collect_xiaohongshu_notes_with_spider_xhs",
    "collect_xiaohongshu_notes_with_xhs_skill",
    "is_unusable_xhs_text",
    "is_valid_nail_post",
    "looks_like_nail_title",
    "parse_metric_text",
    "sanitize_image_url",
    "trend_post_meta",
]
