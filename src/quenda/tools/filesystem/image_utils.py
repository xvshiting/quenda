"""
Image utilities for multimodal support.

Provides image reading, compression, and token estimation.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from quenda.kernel.types import ImageContent
from quenda.tools.security.validation import validate_url


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

# Allowed image media types (for URL validation)
ALLOWED_IMAGE_MEDIA_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/gif",
    "image/webp",
    "image/bmp",
}

# Maximum image download size (10 MB)
MAX_IMAGE_DOWNLOAD_SIZE = 10 * 1024 * 1024


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


@dataclass
class ProcessedImage:
    """Result of image processing with metadata."""

    data: bytes
    media_type: str  # Actual media type after processing
    width: int
    height: int
    was_resized: bool


def resize_image_for_tokens(
    data: bytes,
    max_tokens: int = 4000,
    min_dimension: int = 200,
) -> ProcessedImage:
    """
    Resize image to fit within token budget.

    Args:
        data: Raw image bytes
        max_tokens: Maximum allowed tokens for the image
        min_dimension: Minimum dimension (width or height) to maintain

    Returns:
        ProcessedImage with resized bytes in JPEG format (if resize needed),
        or original data if no resize was needed.
    """
    img = Image.open(io.BytesIO(data))
    width, height = img.size

    # Check if resizing is needed
    current_tokens = estimate_image_tokens(width, height)
    if current_tokens <= max_tokens:
        # No resize needed, return original
        return ProcessedImage(
            data=data,
            media_type=_detect_media_type(data, img),
            width=width,
            height=height,
            was_resized=False,
        )

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
    return ProcessedImage(
        data=output.getvalue(),
        media_type="image/jpeg",
        width=new_width,
        height=new_height,
        was_resized=True,
    )


def _detect_media_type(data: bytes, img: Image.Image | None = None) -> str:
    """
    Detect media type from image data.

    Args:
        data: Raw image bytes
        img: Optional PIL Image object (to avoid re-opening)

    Returns:
        Media type string (e.g., "image/png", "image/jpeg")
    """
    if img is None:
        img = Image.open(io.BytesIO(data))

    format_name = img.format
    if format_name == "PNG":
        return "image/png"
    elif format_name in ("JPEG", "JPG"):
        return "image/jpeg"
    elif format_name == "GIF":
        return "image/gif"
    elif format_name == "WEBP":
        return "image/webp"
    elif format_name == "BMP":
        return "image/bmp"
    else:
        return "image/png"  # Default fallback


def read_image_file(path: Path, max_tokens: int = 4000) -> ImageContent:
    """
    Read an image file and return ImageContent.

    Args:
        path: Path to the image file
        max_tokens: Maximum tokens allowed for the image

    Returns:
        ImageContent with base64-encoded image data and correct media type.
    """
    raw_data = path.read_bytes()

    # Process image (resize if needed)
    processed = resize_image_for_tokens(raw_data, max_tokens)

    # Encode to base64
    base64_data = base64.b64encode(processed.data).decode("utf-8")

    return ImageContent(
        media_type=processed.media_type,
        data=base64_data,
    )


class ImageDownloadError(Exception):
    """Error downloading image."""
    pass


def read_image_url(url: str, max_tokens: int = 4000) -> ImageContent:
    """
    Read an image from URL and return ImageContent.

    For URLs, we have two options:
    1. Pass URL directly to the model (some models support this)
    2. Download and encode as base64

    This implementation downloads and encodes for broader compatibility.

    Security measures:
    - SSRF protection via URL validation
    - Maximum download size limit
    - Content-Type validation
    - Redirect validation

    Args:
        url: URL of the image
        max_tokens: Maximum tokens allowed for the image

    Returns:
        ImageContent with base64-encoded image data and correct media type.

    Raises:
        ImageDownloadError: If download fails or security check fails.
    """
    import httpx

    # SSRF protection: validate URL before downloading
    error = validate_url(url)
    if error:
        raise ImageDownloadError(f"URL validation failed: {error}")

    try:
        # Download with size limit
        with httpx.stream("GET", url, timeout=30.0, follow_redirects=False) as response:
            # Check response status
            if response.status_code >= 400:
                raise ImageDownloadError(f"HTTP error {response.status_code}")

            # Validate Content-Type
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and content_type not in ALLOWED_IMAGE_MEDIA_TYPES:
                raise ImageDownloadError(
                    f"Invalid content type: {content_type}. "
                    f"Expected one of: {', '.join(sorted(ALLOWED_IMAGE_MEDIA_TYPES))}"
                )

            # Handle redirects with validation
            redirect_count = 0
            max_redirects = 5
            current_url = url

            while response.is_redirect and redirect_count < max_redirects:
                redirect_url = response.headers.get("location")
                if not redirect_url:
                    break

                # Resolve relative redirect
                if not redirect_url.startswith(("http://", "https://")):
                    from urllib.parse import urljoin
                    redirect_url = urljoin(current_url, redirect_url)

                # Validate redirect URL
                error = validate_url(redirect_url)
                if error:
                    raise ImageDownloadError(f"Redirect blocked: {error}")

                current_url = redirect_url
                response = httpx.stream("GET", current_url, timeout=30.0, follow_redirects=False)
                redirect_count += 1

            # Download with size limit
            chunks = []
            total_size = 0
            for chunk in response.iter_bytes(chunk_size=8192):
                total_size += len(chunk)
                if total_size > MAX_IMAGE_DOWNLOAD_SIZE:
                    raise ImageDownloadError(
                        f"Image too large: {total_size} bytes exceeds limit of {MAX_IMAGE_DOWNLOAD_SIZE} bytes"
                    )
                chunks.append(chunk)

            raw_data = b"".join(chunks)

    except httpx.TimeoutException:
        raise ImageDownloadError("Request timed out")
    except httpx.RequestError as e:
        raise ImageDownloadError(f"Request failed: {e}")

    # Process image (resize if needed)
    processed = resize_image_for_tokens(raw_data, max_tokens)

    # Encode to base64
    base64_data = base64.b64encode(processed.data).decode("utf-8")

    return ImageContent(
        media_type=processed.media_type,
        data=base64_data,
    )


__all__ = [
    "IMAGE_EXTENSIONS",
    "ALLOWED_IMAGE_MEDIA_TYPES",
    "ProcessedImage",
    "ImageDownloadError",
    "is_image_file",
    "infer_media_type",
    "get_image_dimensions",
    "estimate_image_tokens",
    "resize_image_for_tokens",
    "read_image_file",
    "read_image_url",
]