"""
Tavily Search Integration Test - NO MOCK

Tests real Tavily API search functionality.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_tavily_basic_search(exposure, test_id: str) -> None:
    """
    Test basic Tavily search query.

    EXPOSES: API key issues, rate limits, connectivity problems.
    """
    from aily.search.tavily import TavilyClient

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        pytest.skip("TAVILY_API_KEY not configured")

    client = TavilyClient(api_key)

    try:
        # Test query
        query = "What is the weight of LLM"

        exposure.expose("TAVILY_SEARCH_START", f"Query: {query}", {
            "test_id": test_id,
        })

        results = await client.search(
            query=query,
            max_results=3,
            include_answer=True,
        )

        # Verify response structure
        assert "results" in results, "Missing results field"
        assert isinstance(results["results"], list), "Results should be a list"

        exposure.expose("TAVILY_SUCCESS", f"Got {len(results['results'])} results", {
            "query": query,
            "result_count": len(results["results"]),
            "search_depth": results.get("search_depth", "unknown"),
            "has_answer": bool(results.get("answer")),
        })

        # Log first result for verification
        if results["results"]:
            first = results["results"][0]
            exposure.expose("TAVILY_SAMPLE_RESULT", "First result", {
                "title": first.get("title", "N/A")[:50],
                "url": first.get("url", "N/A")[:60],
                "score": first.get("score", 0),
            })

    except Exception as e:
        exposure.expose("TAVILY_FAILED", str(e), {
            "error_type": type(e).__name__,
        })
        raise

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tavily_to_markdown(exposure, test_id: str) -> None:
    """
    Test Tavily search formatted as markdown note.

    EXPOSES: Formatting issues, empty results handling.
    """
    from aily.search.tavily import TavilyClient

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        pytest.skip("TAVILY_API_KEY not configured")

    client = TavilyClient(api_key)

    try:
        query = "Attention is All You Need paper"
        markdown = await client.search_to_notes(query, max_results=3)

        exposure.expose("TAVILY_MARKDOWN", "Generated markdown note", {
            "query": query,
            "markdown_length": len(markdown),
            "has_headers": "# " in markdown,
            "has_sources": "## Sources" in markdown,
        })

        # Save markdown for review
        from pathlib import Path
        output_path = Path("test-artifacts") / test_id / "tavily_search_result.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown)

        exposure.expose("TAVILY_SAVED", f"Markdown saved to {output_path}", {
            "path": str(output_path),
        })

    except Exception as e:
        exposure.expose("TAVILY_MARKDOWN_FAILED", str(e), {
            "error_type": type(e).__name__,
        })
        raise

    finally:
        await client.close()


def pytest_sessionfinish(session, exitstatus):
    """Print summary after test."""
    print("\n" + "=" * 70)
    print("TAVILY SEARCH TEST SUMMARY")
    print("=" * 70)
    print(f"Test completed at: {datetime.now(timezone.utc).isoformat()}")
    print("Check test-artifacts/ for markdown output")
    print("=" * 70)
