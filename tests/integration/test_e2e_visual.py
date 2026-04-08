"""
Visual E2E Tests for Aily - Screen Recordings & Snapshots.

These tests capture visual evidence of:
1. What Aily sees when fetching content
2. How pages render before parsing
3. Visual state at each step of the pipeline

Artifacts are saved to test-artifacts/{test_id}/ for review.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest


class TestVisualContentCapture:
    """
    Visual tests for content capture pipeline.

    Records what Aily "sees" when fetching URLs.
    """

    async def test_kimi_page_visual_state(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Capture visual state of Kimi-shared content.

        EXPOSES: Rendering issues, paywalls, bot detection, content shifts.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        # Example Kimi share URL (may need real one for valid test)
        # Using a reliable test page that mimics content structure
        test_url = "https://httpbin.org/html"

        try:
            # Navigate and wait for content
            await page.goto(test_url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            # Screenshot initial state
            await helper.screenshot("01_initial_load")

            # Scroll to capture full content
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)  # Wait for any lazy loading

            await helper.screenshot("02_scrolled_content")

            # Check for common blocking elements
            blocking_selectors = [
                ".captcha",
                "#captcha",
                ".paywall",
                ".login-prompt",
                "[class*='block']",
            ]

            for selector in blocking_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await helper.screenshot(f"03_blocking_{selector.replace('.', '')}")
                        exposure.expose("BLOCKING_ELEMENT_DETECTED", f"Found: {selector}", {
                            "url": test_url,
                            "selector": selector,
                        })
                except Exception:
                    pass

        except Exception as e:
            await helper.screenshot("error_state")
            exposure.expose("VISUAL_CAPTURE_FAILED", str(e), {"url": test_url})
            raise

        finally:
            # Report artifacts
            report = helper.get_artifacts_report()
            exposure.expose("VISUAL_ARTIFACTS", f"Captured {report['total_artifacts']} artifacts", report)

    async def test_arxiv_page_visual_capture(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Capture arXiv paper rendering for parser validation.

        EXPOSES: PDF vs HTML rendering, mobile layouts, abstract visibility.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        # arXiv abstract page (reliable academic content)
        test_url = "https://arxiv.org/abs/1706.03762"  # Attention Is All You Need

        try:
            await page.goto(test_url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            # Capture abstract visibility
            await helper.screenshot("01_arxiv_abstract")

            # Check for PDF link
            pdf_link = await page.query_selector("a[href*='pdf']")
            if pdf_link:
                exposure.expose("PDF_LINK_FOUND", "arXiv PDF available", {
                    "url": test_url,
                })

            # Check title
            title = await page.title()
            exposure.expose("ARXIV_TITLE", f"Page title: {title[:50]}", {
                "title": title,
                "url": test_url,
            })

        except Exception as e:
            await helper.screenshot("arxiv_error")
            exposure.expose("ARXIV_CAPTURE_FAILED", str(e), {"url": test_url})

    async def test_youtube_visual_metadata(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Capture YouTube page state (may be blocked).

        EXPOSES: Bot detection, consent dialogs, regional blocking.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        try:
            await page.goto(test_url, timeout=30000)
            await page.wait_for_timeout(3000)  # YouTube is JS-heavy

            await helper.screenshot("01_youtube_loaded")

            # Check for consent dialog (EU users)
            consent_button = await page.query_selector("button:has-text('Accept')")
            if consent_button:
                exposure.expose("YOUTUBE_CONSENT_DIALOG", "Consent dialog detected", {
                    "action": "May need to accept for content access",
                })

            # Check title for video info
            title = await page.title()
            if "YouTube" in title:
                exposure.expose("YOUTUBE_RENDERED", f"Title: {title[:50]}", {"title": title})

        except Exception as e:
            await helper.screenshot("youtube_error")
            exposure.expose("YOUTUBE_BLOCKED", str(e), {
                "likely_cause": "Bot detection or regional blocking",
            })


class TestVisualObsidianIntegration:
    """
    Visual tests for Obsidian integration.

    Records the actual state of notes in Obsidian.
    """

    async def test_obsidian_note_creation_visual(
        self,
        visual_browser_page,
        visual_helper,
        obsidian_client,
        exposure,
        test_id: str,
    ) -> None:
        """
        Visually verify note appears in Obsidian.

        EXPOSES: Rendering issues, markdown formatting problems, sync delays.
        """
        if not os.getenv("OBSIDIAN_REST_API_KEY"):
            pytest.skip("Obsidian not configured")

        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        port = os.getenv("OBSIDIAN_REST_API_PORT", "27123")
        api_key = os.getenv("OBSIDIAN_REST_API_KEY")

        # Create a test note with rich content
        note_content = f"""# Visual Test {test_id}

