from openai import AsyncOpenAI

from ...config import OPENAI_API_KEY


def build_openai_client() -> AsyncOpenAI:
    """Construct the repo-standard OpenAI client."""
    return AsyncOpenAI(api_key=OPENAI_API_KEY)
