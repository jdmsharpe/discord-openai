from typing import List, Optional


class ChatCompletionParameters:
    def __init__(
        self,
        messages: List[str] = [],
        model: str = "gpt-4-turbo",
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        seed: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        thread_owner: Optional[str] = None,
    ):
        self.messages = messages
        self.model = model
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.seed = seed
        self.temperature = temperature
        self.top_p = top_p
        self.thread_owner = thread_owner

    def to_dict(self):
        return {
            "messages": self.messages,
            "model": self.model,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "seed": self.seed,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "thread_owner": self.thread_owner,
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
        input: str,
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
