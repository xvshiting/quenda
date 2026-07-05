"""
Multimodal helpers for Quenda runtime and CLI layers.

These helpers keep image loading and user-message assembly consistent across
one-shot runs, sessions, and REPL flows.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from pathlib import Path

from quenda.kernel.types import ImageContent, TextContent


def infer_media_type(path: str) -> str:
    """Infer a media type from the file extension."""
    ext = Path(path).suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(ext, "image/png")


def load_images(image_paths: Sequence[str]) -> list[ImageContent]:
    """Load local image files into `ImageContent` blocks."""
    images: list[ImageContent] = []
    for path in image_paths:
        img_path = Path(path).expanduser()
        if not img_path.exists():
            continue

        with open(img_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        images.append(
            ImageContent(
                media_type=infer_media_type(path),
                data=data,
            )
        )

    return images


def build_user_message(
    text: str,
    images: Sequence[ImageContent] | None = None,
) -> str | Sequence[TextContent | ImageContent]:
    """Build a user message from text and optional image blocks."""
    if not images:
        return text

    content: list[TextContent | ImageContent] = [TextContent(text=text)]
    content.extend(images)
    return content

