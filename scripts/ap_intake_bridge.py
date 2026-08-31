"""Pure helpers for the AP Discord -> GAS antique intake bridge.

CHANGE GAS-LOCAL-BRIDGE: keep Discord I/O local after Discord error 40333 while
GAS remains the only Gemini/Drive/Sheets authority.  This module contains no
Discord client and no network calls so compression and payload limits can be
tested deterministically.
"""

from __future__ import annotations

import base64
import io
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGES_PER_ARTIFACT = 8
DEFAULT_MAX_DIMENSION = 2200
MIN_LONG_EDGE = 960
DEFAULT_PER_IMAGE_BYTES = 2_500_000
MAX_COMPRESSED_TOTAL_BYTES = 12 * 1024 * 1024
MAX_GAS_JSON_BYTES = 18 * 1024 * 1024
MAX_SOURCE_IMAGE_BYTES = 30 * 1024 * 1024
ALLOWED_SOURCE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
GAS_EXEC_URL_RE = re.compile(r"^https://script\.google\.com/macros/s/[^/]+/exec$")


class BridgeInputError(ValueError):
    """Input cannot safely enter the GAS bridge."""


@dataclass(frozen=True)
class PreparedImage:
    attachment_id: str
    filename: str
    mime_type: str
    data: bytes
    original_bytes: int
    width: int
    height: int
    quality: int

    def to_payload(self) -> dict[str, str]:
        return {
            "attachmentId": self.attachment_id,
            "filename": self.filename,
            "mimeType": self.mime_type,
            "imageBase64": base64.b64encode(self.data).decode("ascii"),
        }


def safe_image_filename(filename: str, index: int) -> str:
    stem = Path(str(filename or "")).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    if not stem:
        stem = f"antique_{index}"
    return f"{stem[:80]}.jpg"


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _resize_long_edge(image: Image.Image, max_dimension: int) -> Image.Image:
    long_edge = max(image.size)
    if long_edge <= max_dimension:
        return image
    scale = max_dimension / long_edge
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(target, Image.Resampling.LANCZOS)


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling="4:2:0",
    )
    return output.getvalue()


def compress_image_bytes(
    source: bytes,
    *,
    attachment_id: str,
    filename: str,
    index: int,
    target_bytes: int = DEFAULT_PER_IMAGE_BYTES,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    max_source_bytes: int = MAX_SOURCE_IMAGE_BYTES,
) -> PreparedImage:
    """Normalize one image to bounded JPEG bytes while removing EXIF metadata."""
    if not source:
        raise BridgeInputError(f"第 {index} 張圖片是空檔案")
    if len(source) > max_source_bytes:
        raise BridgeInputError(
            f"第 {index} 張原圖 {len(source)} bytes，超過本地安全上限 {max_source_bytes}"
        )
    target_bytes = max(350_000, min(int(target_bytes), DEFAULT_PER_IMAGE_BYTES))
    max_dimension = max(MIN_LONG_EDGE, min(int(max_dimension), 4000))

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(source)) as opened:
                opened.load()
                if opened.width * opened.height > 50_000_000:
                    raise BridgeInputError(f"第 {index} 張圖片像素數過大")
                image = _resize_long_edge(_flatten_to_rgb(ImageOps.exif_transpose(opened)), max_dimension)
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise BridgeInputError(f"第 {index} 張不是可安全解碼的圖片") from exc

    qualities = (88, 82, 76, 70, 64, 58, 52, 46)
    encoded = b""
    selected_quality = qualities[-1]
    while True:
        for quality in qualities:
            encoded = _encode_jpeg(image, quality)
            selected_quality = quality
            if len(encoded) <= target_bytes:
                return PreparedImage(
                    attachment_id=str(attachment_id or ""),
                    filename=safe_image_filename(filename, index),
                    mime_type="image/jpeg",
                    data=encoded,
                    original_bytes=len(source),
                    width=image.width,
                    height=image.height,
                    quality=selected_quality,
                )
        if max(image.size) <= MIN_LONG_EDGE:
            break
        next_long_edge = max(MIN_LONG_EDGE, round(max(image.size) * 0.82))
        image = _resize_long_edge(image, next_long_edge)

    raise BridgeInputError(
        f"第 {index} 張壓縮後仍有 {len(encoded)} bytes，超過單圖上限 {target_bytes}"
    )


def per_image_budget(image_count: int) -> int:
    if image_count < 1 or image_count > MAX_IMAGES_PER_ARTIFACT:
        raise BridgeInputError(f"同一藏品圖片數須為 1–{MAX_IMAGES_PER_ARTIFACT}")
    return min(DEFAULT_PER_IMAGE_BYTES, MAX_COMPRESSED_TOTAL_BYTES // image_count)


def build_ingest_payload(
    images: Iterable[PreparedImage],
    *,
    ingest_secret: str,
    caption: str,
    message_id: str,
    channel_id: str,
    user_id: str,
    user_name: str,
) -> tuple[dict[str, object], int]:
    prepared = list(images)
    if not ingest_secret:
        raise BridgeInputError("缺少 AP_INGEST_SECRET")
    if not message_id:
        raise BridgeInputError("缺少 Discord messageId，拒絕無冪等鍵的請求")
    if not 1 <= len(prepared) <= MAX_IMAGES_PER_ARTIFACT:
        raise BridgeInputError(f"同一藏品圖片數須為 1–{MAX_IMAGES_PER_ARTIFACT}")
    compressed_total = sum(len(image.data) for image in prepared)
    if compressed_total > MAX_COMPRESSED_TOTAL_BYTES:
        raise BridgeInputError(
            f"壓縮圖片總量 {compressed_total} bytes，超過 {MAX_COMPRESSED_TOTAL_BYTES}"
        )
    payload: dict[str, object] = {
        "bridgeVersion": "AP-local-bridge-v3.0",
        "ingestSecret": ingest_secret,
        "caption": str(caption or "無描述")[:800],
        "messageId": str(message_id),
        "channelId": str(channel_id),
        "userId": str(user_id),
        "userName": str(user_name)[:100],
        "images": [image.to_payload() for image in prepared],
    }
    request_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if request_bytes > MAX_GAS_JSON_BYTES:
        raise BridgeInputError(
            f"GAS JSON request {request_bytes} bytes，超過安全上限 {MAX_GAS_JSON_BYTES}"
        )
    return payload, request_bytes


def validate_bridge_config(bot_token: str, gas_url: str, ingest_secret: str) -> None:
    missing = [
        name
        for name, value in (
            ("DISCORD_BOT_TOKEN", bot_token),
            ("AP_GAS_DOPOST_URL", gas_url),
            ("AP_INGEST_SECRET", ingest_secret),
        )
        if not str(value or "").strip()
    ]
    if missing:
        raise RuntimeError("缺少必要設定：" + ", ".join(missing))
    if not GAS_EXEC_URL_RE.fullmatch(str(gas_url).strip()):
        raise RuntimeError("AP_GAS_DOPOST_URL 必須是正式 Apps Script /exec URL")
    if str(bot_token).strip().lower().startswith("bot "):
        raise RuntimeError("DISCORD_BOT_TOKEN 只能放原始 token，不可包含 Bot 前綴")
    if len(str(ingest_secret).strip()) < 24:
        raise RuntimeError("AP_INGEST_SECRET 至少需 24 字元")
