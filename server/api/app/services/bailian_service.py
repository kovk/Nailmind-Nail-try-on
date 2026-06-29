from __future__ import annotations

import base64
from pathlib import Path

import requests

from ..config import get_settings


DASHSCOPE_MODEL = "qwen-image-2.0-pro"
DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"


def _image_to_data_uri(filepath: str) -> str:
    path = Path(filepath)
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")
    payload = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{payload}"


def normalize_tryon_error_message(raw_message: str) -> str:
    message = (raw_message or "").strip()
    lowered = message.lower()
    if "overdue-payment" in lowered or "access denied" in lowered or "good standing" in lowered:
        return "AI 试戴服务当前不可用，请检查百炼账号余额或支付状态后重试。"
    if "missing dashscope_api_key" in lowered:
        return "AI 试戴服务尚未配置可用密钥，请联系管理员检查服务配置。"
    if "http-429" in lowered or "rate limit" in lowered:
        return "当前试戴请求较多，请稍后再试。"
    if "timeout" in lowered:
        return "AI 试戴生成超时，请稍后再试。"
    if "http-5" in lowered:
        return "AI 试戴服务暂时异常，请稍后再试。"
    return message or "AI 试戴服务暂时不可用，请稍后再试。"


def generate_tryon_image(hand_path: str, style_path: str, output_path: str) -> tuple[bool, str]:
    settings = get_settings()
    output = Path(output_path)
    if output.exists() and output.stat().st_size > 1000:
        return True, "cached"

    prompt = (
        "你是专业美甲试戴修图师。第一张图是用户真实手部照片，第二张图只作为美甲款式参考。"
        "仅修改第一张图中已经存在的可见指甲甲面，把第二张图的颜色、纹理、图案、亮片、猫眼、渐变或装饰风格转移到这些甲面上。"
        "必须完整保留第一张图的手部结构、手指数量、指甲位置、轮廓、长度、朝向、肤色、皮肤纹理、背景、光线、构图和画幅。"
        "禁止新增手指、删除手指、合并手指、改变手掌形状，禁止复制第二张图中的手、皮肤、背景和姿势。"
        "输出自然写实，不要添加文字、边框、贴纸、水印或说明。"
    )
    payload = {
        "model": DASHSCOPE_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": _image_to_data_uri(hand_path)},
                        {"image": _image_to_data_uri(style_path)},
                        {"text": prompt},
                    ],
                }
            ]
        },
        "parameters": {"n": 1, "prompt_extend": True, "watermark": False},
    }
    if not settings.dashscope_api_key:
        return False, "missing DASHSCOPE_API_KEY"

    headers = {"Authorization": f"Bearer {settings.dashscope_api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(DASHSCOPE_API_URL, json=payload, headers=headers, timeout=120)
        data = response.json()
        if response.status_code != 200 or "output" not in data:
            raw_message = data.get("message", data.get("code", f"http-{response.status_code}"))
            return False, normalize_tryon_error_message(str(raw_message))

        image_url = data["output"]["choices"][0]["message"]["content"][0]["image"]
        image_response = requests.get(image_url, timeout=60)
        image_response.raise_for_status()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_response.content)
        return True, "generated"
    except Exception as exc:
        return False, normalize_tryon_error_message(str(exc))
