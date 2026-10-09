from discord import Attachment

from ...util import (
    IMAGE_CONTENT_TYPES,
    build_attachment_content_block,
    build_input_content,
    estimate_audio_duration_seconds,
    fetch_attachment_bytes,
)


def validate_image_attachment(attachment: Attachment | None) -> str | None:
    if attachment is None:
        return None
    mime = (attachment.content_type or "").split(";")[0].strip()
    if mime in IMAGE_CONTENT_TYPES:
        return None
    return f"Attachment must be an image (PNG, JPEG, GIF, WebP), got `{mime or 'unknown'}`."


__all__ = [
    "IMAGE_CONTENT_TYPES",
    "build_attachment_content_block",
    "build_input_content",
    "estimate_audio_duration_seconds",
    "fetch_attachment_bytes",
    "validate_image_attachment",
]
