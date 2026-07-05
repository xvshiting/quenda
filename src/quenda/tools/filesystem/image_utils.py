"""
Image utilities for multimodal support.

Provides image reading, compression, and token estimation.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from quenda.kernel.types import ImageContent


# Supported image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# Media type mapping
EXTENSION_TO_MEDIA_TYPE = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def is_image_file(path: Path | str) -> bool:
    """Check if a file path is an image based on extension."""
    ext = Path(path).suffix.lower()
    return ext in IMAGE_EXTENSIONS


def infer_media_type(path: Path | str) -> str:
    """Infer media type from file extension."""
    ext = Path(path).suffix.lower()
    return EXTENSION_TO_MEDIA_TYPE.get(ext, "image/png")


def get_image_dimensions(data: bytes) -> tuple[int, int]:
    """Get image dimensions (width, height) from raw bytes."""
    img = Image.open(io.BytesIO(data))
    return img.size


def estimate_image_tokens(width: int, height: int) -> int:
    """
    Estimate token count for an image.

    Uses approximate formula based on Anthropic's token calculation.
    Roughly: tokens ≈ (width * height) / 750
    """
    return (width * height) // 750


def resize_image_for_tokens(
    data: bytes,
    max_tokens: int = 4000,
    min_dimension: int = 200,
) -> bytes:
    """
    Resize image to fit within token budget.

    Args:
        data: Raw image bytes
        max_tokens: Maximum allowed tokens for the image
        min_dimension: Minimum dimension (width or height) to maintain

    Returns:
        Resized image bytes in JPEG format
    """
    img = Image.open(io.BytesIO(data))
    width, height = img.size

    # Check if resizing is needed
    current_tokens = estimate_image_tokens(width, height)
    if current_tokens <= max_tokens:
        return data

    # Calculate scale factor
    scale = (max_tokens * 750 / (width * height)) ** 0.5

    # Calculate new dimensions
    new_width = max(min_dimension, int(width * scale))
    new_height = max(min_dimension, int(height * scale))

    # Resize image
    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Convert to RGB if necessary (for JPEG output)
    if resized.mode in ("RGBA", "P"):
        resized = resized.convert("RGB")

    # Save as JPEG (good compression)
    output = io.BytesIO()
    resized.save(output, format="JPEG", quality=85)
    return output.getvalue()


def read_image_file(path: Path, max_tokens: int = 4000) -> ImageContent:
    """
    Read an image file and return ImageContent.

    Args:
        path: Path to the image file
        max_tokens: Maximum tokens allowed for the image

    Returns:
        ImageContent with base64-encoded image data
    """
    raw_data = path.read_bytes()

    # Resize if needed
    processed_data = resize_image_for_tokens(raw_data, max_tokens)

    # Get final dimensions
    width, height = get_image_dimensions(processed_data)

    # Encode to base64
    base64_data = base64.b64encode(processed_data).decode("utf-8")

    # Use JPEG media type after processing
    return ImageContent(
        media_type="image/jpeg",
        data=base64_data,
    )


def read_image_url(url: str, max_tokens: int = 4000) -> ImageContent:
    """
    Read an image from URL and return ImageContent.

    For URLs, we have two options:
    1. Pass URL directly to the model (some models support this)
    2. Download and encode as base64

    This implementation downloads and encodes for broader compatibility.

    Args:
        url: URL of the image
        max_tokens: Maximum tokens allowed for the image

    Returns:
        ImageContent with base64-encoded image data
    """
    import httpx

    # Download image
    response = httpx.get(url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    raw_data = response.content

    # Resize if needed
    processed_data = resize_image_for_tokens(raw_data, max_tokens)

    # Encode to base64
    base64_data = base64.b64encode(processed_data).decode("utf-8")

    return ImageContent(
        media_type="image/jpeg",
        data=base64_data,
    )


__all__ = [
    "IMAGE_EXTENSIONS",
    "is_image_file",
    "infer_media_type",
    "get_image_dimensions",
    "estimate_image_tokens",
    "resize_image_for_tokens",
    "read_image_file",
    "read_image_url",
]