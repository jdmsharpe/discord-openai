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
