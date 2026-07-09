from pydantic import BaseModel


class CompletionRequest(BaseModel):
    prompt: str
    image_base64: str | None = None


class CompletionResponse(BaseModel):
    text: str
    provider: str
    model: str
