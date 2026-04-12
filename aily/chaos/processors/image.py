"""Image processor using GLM-4V for visual understanding."""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import aiohttp
from PIL import Image

from aily.chaos.processors.base import ContentProcessor
from aily.chaos.types import ExtractedContentMultimodal, VisualElement

logger = logging.getLogger(__name__)


class ImageProcessor(ContentProcessor):
    """Process images using GLM-4V for visual analysis."""

    VISION_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    async def process(self, file_path: Path) -> ExtractedContentMultimodal | None:
        """Process image file."""
        logger.info("Processing image: %s", file_path.name)

        try:
            # Load and resize image
            base64_image = await self._load_image(file_path)

            # Get visual analysis from GLM-4V
            analysis = await self._analyze_with_vision(base64_image)

            # Try OCR if enabled
            ocr_text = None
            if self.config.image.ocr_enabled:
                ocr_text = await self._extract_text_with_ocr(base64_image)

            # Create visual element
            visual_element = VisualElement(
                element_id=file_path.stem,
                element_type="image",
                description=analysis.get("description", "Image") if analysis else "Image",
                base64_data=base64_image[:1000] + "...",  # Truncate for storage
                ocr_text=ocr_text,
                llm_analysis=analysis.get("analysis") if analysis else None,
            )

            # Build text from analysis and OCR
            text_parts = []
            if analysis and analysis.get("description"):
                text_parts.append(f"## Image Description\n\n{analysis['description']}")
            if ocr_text:
                text_parts.append(f"## Extracted Text\n\n{ocr_text}")

            text = "\n\n".join(text_parts) if text_parts else f"[Image: {file_path.name}]"

            return ExtractedContentMultimodal(
                text=text,
                title=file_path.stem.replace("_", " ").replace("-", " ").title(),
                source_type="image",
                source_path=file_path,
                visual_elements=[visual_element],
                processing_method="glm-4v",
                metadata={
                    "format": file_path.suffix.lower(),
                    "has_ocr": ocr_text is not None,
                    "has_analysis": analysis is not None,
                },
            )

        except Exception as e:
            logger.exception("Failed to process image: %s", e)
            return None

    async def _load_image(self, file_path: Path) -> str:
        """Load image and convert to base64, resizing if needed."""
        image = Image.open(file_path)

        # Convert to RGB if necessary (handles RGBA, CMYK, etc.)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if too large
        max_size = self.config.image.max_image_size
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return base64_str

    async def _analyze_with_vision(self, base64_image: str) -> dict | None:
        """Analyze image using GLM-4V."""
        api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("BIGMODEL_API_KEY")
        if not api_key or not self.config.image.visual_analysis:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "glm-4v-flash",  # Use free tier for vision
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this image in detail. What is shown? What are the key elements?",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 1024,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.VISION_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.warning("Vision API error: %s - %s", response.status, error_text)
                        return None

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]

                    return {
                        "description": content,
                        "analysis": content,
                    }

        except Exception as e:
            logger.warning("Vision analysis failed: %s", e)
            return None

    async def _extract_text_with_ocr(self, base64_image: str) -> str | None:
        """Extract text from image using GLM-OCR or vision model."""
        api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("BIGMODEL_API_KEY")
        if not api_key:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Use vision model to extract text
            payload = {
                "model": "glm-4v-flash",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all text from this image. Return only the extracted text, no explanations.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 1024,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.VISION_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        return None

                    result = await response.json()
                    text = result["choices"][0]["message"]["content"]

                    # Clean up common responses
                    if "no text" in text.lower() or "no visible text" in text.lower():
                        return None

                    return text.strip()

        except Exception as e:
            logger.warning("OCR extraction failed: %s", e)
            return None

    def can_process(self, file_path: Path) -> bool:
        """Check if file is an image."""
        ext = file_path.suffix.lower()
        return ext in self.config.supported_formats
