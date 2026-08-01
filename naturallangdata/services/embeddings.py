import asyncio
from typing import List

import httpx

from naturallangdata.core.config import Settings


class EmbeddingsService:
    """Thin wrapper around the OpenRouter embedding endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.openrouter_base_url.rstrip("/")
        self._api_key = settings.openrouter_api_key
        self._model = settings.embedding_model
        self._site_url = settings.openrouter_site_url
        self._app_name = settings.openrouter_app_name
        self._timeout = 45.0

    def _embed_one(self, text: str) -> List[float]:
        payload = {
            "model": self._model,
            "input": text,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url,
            "X-Title": self._app_name,
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base_url}/embeddings", json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = response.text
                raise RuntimeError(
                    f"embedding request failed ({response.status_code}): {detail}"
                ) from exc

            body = response.json()

        data = body.get("data") or []
        if not data or "embedding" not in data[0]:
            raise RuntimeError(f"embedding response missing vector data: {body}")

        return [float(x) for x in data[0]["embedding"]]

    def embed_query(self, text: str) -> List[float]:
        value = text if isinstance(text, str) else str(text)
        return self._embed_one(value)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            value = text if isinstance(text, str) else str(text)
            vectors.append(self._embed_one(value))
        return vectors

    # ── async variants (for non-blocking use inside async route handlers) ─────
    async def aembed_query(self, text: str) -> List[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)
