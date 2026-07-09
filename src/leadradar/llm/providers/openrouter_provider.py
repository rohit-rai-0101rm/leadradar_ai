import httpx

from leadradar.llm.providers.base import AuthError, Provider, RateLimitError

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(Provider):
    name = "openrouter"

    def complete(self, prompt: str) -> str:
        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if response.status_code == 429:
            raise RateLimitError(f"openrouter key rate-limited: {response.text}")
        if response.status_code in (401, 403):
            raise AuthError(f"openrouter key auth failed: {response.text}")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
