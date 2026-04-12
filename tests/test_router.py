import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aily.processing.router import ProcessingRouter, _format_size
from aily.processing.processors import ExtractedContent


class TestFormatSize:
    def test_bytes(self):
        assert _format_size(500) == "500.0B"

    def test_kilobytes(self):
        assert _format_size(1024) == "1.0KB"
        assert _format_size(1536) == "1.5KB"

    def test_megabytes(self):
        assert _format_size(1024 * 1024) == "1.0MB"
        assert _format_size(50 * 1024 * 1024) == "50.0MB"

    def test_gigabytes(self):
        assert _format_size(1024 * 1024 * 1024) == "1.0GB"


class TestProcessingRouterInit:
    def test_initializes_processors(self):
        router = ProcessingRouter()
        assert len(router._processors) == 8
        processor_names = [p.__class__.__name__ for p in router._processors]
        assert "PDFProcessor" in processor_names
        assert "ImageProcessor" in processor_names
        assert "CSVProcessor" in processor_names
        assert "XLSXProcessor" in processor_names


class TestProcessingRouterGetProcessor:
    def test_get_processor_exact_match(self):
        router = ProcessingRouter()
        processor = router._get_processor("application/pdf")
        assert processor.__class__.__name__ == "PDFProcessor"

    def test_get_processor_wildcard_match(self):
        router = ProcessingRouter()
        processor = router._get_processor("image/png")
        assert processor.__class__.__name__ == "ImageProcessor"

    def test_get_processor_no_match_returns_none(self):
        router = ProcessingRouter()
        processor = router._get_processor("application/unknown")
        assert processor is None


class TestProcessingRouterProcess:
    @pytest.mark.asyncio
    async def test_processes_pdf_content(self):
        router = ProcessingRouter()
        # Mock the PDF processor
        mock_processor = MagicMock()
        mock_processor.SUPPORTED_TYPES = ["application/pdf"]
        mock_processor.can_process.return_value = True
        mock_processor.process = AsyncMock(return_value=ExtractedContent(
            text="PDF content",
            title="Test",
            source_type="pdf"
        ))

        router._processors = [mock_processor]

        result = await router.process(b"%PDF-1.4", "test.pdf")
        assert result.text == "PDF content"

    @pytest.mark.asyncio
    async def test_uses_text_fallback_for_unknown_type(self):
        router = ProcessingRouter()
        # Clear processors so no match is found
        router._processors = []

        result = await router.process(b"Some text content", "unknown.xyz")
        # TextProcessor is used as fallback
        assert result.text == "Some text content"

    @pytest.mark.asyncio
    async def test_handles_processing_exception(self):
        router = ProcessingRouter()
        mock_processor = MagicMock()
        mock_processor.SUPPORTED_TYPES = ["application/pdf"]
        mock_processor.can_process.return_value = False
        mock_processor.process = AsyncMock(side_effect=Exception("PDF error"))

        router._processors = [mock_processor]

        result = await router.process(b"%PDF", "test.pdf")
        assert "Processing failed" in result.text
        assert result.source_type == "error"

    @pytest.mark.asyncio
    @patch("aily.processing.router.SETTINGS")
    async def test_rejects_oversized_file(self, mock_settings):
        mock_settings.max_file_size = 1000
        mock_settings.max_image_size = 500

        router = ProcessingRouter()
        result = await router.process(b"x" * 1001, "large.pdf")

        assert "File too large" in result.text
        assert "exceeds limit" in result.text
        assert result.source_type == "error"

    @pytest.mark.asyncio
    @patch("aily.processing.router.SETTINGS")
    async def test_allows_file_under_limit(self, mock_settings):
        mock_settings.max_file_size = 10000
        mock_settings.max_image_size = 5000

        router = ProcessingRouter()
        result = await router.process(b"Small content", "small.txt")

        assert "File too large" not in result.text

    @pytest.mark.asyncio
    @patch("aily.processing.router.SETTINGS")
    async def test_uses_image_size_limit_for_images(self, mock_settings):
        mock_settings.max_file_size = 10000
        mock_settings.max_image_size = 100  # Very small limit

        router = ProcessingRouter()
        result = await router.process(
            b"x" * 101,
            "large.png",
            http_content_type="image/png"
        )

        assert "File too large" in result.text


class TestProcessingRouterProcessUrl:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_fetches_and_processes_url(self, mock_client_cls):
        mock_response = AsyncMock()
        mock_response.content = b"# Markdown content"
        mock_response.headers = {"content-type": "text/markdown"}
        mock_response.raise_for_status = AsyncMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        router = ProcessingRouter()
        result = await router.process_url("https://example.com/doc.md")

        assert "Markdown content" in result.text

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_handles_fetch_failure(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        router = ProcessingRouter()
        result = await router.process_url("https://example.com/doc.md")

        assert "Failed to fetch" in result.text
        assert result.source_type == "web"


class TestProcessingRouterIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_pdf(self):
        router = ProcessingRouter()
        # Use real detection but mock the PDF processing
        result = await router.process(b"Plain text, not PDF", "readme.txt")
        assert result.source_type == "text"
        assert result.text == "Plain text, not PDF"

    @pytest.mark.asyncio
    async def test_full_pipeline_csv(self):
        router = ProcessingRouter()
        csv_data = b"name,value\nAlice,100\nBob,200"
        result = await router.process(csv_data, "data.csv")
        assert result.source_type == "csv"
        assert "| name | value |" in result.text

    @pytest.mark.asyncio
    async def test_full_pipeline_markdown(self):
        router = ProcessingRouter()
        md_data = b"# Heading\n\nParagraph text."
        result = await router.process(md_data, "doc.md")
        assert result.source_type == "markdown"
        assert result.title == "Heading"

    @pytest.mark.asyncio
    async def test_html_detection_from_content(self):
        router = ProcessingRouter()
        html_data = b"<!DOCTYPE html><html><body>Content</body></html>"
        result = await router.process(html_data, "page.html")
        assert result.source_type == "web"
        assert "Content" in result.text
