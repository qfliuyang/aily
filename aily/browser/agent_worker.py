"""
Browser-use Agent-based subprocess worker for AI-powered browser automation.

Replaces raw Playwright with browser-use library for:
- AI-powered content extraction
- Natural language tasking
- Better handling of dynamic/JavaScript-heavy pages
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any

# Add virtualenv site-packages to path for subprocess
venv_site_packages = Path(sys.executable).parent.parent / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
if venv_site_packages.exists():
    sys.path.insert(0, str(venv_site_packages))

logger = logging.getLogger(__name__)


async def _fetch_with_agent(url: str, timeout: int, profile_dir: str, llm_config: dict | None = None) -> dict[str, Any]:
    """
    Use browser-use Agent to intelligently extract content from a URL.

    Args:
        url: The URL to fetch
        timeout: Maximum time to spend on the task
        profile_dir: Browser profile directory for persistence
        llm_config: Optional LLM configuration (provider, model, api_key)

    Returns:
        dict with 'text' (extracted content), 'title', and 'metadata'
    """
    from browser_use import Agent, BrowserSession
    from browser_use.llm.openai.chat import ChatOpenAI
    from browser_use.llm.openai.like import ChatOpenAILike
    from browser_use.llm.google.chat import ChatGoogle
    from browser_use.llm.anthropic.chat import ChatAnthropic

    # Configure LLM based on config or environment
    llm_config = llm_config or {}
    provider = llm_config.get('provider', 'openai')
    model = llm_config.get('model', 'gpt-4o-mini')
    api_key = llm_config.get('api_key') or _get_api_key(provider)

    # Initialize LLM based on provider
    if provider == 'openai':
        # Check if using a custom base_url (OpenAI-compatible API like Zhipu)
        base_url = llm_config.get('base_url')
        if base_url and 'openai.com' not in base_url:
            # Use ChatOpenAILike for OpenAI-compatible providers (Zhipu, etc.)
            # with compatibility settings for providers that don't support strict json_schema
            llm = ChatOpenAILike(
                model=model,
                api_key=api_key,
                base_url=base_url,
                add_schema_to_system_prompt=True,  # Add schema to prompt instead of response_format
                remove_min_items_from_schema=True,  # Remove minItems for compatibility
                remove_defaults_from_schema=True,   # Remove defaults for compatibility
                dont_force_structured_output=False,  # Still try structured output
            )
        else:
            llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url)
    elif provider == 'google':
        llm = ChatGoogle(model=model, api_key=api_key)
    elif provider == 'anthropic':
        llm = ChatAnthropic(model=model, api_key=api_key)
    else:
        # Default to OpenAI
        llm = ChatOpenAI(model='gpt-4o-mini', api_key=api_key)

    # Support using Chrome profile with existing logins
    chrome_profile = llm_config.get('chrome_profile_dir', profile_dir)
    headless = llm_config.get('headless', True)
    use_personal_profile = llm_config.get('use_personal_profile', False)

    if use_personal_profile:
        # Use user's actual Chrome profile where they're logged in
        import platform
        system = platform.system()
        if system == 'Darwin':  # macOS
            chrome_profile = llm_config.get(
                'chrome_profile_dir',
                str(Path.home() / 'Library/Application Support/Google/Chrome')
            )
        elif system == 'Windows':
            chrome_profile = llm_config.get(
                'chrome_profile_dir',
                str(Path.home() / 'AppData/Local/Google/Chrome/User Data')
            )
        else:  # Linux
            chrome_profile = llm_config.get(
                'chrome_profile_dir',
                str(Path.home() / '.config/google-chrome')
            )
        headless = False  # Must be visible to use personal profile
        logger.info("Using personal Chrome profile: %s", chrome_profile)

    # Create browser session with profile
    browser_kwargs = {
        'headless': headless,
    }
    if chrome_profile and Path(chrome_profile).exists():
        browser_kwargs['user_data_dir'] = chrome_profile

    browser = BrowserSession(**browser_kwargs)

    # Create agent with extraction task
    is_logged_in = llm_config.get('use_personal_profile', False) if llm_config else False
    login_hint = "You are already logged in. " if is_logged_in else ""

    extraction_task = f"""
    Navigate to {url} and extract the main content.

    Instructions:
    1. Navigate to the URL and wait for page to fully load (up to 30 seconds)
    2. If you see a chat interface, explore it and extract visible conversations
    3. If you see a history/sidebar, click through recent items to gather content
    4. {login_hint}If logged in, access the user's content directly
    5. If there's a login modal and you're not logged in, report "AUTH_REQUIRED"
    6. Extract the main readable content (chat, article, or document)
    7. Preserve the structure (headings, lists, code blocks, chat messages)
    8. Add small delays (1-2 seconds) between actions to avoid rate limiting
    9. Return the content in markdown format

    Be thorough but focus on the main content area, not navigation or ads.
    """

    agent = Agent(
        task=extraction_task,
        llm=llm,
        browser=browser,
    )

    try:
        # Run the agent with timeout
        result = await asyncio.wait_for(
            agent.run(),
            timeout=timeout
        )

        # Extract content from agent result
        extracted_text = result.extracted_content() if hasattr(result, 'extracted_content') else str(result)

        # Get page info if available
        page_title = "Untitled"
        if hasattr(agent, 'browser') and agent.browser:
            try:
                page_title = await agent.browser.get_page_title()
            except Exception:
                pass

        return {
            'status': 'ok',
            'text': extracted_text,
            'title': page_title,
            'url': url,
            'metadata': {
                'agent_steps': len(result.history) if hasattr(result, 'history') else 0,
            }
        }

    except asyncio.TimeoutError:
        return {
            'status': 'error',
            'message': f'Agent timeout after {timeout}s',
            'url': url,
        }
    except Exception as exc:
        logger.exception("Agent failed for %s", url)
        return {
            'status': 'error',
            'message': str(exc),
            'url': url,
        }
    finally:
        try:
            await browser.close()
        except Exception:
            pass


def _get_api_key(provider: str) -> str | None:
    """Get API key from environment variables."""
    import os
    env_vars = {
        'openai': 'OPENAI_API_KEY',
        'google': 'GOOGLE_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
    }
    return os.environ.get(env_vars.get(provider, 'OPENAI_API_KEY'))


def _run_loop(listener, fetch_fn):
    """Main IPC loop handling fetch requests."""
    while True:
        with listener.accept() as conn:
            while True:
                try:
                    msg = conn.recv()
                except EOFError:
                    break

                if msg.get("type") == "shutdown":
                    conn.send({"status": "ok"})
                    return

                if msg.get("type") == "fetch":
                    url = msg.get("url")
                    timeout = msg.get("timeout", 60)
                    profile_dir = msg.get("profile_dir", "")
                    llm_config = msg.get("llm_config")

                    try:
                        result = fetch_fn(url, timeout, profile_dir, llm_config)
                        conn.send(result)
                    except Exception as exc:
                        logger.exception("Fetch failed for %s", url)
                        conn.send({
                            "status": "error",
                            "message": str(exc),
                            "url": url,
                        })

                elif msg.get("type") == "agent_task":
                    # Support for custom agent tasks
                    url = msg.get("url")
                    task = msg.get("task")
                    timeout = msg.get("timeout", 120)
                    profile_dir = msg.get("profile_dir", "")
                    llm_config = msg.get("llm_config")

                    try:
                        result = asyncio.run(_run_custom_task(
                            url, task, timeout, profile_dir, llm_config
                        ))
                        conn.send(result)
                    except Exception as exc:
                        logger.exception("Custom task failed for %s", url)
                        conn.send({
                            "status": "error",
                            "message": str(exc),
                            "url": url,
                        })

                else:
                    conn.send({"status": "error", "message": "Unknown type"})


async def _run_custom_task(
    url: str,
    task: str,
    timeout: int,
    profile_dir: str,
    llm_config: dict | None = None
) -> dict[str, Any]:
    """Run a custom agent task on a URL."""
    from browser_use import Agent, BrowserSession
    from browser_use.llm.openai.chat import ChatOpenAI
    from browser_use.llm.openai.like import ChatOpenAILike

    llm_config = llm_config or {}
    provider = llm_config.get('provider', 'openai')
    model = llm_config.get('model', 'gpt-4o-mini')
    api_key = llm_config.get('api_key') or _get_api_key(provider)
    base_url = llm_config.get('base_url')

    # Use ChatOpenAILike for non-OpenAI providers with compatibility settings
    if base_url and 'openai.com' not in base_url:
        llm = ChatOpenAILike(
            model=model,
            api_key=api_key,
            base_url=base_url,
            add_schema_to_system_prompt=True,
            remove_min_items_from_schema=True,
            remove_defaults_from_schema=True,
        )
    else:
        llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url)

    browser = BrowserSession(
        headless=True,
        user_data_dir=profile_dir,
    )

    full_task = f"Navigate to {url} and {task}"

    agent = Agent(
        task=full_task,
        llm=llm,
        browser=browser,
    )

    try:
        result = await asyncio.wait_for(agent.run(), timeout=timeout)

        return {
            'status': 'ok',
            'text': str(result),
            'url': url,
        }
    except asyncio.TimeoutError:
        return {
            'status': 'error',
            'message': f'Task timeout after {timeout}s',
        }
    finally:
        try:
            await browser.close()
        except Exception:
            pass


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", required=True)
    parser.add_argument("--authkey", default="aily-browser")
    args = parser.parse_args(argv)

    authkey = args.authkey.encode()
    profile_dir = args.profile_dir

    # Ensure profile directory exists
    Path(profile_dir).mkdir(parents=True, exist_ok=True)

    with Listener(("localhost", 0), authkey=authkey) as listener:
        print(f"READY {listener.address[1]}", flush=True)
        _run_loop(
            listener,
            lambda url, timeout, prof, llm: asyncio.run(
                _fetch_with_agent(url, timeout, prof or profile_dir, llm)
            ),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
