import base64
import logging
from pathlib import Path

import fitz
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pypdf import PdfReader

from naturallangdata.core.config import Settings


logger = logging.getLogger(__name__)


VISION_SYSTEM_PROMPT = (
    "You are a document OCR assistant. Extract every piece of readable text from the given page image. "
    "Include headings, labels, bullet points, table cells, flowchart node text, and side notes. "
    "Return plain text only with clean structure. Do not add explanations."
)


class PDFExtractionService:
    """Hybrid PDF extractor: native PDF text + vision fallback for image-heavy pages."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._vision_llm = ChatOpenAI(
            model=settings.vision_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.openrouter_app_name,
            },
        )

    def extract(self, pdf_path: Path) -> str:
        reader = PdfReader(str(pdf_path))
        doc = fitz.open(str(pdf_path))

        page_text_blocks: list[str] = []

        for idx, page in enumerate(reader.pages):
            native_text = (page.extract_text() or "").strip()
            has_images = False
            try:
                has_images = len(page.images) > 0
            except Exception:
                has_images = False

            needs_vision = has_images or len(native_text) < self._settings.pdf_vision_min_text_chars
            vision_text = ""

            if needs_vision and idx < len(doc):
                vision_text = self._extract_page_via_vision(doc[idx], idx + 1)

            combined = self._merge_page_text(native_text=native_text, vision_text=vision_text)
            if combined:
                page_text_blocks.append(f"[PAGE {idx + 1}]\n{combined}")

        doc.close()
        return "\n\n".join(page_text_blocks)

    def _extract_page_via_vision(self, page: fitz.Page, page_number: int) -> str:
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_bytes = pix.tobytes("png")
            b64 = base64.b64encode(image_bytes).decode("utf-8")

            response = self._vision_llm.invoke(
                [
                    SystemMessage(content=VISION_SYSTEM_PROMPT),
                    HumanMessage(
                        content=[
                            {"type": "text", "text": f"Extract all text from this PDF page image (page {page_number})."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ]
                    ),
                ]
            )
            text = response.content if hasattr(response, "content") else str(response)
            logger.info("pdf.vision_extraction page=%d chars=%d", page_number, len(text or ""))
            return (text or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("pdf.vision_extraction_failed page=%d error=%s", page_number, exc)
            return ""

    @staticmethod
    def _merge_page_text(native_text: str, vision_text: str) -> str:
        native = (native_text or "").strip()
        vision = (vision_text or "").strip()
        if native and vision:
            return f"{native}\n\n[EXTRACTED_FROM_PAGE_IMAGE]\n{vision}"
        return native or vision
