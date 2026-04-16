"""PDF processor using Docling with GLM-OCR and pdfplumber fallbacks."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from pathlib import Path

import aiohttp
from pdf2image import convert_from_path

from aily.chaos.processors.base import ContentProcessor
from aily.chaos.types import ExtractedContentMultimodal, VisualElement

logger = logging.getLogger(__name__)


class PDFProcessor(ContentProcessor):
    """Process PDF files using Docling primary, with GLM-OCR and pdfplumber fallbacks."""

    OCR_API_URL = "https://api.z.ai/api/paas/v4/layout_parsing"

    async def process(self, file_path: Path) -> ExtractedContentMultimodal | None:
        """Process PDF file."""
        logger.info("Processing PDF: %s", file_path.name)

        try:
            # Method 1: Docling (best quality, handles layout/tables/images)
            docling_result = await self._call_docling(file_path)
            if docling_result:
                return docling_result

            # Method 2: Try GLM-OCR API
            ocr_result = await self._call_glm_ocr(file_path)

            if ocr_result and ocr_result.get("text"):
                text = ocr_result["text"]
                metadata = {
                    "pages": ocr_result.get("pages", 1),
                    "method": "glm-ocr",
                }
            else:
                # Fallback: basic extraction
                text = await self._fallback_extract(file_path)
                metadata = {"method": "fallback"}

            # Extract visual elements if enabled
            visual_elements = []
            if self.config.pdf.visual_analysis:
                visual_elements = await self._extract_visual_elements(file_path)

            return ExtractedContentMultimodal(
                text=text,
                title=file_path.stem.replace("_", " ").replace("-", " ").title(),
                source_type="pdf",
                source_path=file_path,
                visual_elements=visual_elements,
                processing_method="glm-ocr" if ocr_result else "pdfminer",
                metadata=metadata,
            )

        except Exception as e:
            logger.exception("Failed to process PDF: %s", e)
            return None

    async def _call_docling(self, file_path: Path) -> ExtractedContentMultimodal | None:
        """Primary extraction using Docling."""
        try:
            from aily.chaos.processors.docling_processor import DoclingProcessor

            processor = DoclingProcessor(self.config, self.llm_client)
            result = await processor.process(file_path)
            if result:
                logger.info("Docling succeeded for %s", file_path.name)
            return result
        except Exception as e:
            logger.warning("Docling extraction failed for %s: %s", file_path.name, e)
            return None

    async def _call_glm_ocr(self, file_path: Path) -> dict | None:
        """Call GLM-OCR API for layout-aware extraction."""
        api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("BIGMODEL_API_KEY")
        if not api_key:
            logger.warning("No API key for GLM-OCR, using fallback")
            return None

        try:
            # Read file and encode to base64
            file_content = await asyncio.to_thread(file_path.read_bytes)
            base64_content = base64.b64encode(file_content).decode("utf-8")

            # Determine MIME type
            mime_type = "application/pdf"

            # GLM-OCR requires the specific OCR model, fallback to text extraction
            # Free tier doesn't support layout_parsing endpoint
            return None

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.OCR_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        logger.warning("GLM-OCR API error: %s", response.status)
                        return None

                    result = await response.json()

                    # Parse response
                    if "text" in result:
                        return {
                            "text": result["text"],
                            "pages": result.get("page_count", 1),
                            "layout": result.get("layout_details", []),
                        }
                    return None

        except Exception as e:
            logger.warning("GLM-OCR failed: %s", e)
            return None

    async def _fallback_extract(self, file_path: Path) -> str:
        """Fallback PDF extraction using pdfplumber."""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            return "\n\n".join(text_parts) if text_parts else ""
        except Exception as e:
            logger.warning("Fallback extraction failed: %s", e)
            return f"[PDF extraction failed for {file_path.name}]"

    async def _extract_visual_elements(self, file_path: Path) -> list[VisualElement]:
        """Extract visual elements from PDF pages."""
        visual_elements = []

        try:
            # Convert PDF pages to images
            images = await asyncio.to_thread(
                convert_from_path,
                str(file_path),
                first_page=1,
                last_page=min(10, self.config.pdf.max_pages_for_visual_analysis),
                dpi=150,
            )

            for i, image in enumerate(images):
                try:
                    # Convert to base64
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    # Create visual element
                    element = VisualElement(
                        element_id=f"page_{i+1}",
                        element_type="page",
                        description=f"Page {i+1}",
                        source_page=i + 1,
                        base64_data=base64_image[:1000] + "...",  # Truncate for storage
                    )
                    visual_elements.append(element)

                except Exception as e:
                    logger.warning("Failed to process page %d: %s", i + 1, e)

        except Exception as e:
            logger.warning("Visual element extraction failed: %s", e)

        return visual_elements

    def can_process(self, file_path: Path) -> bool:
        """Check if file is PDF."""
        return file_path.suffix.lower() == ".pdf"
