"""
LLM Client — OpenAI-compatible wrapper for NVIDIA API (integrate.api.nvidia.com).
"""

from openai import OpenAI
from config import config


_client = OpenAI(
    api_key=config.NVIDIA_API_KEY,
    base_url=config.NVIDIA_BASE_URL,
)


def call_llm(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Send a chat completion request and return the text response."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = _client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            temperature=temperature,
            top_p=1,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return f"Error: {e}"


def call_llm_with_history(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Send a multi-turn chat completion request."""
    try:
        response = _client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=messages,
            temperature=temperature,
            top_p=1,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return f"Error: {e}"
