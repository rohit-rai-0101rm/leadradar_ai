import httpx

from leadradar.llm.providers.base import AuthError, Provider, RateLimitError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(Provider):
    name = "groq"

    def complete(self, prompt: str) -> str:
        response = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if response.status_code == 429:
            raise RateLimitError(f"groq key rate-limited: {response.text}")
        if response.status_code in (401, 403):
            raise AuthError(f"groq key auth failed: {response.text}")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
