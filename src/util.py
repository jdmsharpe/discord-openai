import re
from typing import List, Optional


class ChatCompletionParameters:
    def __init__(
        self,
        messages: List[dict] = [],
        model: str = "gpt-4o",
        persona: str = "You are a helpful assistant.",
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        conversation_starter: Optional[str] = None,
        conversation_id: Optional[str] = None,
        conversation_channel: Optional[str] = None,
    ):
        self.messages = messages
        self.model = model
        self.persona = persona
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.seed = seed
        self.temperature = temperature
        self.top_p = top_p
        self.conversation_starter = conversation_starter
        self.conversation_id = conversation_id
        self.conversation_channel = conversation_channel

    def to_dict(self):
        # Create a copy of messages to avoid mutating original list
        messages_copy = [msg.copy() for msg in self.messages]
        for message in messages_copy:
            if "content" in message:
                # Ensure content is a list of dictionaries if not already
                if not isinstance(message["content"], list):
                    message["content"] = [message["content"]]

        return {
            "messages": messages_copy,
            "model": self.model,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "seed": self.seed,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }


class ImageGenerationParameters:
    def __init__(
        self,
        prompt: str = "",
        model: str = "dall-e-3",
        n: int = 1,
        quality: str = "standard",
        size: str = "1024x1024",
        style: Optional[str] = None,
    ):
        self.prompt = prompt
        self.model = model
        self.n = n
        self.quality = quality
        self.size = size
        self.style = style

    def to_dict(self):
        return {
            "prompt": self.prompt,
            "model": self.model,
            "n": self.n,
            "quality": self.quality,
            "size": self.size,
            "style": self.style,
        }


class TextToSpeechParameters:
    def __init__(
        self,
        input: str = "",
        model: str = "tts-1",
        voice: str = "alloy",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        self.input = input
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.speed = speed

    def to_dict(self):
        return {
            "input": self.input,
            "model": self.model,
            "voice": self.voice,
            "response_format": self.response_format,
            "speed": self.speed,
        }


def chunk_text(text, size):
    """Yield successive size chunks from text."""
    for i in range(0, len(text), size):
        yield list(text[i : i + size])


def extract_urls(text):
    url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    urls = re.findall(url_pattern, text)
    return urls
