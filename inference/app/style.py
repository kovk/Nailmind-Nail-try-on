from __future__ import annotations

from collections import Counter
from io import BytesIO

from PIL import Image, ImageOps


class StyleExtractor:
    def describe(self, image_bytes: bytes) -> str:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((256, 256))
        colors = self._dominant_color_words(image)
        return "、".join(colors) if colors else "自然通透美甲"

    def _dominant_color_words(self, image: Image.Image) -> list[str]:
        pixels = list(image.getdata())
        if not pixels:
            return []
        buckets: Counter[str] = Counter()
        for r, g, b in pixels[:: max(1, len(pixels) // 5000)]:
            brightness = (r + g + b) / 3
            saturation = max(r, g, b) - min(r, g, b)
            if brightness > 235 and saturation < 20:
                continue
            buckets[self._color_word(r, g, b)] += 1
        return [name for name, _ in buckets.most_common(4) if name != "自然肤色"]

    @staticmethod
    def _color_word(r: int, g: int, b: int) -> str:
        if r < 45 and g < 45 and b < 45:
            return "黑色"
        if r > 210 and g > 210 and b > 210:
            return "白色"
        if abs(r - g) < 18 and abs(g - b) < 18:
            return "银灰"
        if r > 180 and g < 100 and b < 110:
            return "红色"
        if r > 190 and g > 120 and b > 135:
            return "裸粉"
        if r > 180 and g > 130 and b < 95:
            return "焦糖棕"
        if b > r + 30 and b > g + 15:
            return "蓝色"
        if g > r + 20 and g > b + 15:
            return "绿色"
        if r > 145 and b > 130 and g < 130:
            return "紫色"
        return "自然肤色"
