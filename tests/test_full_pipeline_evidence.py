from pathlib import Path

from aily.chaos.types import ExtractedContentMultimodal, VisualElement
from scripts.test_framework import extraction_metadata_for


def test_extraction_metadata_uses_visual_elements_field() -> None:
    extracted = ExtractedContentMultimodal(
        text="real extracted text",
        title="Test PDF",
        source_type="pdf",
        source_path=Path("/tmp/test.pdf"),
        processing_method="pdfminer",
        visual_elements=[
            VisualElement(
                element_id="fig_1",
                element_type="figure",
                description="A real figure",
                asset_path="images/fig_1.png",
            )
        ],
        metadata={"method": "fallback"},
    )

    metadata = extraction_metadata_for(extracted)

    assert metadata["visual_elements"] == 1
    assert metadata["processing_method"] == "pdfminer"
    assert metadata["metadata_method"] == "fallback"
