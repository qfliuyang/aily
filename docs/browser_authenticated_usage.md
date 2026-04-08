# Using Browser Automation with Your Logged-In Accounts

This guide explains how to use Browser Use with your existing Chrome profile where you're already logged into Monica, Kimi, or other services.

## How It Works

Instead of using a fresh browser profile (which requires login), you can point Browser Use at your actual Chrome profile. This means:
- You're already logged in to Monica/Kimi
- Cookies and session tokens are available
- No CAPTCHA or login walls
- Much more reliable extraction

## Prerequisites

1. **Chrome must be closed** — The profile can only be used by one browser instance at a time
2. **You must be logged in** — Use Chrome normally to log into the services you want to automate
3. **Chrome profile location** — The code auto-detects this based on your OS

## Usage

### Quick Test

```bash
# Make sure Chrome is completely closed first

# Run the test script
python scripts/test_browser_authenticated.py --url https://kimi.moonshot.cn
```

### In Your Code

```python
from aily.browser.manager import BrowserUseManager

# Create manager with agent worker
browser = BrowserUseManager(
    worker_type="agent",
    llm_config={
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key": "your-openai-key",
    }
)

await browser.start()

# Extract using your logged-in profile
result = await browser.fetch(
    url="https://kimi.moonshot.cn",
    timeout=120,
    use_personal_profile=True  # <-- This is the key
)

print(result)  # Content from your logged-in session
await browser.stop()
```

## What Happens

When `use_personal_profile=True`:

1. **Browser opens visibly** (`headless=False`) — You can watch it work
2. **Your Chrome profile loads** — All your cookies, logins, extensions
3. **Agent navigates to the URL** — Already authenticated
4. **Content is extracted** — No login walls or CAPTCHAs

## Chrome Profile Locations (Auto-Detected)

| OS | Default Location |
|----|------------------|
| macOS | `~/Library/Application Support/Google/Chrome` |
| Windows | `%LOCALAPPDATA%/Google/Chrome/User Data` |
| Linux | `~/.config/google-chrome` |

You can override with:
```python
llm_config={
    "use_personal_profile": True,
    "chrome_profile_dir": "/path/to/your/profile"
}
```

## Important Notes

### Chrome Must Be Closed
If Chrome is running, you'll get a profile lock error:
```
Failed to create browser context: Profile in use
```
Close all Chrome windows before running.

### Security Considerations
- Your cookies and session tokens are used
- The agent can access any site you're logged into
- Don't share recordings/screenshots if they contain sensitive data

### Rate Limiting Still Applies
Even when logged in, don't hammer the service:
- Add delays between requests
- Don't extract 100s of chats at once
- Space out your automation

## Troubleshooting

### "Profile in use" error
Close all Chrome windows completely. Check Activity Monitor/Task Manager for Chrome processes.

### Still seeing login page
Your session may have expired. Open Chrome normally, log in again, then close Chrome and retry.

### Agent can't find content
The page structure may have changed. Try:
- Increasing timeout (120s or more)
- Watching the browser to see what's happening
- Adjusting the extraction prompt in `agent_worker.py`

## Comparison: Anonymous vs Authenticated

| Aspect | Anonymous Profile | Authenticated Profile |
|--------|------------------|----------------------|
| Login required | Yes (often blocked) | No (already logged in) |
| CAPTCHA | Common | Rare |
| Rate limiting | Aggressive | Normal user limits |
| Content access | Public only | Your full account |
| Setup complexity | Low | Medium |
| Reliability | Low-Medium | High |

## Recommendation

For Monica/Kimi automation:
1. **Use authenticated profile** for reliable extraction
2. **Run on your machine** (not cloud) to avoid IP reputation issues
3. **Be respectful** — don't abuse the service, add delays
4. **Consider APIs first** — Claude API, OpenAI API are more reliable

## Example: Extract Your Kimi Chat History

```python
import asyncio
from aily.browser.manager import BrowserUseManager

async def extract_kimi_chats():
    browser = BrowserUseManager(worker_type="agent")
    await browser.start()

    try:
        # Go to Kimi while logged in
        result = await browser.fetch(
            "https://kimi.moonshot.cn",
            use_personal_profile=True,
            timeout=180  # Give it time to navigate
        )

        # The agent will:
        # 1. Load the page (already logged in)
        # 2. See your chat history/sidebar
        # 3. Explore and extract visible chats
        # 4. Return structured content

        print(f"Extracted {len(result)} characters")
        return result

    finally:
        await browser.stop()

# Run it
asyncio.run(extract_kimi_chats())
```

This is the most reliable way to automate Monica/Kimi because it uses your real user session.
