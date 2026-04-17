from openai import AsyncOpenAI

from ...config import OPENAI_API_KEY

MAX_API_ATTEMPTS = 5
API_TIMEOUT_SECONDS = 300.0


def build_openai_client() -> AsyncOpenAI:
    """Construct the repo-standard OpenAI client.

    The SDK's built-in retry policy is raised from its default (2 attempts) to
    MAX_API_ATTEMPTS so transient 429/5xx/connection errors recover transparently.
    """
    return AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        max_retries=MAX_API_ATTEMPTS - 1,
        timeout=API_TIMEOUT_SECONDS,
    )
