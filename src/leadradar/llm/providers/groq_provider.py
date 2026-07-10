import httpx

from leadradar.llm.providers.base import (
    AuthError,
    Provider,
    ProviderError,
    RateLimitError,
    openai_style_content,
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(Provider):
    name = "groq"

    def complete(self, prompt: str, image_base64: str | None = None) -> str:
        response = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "user", "content": openai_style_content(prompt, image_base64)}
                ],
            },
            timeout=30,
        )
        if response.status_code == 429:
            raise RateLimitError(f"groq key rate-limited: {response.text}")
        if response.status_code in (401, 403):
            raise AuthError(f"groq key auth failed: {response.text}")
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ProviderError(f"groq response missing choices: {data}")
        return choices[0]["message"]["content"]
