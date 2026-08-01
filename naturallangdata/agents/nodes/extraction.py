"""Text extraction node — document path → raw text."""
from pathlib import Path
from typing import Callable

from naturallangdata.agents.state import IngestionState


def make_extract_text_node(extract_text_fn: Callable[[Path], str]):
    def extract_text_node(state: IngestionState) -> IngestionState:
        try:
            text = extract_text_fn(Path(state["file_path"]))
            if not text.strip():
                return {**state, "status": "error", "error": "No text could be extracted from the document"}
            return {**state, "raw_text": text, "status": "chunking"}
        except Exception as exc:
            return {**state, "status": "error", "error": f"text extraction failed: {exc}"}

    return extract_text_node
