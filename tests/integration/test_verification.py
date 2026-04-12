"""
Claim Verification Test - NO MOCK

Tests source verification like a human clicking links to check claims.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_claim_extraction(exposure, test_id: str) -> None:
    """
    Test extracting verifiable claims from markdown.

    EXPOSES: Claim detection accuracy, false positives.
    """
    from aily.verify.verifier import ClaimExtractor

    extractor = ClaimExtractor()

    sample_markdown = """
# Daily Digest

## Overview
Today we processed 150 nodes and 340 edges.

## Key Findings
- **Transformer architecture** achieves 27.5 BLEU score
- GPT-4 has 1.76 trillion parameters
- Model version 2.3.1 released 2024-01-15

## Stats
- Processing time: 45.5% faster than baseline
- Memory usage: 2.3 GB peak
"""

    claims = extractor.extract(sample_markdown)

    exposure.expose("CLAIMS_EXTRACTED", f"Found {len(claims)} verifiable claims", {
        "test_id": test_id,
        "claims": claims[:5],
    })

    # Verify we found the key claims
    claim_text = " ".join(claims).lower()

    if "transformer" in claim_text:
        exposure.expose("CLAIM_FOUND", "Found Transformer claim", {})
    if "bleu" in claim_text:
        exposure.expose("CLAIM_FOUND", "Found BLEU score claim", {})

    assert len(claims) > 0, "Should extract at least one claim"


@pytest.mark.asyncio
async def test_keyword_verification(exposure, test_id: str) -> None:
    """
    Test keyword-based claim verification (fallback mode).

    EXPOSES: Verification accuracy without LLM.
    """
    from aily.verify.verifier import ClaimVerifier

    verifier = ClaimVerifier(llm=None)  # Use keyword fallback

    # Simple test with known content
    claim = "The Transformer model uses attention mechanisms"
    source_content = """
    The Transformer is a deep learning model introduced in 2017.
    It uses attention mechanisms instead of recurrent layers.
    This allows for better parallelization during training.
    """

    result = verifier._keyword_verify(claim, source_content)

    exposure.expose("KEYWORD_VERIFICATION", "Fallback verification result", {
        "claim": claim[:50],
        "verified": result["verified"],
        "confidence": f"{result['confidence']:.2f}",
        "notes": result["notes"],
    })

    # Should find keyword matches
    assert result["confidence"] > 0.5, "Should have reasonable confidence"


@pytest.mark.asyncio
async def test_verification_end_to_end(exposure, test_id: str) -> None:
    """
    End-to-end: Extract and verify claims from real content.

    EXPOSES: Full verification pipeline issues.
    """
    from aily.verify.verifier import ClaimVerifier

    # Use LLM if available, otherwise keyword fallback
    from aily.llm.client import LLMClient
    from aily.config import SETTINGS

    llm = None
    if SETTINGS.llm_api_key:
        llm = LLMClient(
            base_url=SETTINGS.llm_base_url,
            api_key=SETTINGS.llm_api_key,
        )

    verifier = ClaimVerifier(llm=llm)

    # Sample markdown with claims
    markdown = """
## LLM Architecture

The **Transformer** architecture introduced in "Attention Is All You Need"
achieved 27.5 BLEU on English-to-German translation.

Key specs:
- 165 million parameters
- 8 attention heads
- 6 encoder and decoder layers
"""

    # Use arXiv as a known-good source
    source_urls = ["https://arxiv.org/abs/1706.03762"]

    exposure.expose("VERIFICATION_START", "Starting E2E verification", {
        "claims_expected": 3,
        "sources": len(source_urls),
    })

    try:
        results = await verifier.verify_digest(markdown, source_urls)

        verified = [r for r in results if r.verified]
        flagged = [r for r in results if not r.verified]

        exposure.expose("VERIFICATION_COMPLETE", f"{len(verified)} verified, {len(flagged)} flagged", {
            "total_claims": len(results),
            "verified": len(verified),
            "flagged": len(flagged),
        })

        # Log sample result
        if results:
            sample = results[0]
            exposure.expose("SAMPLE_VERIFICATION", "First claim result", {
                "claim": sample.claim[:60],
                "verified": sample.verified,
                "confidence": f"{sample.confidence:.2f}",
            })

    except Exception as e:
        exposure.expose("VERIFICATION_FAILED", str(e), {
            "error_type": type(e).__name__,
        })
        raise


def pytest_sessionfinish(session, exitstatus):
    """Print summary after test."""
    print("\n" + "=" * 70)
    print("CLAIM VERIFICATION TEST SUMMARY")
    print("=" * 70)
    print(f"Test completed at: {datetime.now(timezone.utc).isoformat()}")
    print("Verification: Like a human clicking source links")
    print("=" * 70)
