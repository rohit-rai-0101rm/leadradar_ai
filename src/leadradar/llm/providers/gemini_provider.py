import httpx

from leadradar.llm.providers.base import AuthError, Provider, RateLimitError

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(Provider):
    name = "gemini"

    def complete(self, prompt: str, image_base64: str | None = None) -> str:
        parts = [{"text": prompt}]
        if image_base64 is not None:
            parts.append({"inline_data": {"mime_type": "image/png", "data": image_base64}})

        response = httpx.post(
            GEMINI_URL.format(model=self.model),
            params={"key": self.key},
            json={"contents": [{"parts": parts}]},
            timeout=30,
        )
        if response.status_code == 429:
            raise RateLimitError(f"gemini key rate-limited: {response.text}")
        if response.status_code in (401, 403):
            raise AuthError(f"gemini key auth failed: {response.text}")
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
