"""Embedding node — chunks → dense vectors."""
from typing import Callable, List

from naturallangdata.agents.state import IngestionState


def make_embed_chunks_node(embed_fn: Callable[[List[str]], List[List[float]]]):
    def embed_chunks_node(state: IngestionState) -> IngestionState:
        try:
            embeddings = embed_fn(state["chunks"])
            return {**state, "embeddings": embeddings, "status": "ingesting"}
        except Exception as exc:
            return {**state, "status": "error", "error": f"embedding failed: {exc}"}

    return embed_chunks_node