## Test Content

This note tests visual rendering.

- **Bold text**
- *Italic text*
- `Code inline`

### Code Block

```python
def hello():
    print("Hello from visual test")
```

### Table

| Col1 | Col2 |
|------|------|
| A    | B    |
| C    | D    |

---

*Created: {datetime.now(timezone.utc).isoformat()}*
"""

        try:
            # Create note via API
            filename = f"visual-test-{test_id}.md"
            await obsidian_client.write_note(filename, note_content)

            exposure.expose("NOTE_CREATED", f"Created: {filename}", {
                "size_bytes": len(note_content.encode('utf-8')),
            })

            # Try to view in Obsidian (if web interface available)
            try:
                await page.goto(f"http://127.0.0.1:{port}/", timeout=5000)
                await helper.screenshot("01_obsidian_rest_api")
            except Exception:
                exposure.expose("OBSIDIAN_WEB_UNAVAILABLE", "No web interface to screenshot", {
                    "note": "Note created but cannot visually verify via browser",
                })

            # Read back and verify content
            read_content = await obsidian_client.read_note(filename)

            # Check formatting preserved
            checks = {
                "headers": "# Visual Test" in read_content,
                "bold": "**Bold text**" in read_content,
                "code_block": "```python" in read_content,
                "table": "| Col1 |" in read_content,
            }

            exposure.expose("CONTENT_INTEGRITY", "Markdown structure check", checks)

        except Exception as e:
            exposure.expose("OBSIDIAN_VISUAL_FAILED", str(e), {})
            raise


class TestVisualFeishuInteraction:
    """
    Visual tests for Feishu bot interactions.

    Records message rendering and bot responses.
    """

    async def test_feishu_chat_visual_simulation(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Simulate Feishu chat and capture visual state.

        EXPOSES: Message formatting issues, card rendering problems.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        # Since we can't easily access Feishu web without auth,
        # create a visual representation of what the user sees

        # Create HTML representation of chat
        chat_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, sans-serif; padding: 20px; background: #f5f5f5; }}
                .message {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; }}
                .user {{ border-left: 4px solid #3370ff; }}
                .bot {{ border-left: 4px solid #00b96b; }}
                .meta {{ color: #666; font-size: 12px; margin-top: 5px; }}
                .url {{ color: #3370ff; text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h2>Feishu Chat Simulation - Test {test_id[:8]}</h2>

            <div class="message user">
                <div>User sends a link:</div>
                <div class="url">https://example.com/article-{test_id}</div>
                <div class="meta">{datetime.now(timezone.utc).strftime('%H:%M')}</div>
            </div>

            <div class="message bot">
                <div>Aily Bot responds:</div>
                <div style="margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 4px;">
                    ✅ Saved to Obsidian: <strong>Aily/Articles/example-article.md</strong>
                </div>
                <div class="meta">{datetime.now(timezone.utc).strftime('%H:%M')} • Aily Bot</div>
            </div>
        </body>
        </html>
        """

        # Save HTML for review
        html_path = artifacts_dir / "feishu_chat_simulation.html"
        html_path.write_text(chat_html)

        # Load in browser and screenshot
        await page.goto(f"file://{html_path.absolute()}")
        await helper.screenshot("01_feishu_chat_simulation")

        exposure.expose("CHAT_VISUAL_CREATED", "Feishu chat simulation captured", {
            "html_path": str(html_path),
            "scenario": "User shares link → Bot confirms save",
        })


