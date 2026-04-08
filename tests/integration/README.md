# Aily Integration Tests - NO MOCK

Real service testing against production APIs. No mocks, no simulations - actual HTTP calls to real services.

## Philosophy

These tests are designed to **EXPOSE problems**, not pass:

- Network timeouts
- API rate limits
- Authentication failures
- Data corruption
- Race conditions
- Encoding issues

If something can go wrong, these tests will find it.

## E2E MVP Tests (Start Here)

The E2E MVP tests validate Aily's core value proposition:

> **Send a link → Get structured knowledge in Obsidian**

### Running E2E MVP Tests

```bash
# Run the full E2E MVP test suite
./run-real.sh e2e

# Or directly with pytest
pytest tests/integration/test_e2e_mvp.py -v -s
```

### What E2E Tests Validate

| Test | What It Proves |
|------|----------------|
| `test_send_url_receive_note_in_obsidian` | The complete happy path works |
| `test_link_deduplication_prevents_duplicate_notes` | Same URL twice = one note |
| `test_bad_url_results_in_failure_notification` | Failures are communicated |
| `test_obsidian_down_graceful_failure` | System degrades gracefully |
| `test_note_has_proper_structure` | Output quality is maintained |
| `test_concurrent_note_creation` | No race conditions |

**If E2E tests pass, Aily delivers its core promise.**
**If they fail, the product is broken.**

## Visual Tests (Screenshots & Screen Recordings)

Visual tests capture what Aily "sees" when fetching and processing content. Every test generates artifacts for manual review.

### Running Visual Tests

```bash
# Run visual tests with screen recordings
./run-real.sh visual

# Artifacts are saved to test-artifacts/{test_id}/
ls -la test-artifacts/
```

### Visual Test Artifacts

Each visual test generates:

| Artifact | Description |
|----------|-------------|
| `*.png` | Screenshots at key moments |
| `*.webm` | Screen recording of full test |
| `*.html` | Simulated UI states (Feishu chat, etc.) |

### Visual Tests

| Test | Captures |
|------|----------|
| `test_kimi_page_visual_state` | Content rendering, blocking elements |
| `test_arxiv_page_visual_capture` | PDF vs HTML, abstract visibility |
| `test_youtube_visual_metadata` | Bot detection, consent dialogs |
| `test_obsidian_note_creation_visual` | Markdown formatting, note structure |
| `test_feishu_chat_visual_simulation` | Message UI simulation |
| `test_docker_browser_capabilities` | Font rendering, CSS support |
| `test_video_recording_quality` | Recording integrity, frame capture |

### Docker Visual Testing

In Docker environments, visual tests verify:
- Browser capabilities in containerized environment
- Font availability and rendering
- Video encoding quality
- Screenshot capture reliability

```bash
# Run in Docker with visual output
docker run -v $(pwd)/test-artifacts:/app/test-artifacts aily-tests visual
```

## Prerequisites

### Required Environment Variables

```bash
# Feishu (Lark) Bot
export FEISHU_APP_ID="cli_xxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxx"

# Obsidian Local REST API
export OBSIDIAN_VAULT_PATH="/Users/you/Documents/Vault"
export OBSIDIAN_REST_API_KEY="your-api-key"

# Optional: Feishu test target
export FEISHU_TEST_OPEN_ID="ou_xxxxxxxx"  # Your Open ID for test messages
```

### Setting Up Feishu

1. Go to [Feishu Developer Console](https://open.feishu.cn/app)
2. Create a new app (bot)
3. Copy App ID and App Secret
4. Enable bot capability
5. Add yourself as a tester
6. Find your Open ID via the Feishu API or admin console

### Setting Up Obsidian

1. Install the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api)
2. Enable the plugin in Obsidian Settings
3. Copy the API key from plugin settings
4. Note your vault path

## Running Tests

### All Real Service Tests

```bash
cd /Users/luzi/code/aily
source .venv/bin/activate
pytest tests/integration/test_real_services.py -v
```

### Specific Service Tests

```bash
# Feishu tests only
pytest tests/integration/test_real_services.py::TestRealFeishuExposesProblems -v

# Obsidian tests only
pytest tests/integration/test_real_services.py::TestRealObsidianExposesProblems -v

# Browser tests only
pytest tests/integration/test_real_services.py::TestRealBrowserExposesProblems -v

# Database tests only
pytest tests/integration/test_real_services.py::TestDatabaseExposesProblems -v
```

