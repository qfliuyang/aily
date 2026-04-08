# Monica/Kimi DOM Selectors Discovery

**Date:** 2026-04-08
**Purpose:** Identify DOM selectors for passive capture of Monica chats and Kimi reports

---

## Monica (monica.im)

### URL Patterns
- Chat interface: `https://monica.im/chat` or `https://monica.im/chat/*`
- Main page: `https://monica.im/`

### Authentication State Detection

**Logged out indicator:**
- Login modal present: `.auth-modal`, `[data-testid="login-modal"]`
- URL contains `/login` or shows login button

**Logged in indicator:**
- Sidebar visible: `.sidebar`, `[class*="sidebar"]`
- Chat list present: `.chat-list`, `[class*="chat-list"]`

### Chat Message Selectors

From analysis of Monica's interface:

**Primary selector strategy:**
```javascript
// Messages are typically in article or div containers with role attributes
const messages = document.querySelectorAll('article, [role="article"], .message-item');

// User messages (outgoing)
const userMessages = document.querySelectorAll(
  '[data-sender="user"], .user-message, [class*="user"] article'
);

// AI messages (incoming from Monica)
const aiMessages = document.querySelectorAll(
  '[data-sender="assistant"], .assistant-message, [class*="assistant"] article, [class*="monica"] article'
);
```

**Alternative strategy (text-based):**
```javascript
// Look for message pairs - alternating structure
const allMessages = document.querySelectorAll('main article, .chat-content article');
```

### New Chat Detection

Monica doesn't have a traditional "new chat notification." Strategy:

1. **URL-based detection:** Store last seen chat URL
2. **Message count tracking:** Compare current message count vs. last scan
3. **Timestamp comparison:** Look for messages newer than last capture time

```javascript
// Get all message timestamps
const timestamps = Array.from(document.querySelectorAll('[data-timestamp], time'))
  .map(el => new Date(el.getAttribute('datetime') || el.dataset.timestamp));
```

---

## Kimi (kimi.moonshot.cn)

### URL Patterns
- Chat interface: `https://kimi.moonshot.cn/chat/*`
- Main page: `https://kimi.moonshot.cn/`

### Authentication State Detection

**Logged in indicators:**
- User avatar present: `.user-avatar`, `[class*="avatar"]`
- Chat sidebar visible

### Chat Message Selectors

Based on typical React-based chat interfaces:

```javascript
// Kimi messages are usually in specific containers
const messages = document.querySelectorAll(
  '.message-content, [class*="message-content"], .chat-message'
);

// Distinguish user vs Kimi by position or attributes
messages.forEach((msg, index) => {
  const isUser = msg.classList.contains('user') ||
                 msg.closest('[data-role="user"]') ||
                 index % 2 === 0; // Alternating pattern
});
```

### Report/Document Extraction

Kimi can generate reports/documents:

```javascript
// Look for document containers
const docs = document.querySelectorAll(
  '.document-viewer, .report-container, [class*="document"]'
);

// Export buttons indicate downloadable content
const exportBtn = document.querySelector('[data-action="export"], .export-btn');
```

---

## Implementation Strategy

### Phase 1: URL-based Detection (Current)

Since DOM selectors are fragile with React apps, start with URL-based approach:

1. Monitor `chrome.history` or browser tabs for new Monica/Kimi URLs
2. When new chat URL detected, enqueue for capture
3. Browser Use navigates to URL and extracts full page content

### Phase 2: Content-based Extraction

```python
# In passive capture scheduler
async def _detect_urls(self) -> list[str]:
    # Query browser for open Monica/Kimi tabs
    # Check if any are new (not seen in last 24h)
    # Return list of URLs to capture
    pass
```

### Phase 3: DOM-based Change Detection (Future)

If URL-based isn't sufficient, inject content script to:
- Listen for new messages via MutationObserver
- Send message to background script
- Background script notifies Aily via local HTTP endpoint

---

## Browser Use Configuration

For Browser Use to work with Monica/Kimi:

```python
browser_config = {
    "headless": False,  # May need visible browser for auth
    "user_data_dir": "~/.aily/browser_profile",  # Persist login
    "args": [
        "--disable-blink-features=AutomationControlled",  # Hide automation
    ]
}
```

### Extraction Prompt for Browser Use

```python
extraction_prompt = """
You are on a Monica chat page. Extract the conversation content:
1. Identify all user messages
2. Identify all Monica (AI) responses
3. Format as markdown with clear role labels
4. Preserve any code blocks, links, or formatting

If the page shows a login modal, report "AUTH_REQUIRED".
If the page shows no chat content, report "NO_CONTENT".
"""
```

---

## Validation Checklist

- [x] Monica interface analyzed via screenshots
- [ ] Live browser test with authenticated session
- [ ] Chinese text extraction verified
- [ ] Kimi interface tested
- [ ] Document/report download tested
- [ ] Error handling for auth expiration

---

## Fallback Strategy

If DOM selectors prove too fragile:

1. **Manual URL sharing:** User copies chat URL, sends to Feishu bot
2. **Bookmarklet:** JavaScript bookmarklet extracts content, sends to Aily
3. **Export feature:** Use Monica/Kimi's native export, file watcher picks up downloads
