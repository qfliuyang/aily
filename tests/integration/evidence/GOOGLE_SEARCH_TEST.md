# Google Search Test - Mac Mini Browser Automation

**Date:** 2026-04-08
**Location:** Mac Mini (local execution)
**Browser:** Chrome with Playwright Stealth

## Test Summary

Automated Google search using Playwright with playwright-stealth on your Mac Mini's browser.

## Screenshots

| File | Description | Status |
|------|-------------|--------|
| `01_google_home.png` | Google homepage | ✅ Success |
| `02_query_typed.png` | Query typed: "What is the weight of LLM" | ✅ Success |
| `03_search_results.png` | Search results page / CAPTCHA | ⚠️ reCAPTCHA triggered |

## Test Results

### Attempt 1: Standard Browser
- **Result:** reCAPTCHA triggered immediately
- **Evidence:** `google_01_home.png`, `google_03_results.png`

### Attempt 2: playwright-stealth
- **Library:** `playwright-stealth` v2.0.3
- **Configuration:** Default evasions + realistic user agent
- **Result:** reCAPTCHA still triggered
- **Evidence:** `test-artifacts/test-20260408-022210-*/`

## Observations

1. **Browser automation works** on your Mac Mini
2. **Google's anti-bot detection is sophisticated**
   - playwright-stealth did not bypass detection
   - reCAPTCHA appears even with stealth mode
3. **Sites without anti-bot work fine** (arXiv, httpbin, YouTube)

## Technical Details

```python
Browser: Chromium (via Playwright)
Stealth: playwright-stealth v2.0.3
Headless: True
User Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...
Evasions Applied: navigator.webdriver, plugins, webgl_vendor, etc.
```

## Implications for Aily Testing

✅ **What works:**
- Browser automation on Mac Mini
- Screenshot capture
- Video recording (WEBM)
- Sites without aggressive anti-bot (arXiv, httpbin, YouTube)

⚠️ **Limitations:**
- Google searches trigger anti-bot protection
- playwright-stealth insufficient for Google
- Sites with reCAPTCHA will block automation

## Recommendation

**For Aily E2E tests, avoid Google searches.** Use:
- Direct URL fetching (arXiv, httpbin, etc.)
- API-based integrations (Obsidian REST API)
- Sites without anti-bot protection

**If Google access is needed:**
- Use authenticated Google API instead of scraping
- Consider residential proxy services
- Manual cookie/session import from real browser
