#!/usr/bin/env python3
"""Direct extraction from Monica using browser-use."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aily.config import SETTINGS


async def main():
    url = "https://monica.im/home/chat/Monica/monica?convId=conv%3Ab743d1ff-7dc1-4c59-8f0d-43d054fc15a7"
    
    print("=" * 60)
    print("Monica to Obsidian Pipeline")
    print("=" * 60)
    print(f"URL: {url}")
    print("\nStarting extraction using your Chrome profile...")
    
    # Import here to catch errors gracefully
    try:
        from browser_use import Agent, BrowserSession
        from browser_use.llm.openai.chat import ChatOpenAI
        import platform
    except ImportError as e:
        print(f"Error: {e}")
        return
    
    # Use personal Chrome profile
    system = platform.system()
    if system == "Darwin":
        chrome_profile = str(Path.home() / "Library/Application Support/Google/Chrome")
    else:
        chrome_profile = str(Path.home() / ".config/google-chrome")
    
    print(f"Chrome profile: {chrome_profile}")
    
    browser = BrowserSession(
        headless=False,
        user_data_dir=chrome_profile,
    )
    
    llm = ChatOpenAI(
        model=SETTINGS.llm_model,
        api_key=SETTINGS.llm_api_key,
        base_url=SETTINGS.llm_base_url,
    )
    
    agent = Agent(
        task=f"Go to {url} and extract the conversation content",
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Result: {result}")
    
    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