class TestVisualDockerEnvironment:
    """
    Visual tests specifically for Docker-based testing.

    Verifies containerized browser behavior.
    """

    async def test_docker_browser_capabilities(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Verify browser capabilities in Docker environment.

        EXPOSES: Missing fonts, display issues, permission problems.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        # Test page with various elements
        test_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
                body {{
                    font-family: 'Inter', -apple-system, sans-serif;
                    padding: 40px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: rgba(255,255,255,0.1);
                    padding: 30px;
                    border-radius: 16px;
                }}
                h1 {{ margin-top: 0; }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-top: 20px;
                }}
                .card {{
                    background: rgba(255,255,255,0.2);
                    padding: 20px;
                    border-radius: 8px;
                }}
                .emoji {{ font-size: 24px; }}
                .chinese {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Docker Browser Test</h1>
                <p>Test ID: {test_id}</p>
                <p class="emoji">🎉 🚀 💻 📊</p>
                <p class="chinese">中文测试: 你好世界</p>

                <div class="grid">
                    <div class="card">
                        <h3>Fonts</h3>
                        <p>Inter font loaded from Google Fonts</p>
                    </div>
                    <div class="card">
                        <h3>CSS</h3>
                        <p>Gradients, grid, transparency</p>
                    </div>
                    <div class="card">
                        <h3>Unicode</h3>
                        <p>é à ñ ü 日本語 한국어 العربية</p>
                    </div>
                    <div class="card">
                        <h3>Time</h3>
                        <p>{datetime.now(timezone.utc).isoformat()}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        html_path = artifacts_dir / "docker_browser_test.html"
        html_path.write_text(test_html)

        await page.goto(f"file://{html_path.absolute()}")
        await page.wait_for_timeout(1000)  # Wait for font load attempt

        await helper.screenshot("01_docker_browser_capabilities")

        # Check capabilities
        capabilities = await page.evaluate("""
            () => ({
                userAgent: navigator.userAgent,
                languages: navigator.languages,
                viewport: { width: window.innerWidth, height: window.innerHeight },
                devicePixelRatio: window.devicePixelRatio,
                webdriver: navigator.webdriver,
            })
        """)

        exposure.expose("DOCKER_BROWSER_CAPABILITIES", "Browser env in container", capabilities)

    async def test_video_recording_quality(
        self,
        visual_browser_page,
        visual_helper,
        exposure,
        test_id: str,
    ) -> None:
        """
        Verify video recording captures interactions correctly.

        EXPOSES: Video corruption, encoding issues, frame drops.
        """
        page, artifacts_dir = visual_browser_page
        helper = visual_helper(page, artifacts_dir, exposure)

        # Perform actions that should be captured in video
        await page.goto("https://httpbin.org/html")
        await page.wait_for_timeout(1000)
        await helper.screenshot("video_test_start")

        # Scroll action (should be in video)
        await page.evaluate("window.scrollTo(0, 500)")
        await page.wait_for_timeout(500)

        # Click action (should be in video)
        try:
            await page.click("h1")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        await helper.screenshot("video_test_end")

        # Video will be saved on context close
        report = helper.get_artifacts_report()
        exposure.expose("VIDEO_TEST_COMPLETE", "Interaction sequence recorded", {
            "video_saved": len(report["videos"]) > 0,
            "video_count": len(report["videos"]),
            "artifacts": report,
        })


# =============================================================================
# Visual Test Summary
# =============================================================================

def pytest_sessionfinish(session, exitstatus):
    """Print visual test artifact locations."""
    print("\n" + "="*70)
    print("VISUAL TEST ARTIFACTS")
    print("="*70)

    artifacts_base = Path("test-artifacts")
    if artifacts_base.exists():
        test_dirs = list(artifacts_base.iterdir())
        print(f"\n{len(test_dirs)} test artifact directories:")

        for test_dir in sorted(test_dirs):
            screenshots = list(test_dir.glob("*.png"))
            videos = list(test_dir.glob("*.webm"))
            html = list(test_dir.glob("*.html"))

            print(f"\n  {test_dir.name}/")
            print(f"    Screenshots: {len(screenshots)}")
            print(f"    Videos: {len(videos)}")
            print(f"    HTML: {len(html)}")

        print(f"\nFull path: {artifacts_base.absolute()}")
    else:
        print("\nNo artifacts directory found.")

    print("="*70)
