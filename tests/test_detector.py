import pytest

from aily.processing.detector import ContentType, ContentTypeDetector


class TestContentType:
    def test_basic_creation(self):
        ct = ContentType("text/plain")
        assert ct.mime_type == "text/plain"
        assert ct.extension is None
        assert ct.confidence == 1.0

    def test_full_creation(self):
        ct = ContentType("application/pdf", ".pdf", 0.95)
        assert ct.mime_type == "application/pdf"
        assert ct.extension == ".pdf"
        assert ct.confidence == 0.95


class TestDetectFromBytes:
    def test_detects_pdf_from_magic_bytes(self):
        data = b"%PDF-1.4\n1 0 obj\n<<"
        result = ContentTypeDetector.detect_from_bytes(data, "doc.txt")
        assert result.mime_type == "application/pdf"
        assert result.confidence == 0.95

    def test_detects_png_from_magic_bytes(self):
        data = b"\x89PNG\r\n\x1a\n"
        result = ContentTypeDetector.detect_from_bytes(data, "image.gif")
        assert result.mime_type == "image/png"
        assert result.confidence == 0.95

    def test_detects_jpeg_from_magic_bytes(self):
        data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "image/jpeg"
        assert result.confidence == 0.95

    def test_detects_gif87a_from_magic_bytes(self):
        data = b"GIF87a\x01\x00\x01\x00"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "image/gif"

    def test_detects_gif89a_from_magic_bytes(self):
        data = b"GIF89a\x01\x00\x01\x00"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "image/gif"

    def test_detects_zip_from_magic_bytes(self):
        data = b"PK\x03\x04\x14\x00\x00\x00"
        result = ContentTypeDetector.detect_from_bytes(data, "document.docx")
        assert result.mime_type == "application/zip"
        assert result.extension == ".docx"

    def test_detects_gzip_from_magic_bytes(self):
        data = b"\x1f\x8b\x08\x00\x00\x00\x00\x00"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "application/gzip"

    def test_falls_back_to_extension(self):
        data = b"Some plain text content"
        result = ContentTypeDetector.detect_from_bytes(data, "readme.md")
        assert result.mime_type == "text/markdown"
        assert result.extension == ".md"
        assert result.confidence == 0.8

    def test_extension_mapping_pdf(self):
        data = b"Not a real PDF but has .pdf extension"
        result = ContentTypeDetector.detect_from_bytes(data, "doc.pdf")
        assert result.mime_type == "application/pdf"

    def test_extension_mapping_docx(self):
        data = b"Not a real docx"
        result = ContentTypeDetector.detect_from_bytes(data, "document.docx")
        assert result.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_extension_mapping_html(self):
        data = b"Not HTML"
        result = ContentTypeDetector.detect_from_bytes(data, "page.html")
        assert result.mime_type == "text/html"

    def test_detects_text_plain(self):
        data = b"This is just plain text content."
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/plain"
        assert result.confidence == 0.5

    def test_detects_html_from_content(self):
        data = b"<!DOCTYPE html>\n<html>\n<body>Hello</body>\n</html>"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/html"
        assert result.confidence == 0.7

    def test_detects_html_lowercase(self):
        data = b"<!doctype html>\n<html>\n<body>Hello</body>\n</html>"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/html"

    def test_detects_markdown_from_content(self):
        data = b"# Heading\n\nSome paragraph."
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/markdown"
        assert result.confidence == 0.4

    def test_detects_markdown_list(self):
        data = b"- Item 1\n- Item 2\n- Item 3"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/markdown"

    def test_detects_markdown_table(self):
        data = b"| Col1 | Col2 |\n|------|------|"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "text/markdown"

    def test_falls_back_to_octet_stream_for_binary(self):
        data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        result = ContentTypeDetector.detect_from_bytes(data)
        assert result.mime_type == "application/octet-stream"
        assert result.confidence == 0.1

    def test_no_filename_provided(self):
        data = b"Some content"
        result = ContentTypeDetector.detect_from_bytes(data, None)
        assert result.mime_type == "text/plain"


class TestDetectFromHttpHeaders:
    def test_detects_from_content_type_header(self):
        result = ContentTypeDetector.detect_from_http_headers("text/html; charset=utf-8")
        assert result.mime_type == "text/html"
        assert result.confidence == 0.9

    def test_normalizes_application_x_pdf(self):
        result = ContentTypeDetector.detect_from_http_headers("application/x-pdf")
        assert result.mime_type == "application/pdf"

    def test_normalizes_image_jpg(self):
        result = ContentTypeDetector.detect_from_http_headers("image/jpg")
        assert result.mime_type == "image/jpeg"

    def test_normalizes_text_x_markdown(self):
        result = ContentTypeDetector.detect_from_http_headers("text/x-markdown")
        assert result.mime_type == "text/markdown"

    def test_handles_none_header(self):
        result = ContentTypeDetector.detect_from_http_headers(None)
        assert result is None

    def test_handles_empty_header(self):
        result = ContentTypeDetector.detect_from_http_headers("")
        assert result is None

    def test_lowercases_mime_type(self):
        result = ContentTypeDetector.detect_from_http_headers("TEXT/HTML")
        assert result.mime_type == "text/html"


class TestDetect:
    def test_uses_http_header_when_high_confidence(self):
        result = ContentTypeDetector.detect(
            data=b"%PDF",
            http_content_type="text/html; charset=utf-8"
        )
        assert result.mime_type == "text/html"
        assert result.confidence == 0.9

    def test_prefers_magic_bytes_over_extension(self):
        result = ContentTypeDetector.detect(
            data=b"%PDF fake pdf content",
            filename="document.txt"
        )
        assert result.mime_type == "application/pdf"

    def test_uses_extension_when_no_data(self):
        result = ContentTypeDetector.detect(
            data=None,
            filename="document.pdf"
        )
        assert result.mime_type == "application/pdf"
        assert result.confidence == 0.5

    def test_falls_back_to_octet_stream(self):
        result = ContentTypeDetector.detect()
        assert result.mime_type == "application/octet-stream"
        assert result.confidence == 0.0


class TestIsText:
    def test_returns_true_for_plain_text(self):
        data = b"This is plain text."
        assert ContentTypeDetector._is_text(data) is True

    def test_returns_false_for_binary_with_null_bytes(self):
        data = b"\x00\x01\x02\x03"
        assert ContentTypeDetector._is_text(data) is False

    def test_returns_false_for_invalid_utf8(self):
        data = b"\xff\xfe\x00\x01"
        assert ContentTypeDetector._is_text(data) is False

    def test_handles_empty_data(self):
        data = b""
        assert ContentTypeDetector._is_text(data) is True


class TestGetExtension:
    def test_extracts_extension(self):
        assert ContentTypeDetector._get_extension("document.pdf") == ".pdf"
        assert ContentTypeDetector._get_extension("/path/to/file.txt") == ".txt"

    def test_handles_no_extension(self):
        assert ContentTypeDetector._get_extension("README") is None

    def test_handles_none_input(self):
        assert ContentTypeDetector._get_extension(None) is None

    def test_handles_empty_string(self):
        assert ContentTypeDetector._get_extension("") is None

    def test_lowercases_extension(self):
        assert ContentTypeDetector._get_extension("File.PDF") == ".pdf"
