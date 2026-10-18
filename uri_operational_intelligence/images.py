"""Images on a working-system turn (BRAIN-QUICK-CONTROLS, Vision On).

A turn may carry `images`: [{"name": str, "mime": "image/png" | "image/jpeg" | "image/webp", "data": base64}].
The worker decodes and type-checks every image before anything reaches the Brain; the answer channel then sends
them to llama-server as OpenAI `image_url` parts (the projector of the active Vision profile encodes them).

Limits follow the worker's framed stdio protocol (`uri_core.client_contracts.FRAME_LIMIT`, 2 MiB per frame, frozen):
at most 2 images and 1.25 MiB of image bytes per turn. The UI scales pictures down to fit before it sends them.
Nothing is ever dropped silently: an image that fails a check refuses the whole turn with a code.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

MAX_IMAGES = 2
MAX_TOTAL_BYTES = 1_310_720          # 1.25 MiB decoded; base64 + JSON stay below the 2 MiB frame
MAX_NAME = 120
MAGIC = {"image/png": (b"\x89PNG\r\n\x1a\n",), "image/jpeg": (b"\xff\xd8\xff",), "image/webp": (b"RIFF",)}


class ImageRejected(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TurnImage:
    name: str
    mime: str
    data: bytes

    def data_url(self) -> str:
        return "data:%s;base64,%s" % (self.mime, base64.b64encode(self.data).decode("ascii"))


def _type_ok(mime, data) -> bool:
    if not any(data.startswith(m) for m in MAGIC[mime]):
        return False
    return mime != "image/webp" or data[8:12] == b"WEBP"


def parse(raw) -> tuple:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_IMAGES:
        raise ImageRejected("IMAGES_INVALID")
    out, total = [], 0
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"name", "mime", "data"}:
            raise ImageRejected("IMAGES_INVALID")
        name, mime, data = item["name"], item["mime"], item["data"]
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME or any(ch in name for ch in "\r\n"):
            raise ImageRejected("IMAGE_NAME_INVALID")
        if mime not in MAGIC or not isinstance(data, str):
            raise ImageRejected("IMAGE_TYPE_UNSUPPORTED")
        try:
            blob = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            raise ImageRejected("IMAGE_DATA_INVALID") from None
        total += len(blob)
        if not blob or total > MAX_TOTAL_BYTES:
            raise ImageRejected("IMAGES_TOO_LARGE")
        if not _type_ok(mime, blob):
            raise ImageRejected("IMAGE_TYPE_MISMATCH")
        out.append(TurnImage(name.strip(), mime, blob))
    return tuple(out)


def placeholder(img: TurnImage) -> str:
    """What the conversation history keeps instead of the image (never the bytes)."""
    return "[Attached image: %s]" % img.name


def user_content(text: str, images) -> list | str:
    """The user message content for the Brain: text first, then the images as `image_url` parts."""
    if not images:
        return text
    return [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": i.data_url()}}
                                               for i in images]