### With Problem Exposure Report

```bash
pytest tests/integration/test_real_services.py -v -s
```

The `-s` flag shows the problem exposure output even for passing tests.

## Test Categories

### Feishu Tests (`TestRealFeishuExposesProblems`)

Sends **actual messages** to real users. Pollutes your Feishu history.

- `test_auth_exposes_wrong_credentials` - Verifies bad auth fails loudly
- `test_send_message_exposes_network_issues` - Tests real message sending
- `test_concurrent_sends_expose_rate_limits` - Sends 5 messages concurrently to find rate limits

### Obsidian Tests (`TestRealObsidianExposesProblems`)

Writes **actual files** to your vault in `Aily Tests/` folder.

- `test_vault_not_running_exposes_failure` - Fails if Obsidian isn't running
- `test_write_exposes_encoding_issues` - Tests unicode, emoji, special chars
- `test_large_files_expose_performance_issues` - Tests 1KB/50KB/500KB writes

### Browser Tests (`TestRealBrowserExposesProblems`)

Fetches **real websites** over the internet.

- `test_fetch_down_site_exposes_failure` - Tests error handling for bad URLs
- `test_fetch_real_sites_exposes_actual_behavior` - Fetches live sites (may hit anti-bot)
- `test_javascript_rendering_exposes_timing_issues` - Tests JS execution and race conditions

### Database Tests (`TestDatabaseExposesProblems`)

Uses **real file I/O** (not :memory:) to expose actual SQLite behavior.

- `test_concurrent_writes_expose_locking_issues` - 3 threads writing concurrently
- `test_large_transaction_expose_memory_issues` - 100 x 100KB rows in one transaction

## Problem Exposure

Unlike unit tests that expect success, these tests actively hunt for failures.

```python
exposure.expose("TIMEOUT", "Feishu API timed out", {
    "error": str(e),
    "this_is_a_real_problem": True,
})
```

Even if a test "passes" (expected behavior), problems are logged and reported.

## Cleanup

Tests clean up after themselves:

- **Obsidian**: All files in `Aily Tests/` folder deleted after session
- **Database**: Temp files deleted after each test
- **Feishu**: Messages persist (intentional - visible proof of testing)

## Skipping Unconfigured Services

Tests automatically skip if credentials aren't set:

```
⚠️  Missing real services: feishu, obsidian
Tests for these services will be SKIPPED
```

## Safety Warnings

⚠️ **These tests have real side effects:**

1. **Feishu**: Sends actual messages to your account
2. **Obsidian**: Creates/deletes files in your vault
3. **Browser**: Makes real HTTP requests to external sites
4. **Database**: Creates temp files on disk

**Do not run in CI/CD without proper credentials and isolation.**

## Debugging Failed Tests

```bash
# Show all output including problem exposure
pytest tests/integration/test_real_services.py -v -s --tb=long

# Run single test with max verbosity
pytest tests/integration/test_real_services.py::TestRealFeishuExposesProblems::test_send_message_exposes_network_issues -vvs
```

## Architecture

```
┌─────────────────────────────────────────┐
│  pytest + ProblemExposure Reporter      │
└──────────┬──────────────────────────────┘
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
┌────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐
│ Feishu │ │ Obsidian   │ │ Browser  │ │ SQLite   │
│ API    │ │ REST API   │ │ Playwright│ │ (file)   │
└────────┘ └────────────┘ └──────────┘ └──────────┘
```

## Writing New Tests

Pattern for exposing problems:

```python
async def test_something_exposes_problem(
    self,
    feishu_client,  # or obsidian_client, browser_page, database_connection
    exposure,
    test_id: str,
) -> None:
    try:
        result = await feishu_client.do_something()

        # Check for partial failures
        if result.get("code") != 0:
            exposure.expose("API_ERROR", "Service returned error", result)

    except httpx.TimeoutException as e:
        exposure.expose("TIMEOUT", "Service timed out", {"error": str(e)})
        raise  # Fail the test

    except Exception as e:
        exposure.expose("UNEXPECTED_ERROR", type(e).__name__, {"error": str(e)})
        raise
```

Key principles:
1. **Expose everything** - Log issues even if test passes
2. **Fail on critical errors** - Re-raise to fail test
3. **Test real behavior** - Don't mock, hit the real API
4. **Document side effects** - Tests have real consequences
