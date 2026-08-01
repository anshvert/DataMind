import logging
from typing import List

import httpx

from naturallangdata.core.config import Settings


logger = logging.getLogger(__name__)


class OpenRouterRerankerService:
    """Rerank candidate chunks via OpenRouter's rerank model endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.openrouter_base_url.rstrip("/")
        self._api_key = settings.openrouter_api_key
        self._model = settings.rerank_model
        self._site_url = settings.openrouter_site_url
        self._app_name = settings.openrouter_app_name
        self._timeout = 45.0

    def rerank(self, question: str, docs: List[dict], top_n: int) -> List[dict]:
        if not docs:
            return []

        payload = {
            "model": self._model,
            "query": question,
            "documents": [d.get("text", "") for d in docs],
            "top_n": top_n,
            # Required by many Cohere-compatible rerank providers
            "return_documents": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._site_url,
            "X-Title": self._app_name,
        }

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base_url}/rerank", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        ranked = self._parse_response(body, docs)
        return ranked[:top_n]

    def _parse_response(self, body: dict, docs: List[dict]) -> List[dict]:
        # Cohere-style shape: {"results": [{"index": 3, "relevance_score": 0.92}, ...]}
        items = body.get("results") or body.get("data") or []

        reranked: List[dict] = []
        for item in items:
            idx = item.get("index")
            if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(docs):
                continue
            doc = dict(docs[idx])
            doc["rerank_score"] = float(item.get("relevance_score", item.get("score", 0.0)))
            reranked.append(doc)

        # If provider shape changed unexpectedly, fall back to vector ranking.
        if not reranked:
            logger.warning("reranker.parse_empty_results body_keys=%s", list(body.keys()))
            return docs

        return reranked
