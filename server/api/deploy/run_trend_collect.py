from __future__ import annotations

import json
import urllib.request


BASE_URL = "http://127.0.0.1:8080"


def post_json(path: str, payload: dict, token: str | None = None, timeout: int = 30) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    login = post_json(
        "/admin/auth/login",
        {"email": "operator@nailmind.app", "password": "123456"},
        timeout=20,
    )
    token = login["token"]
    result = post_json(
        "/admin/trends/collect",
        {
            "keywords": ["法式美甲", "猫眼美甲", "新中式美甲"],
            "maxPostsPerKeyword": 3,
            "headless": True,
        },
        token=token,
        timeout=300,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
