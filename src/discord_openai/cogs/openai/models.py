from typing import Any, Protocol

from ...util import (
    ImageGenerationParameters,
    ResearchParameters,
    ResponseParameters,
    TextToSpeechParameters,
    VideoGenerationParameters,
)


class PermissionAwareChannel(Protocol):
    def permissions_for(self, member: Any) -> Any: ...


__all__ = [
    "ImageGenerationParameters",
    "PermissionAwareChannel",
    "ResearchParameters",
    "ResponseParameters",
    "TextToSpeechParameters",
    "VideoGenerationParameters",
]
