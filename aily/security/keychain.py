from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "aily"


class CredentialError(Exception):
    """Raised when credential operation fails."""
    pass


@dataclass
class Credential:
    account: str
    password: str
    service: str = SERVICE_NAME


class KeychainCredentialStore:
    """
    Secure credential storage using macOS Keychain.

    Replaces .env file storage for sensitive values like API keys.
    Uses the 'security' CLI tool to interact with Keychain.
    """

    def __init__(self, service: str = SERVICE_NAME) -> None:
        self.service = service

    async def get(self, account: str) -> Optional[str]:
        """
        Retrieve a credential from Keychain.

        Args:
            account: The account name (e.g., 'feishu_app_secret', 'openai_api_key')

        Returns:
            The credential value, or None if not found
        """
        try:
            result = subprocess.run(
                [
                    "security",
                    "find-generic-password",
                    "-s", self.service,
                    "-a", account,
                    "-w",  # Output password only
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            value = result.stdout.strip()
            logger.debug("Retrieved credential from keychain: %s", account)
            return value
        except subprocess.CalledProcessError as e:
            if e.returncode == 44:  # Item not found
                logger.debug("Credential not found in keychain: %s", account)
                return None
            logger.error("Failed to retrieve credential: %s (code %s)", account, e.returncode)
            raise CredentialError(f"Failed to retrieve {account}: {e}") from e
        except FileNotFoundError:
            raise CredentialError("security CLI not found - is this macOS?") from None

    async def set(self, account: str, password: str, update: bool = True) -> None:
        """
        Store a credential in Keychain.

        Args:
            account: The account name
            password: The credential value
            update: If True, updates existing credential; if False, raises error on duplicate
        """
        try:
            # Check if credential exists
            existing = await self.get(account)

            if existing is not None:
                if update:
                    # Delete old one first
                    await self.delete(account)
                else:
                    raise CredentialError(f"Credential already exists: {account}")

            subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-s", self.service,
                    "-a", account,
                    "-w", password,
                    "-U",  # Allow any user to access (for this user)
                ],
                capture_output=True,
                check=True,
            )
            logger.info("Stored credential in keychain: %s", account)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to store credential: %s", account)
            raise CredentialError(f"Failed to store {account}: {e}") from e

    async def delete(self, account: str) -> bool:
        """
        Delete a credential from Keychain.

        Args:
            account: The account name

        Returns:
            True if deleted, False if not found
        """
        try:
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-s", self.service,
                    "-a", account,
                ],
                capture_output=True,
                check=True,
            )
            logger.info("Deleted credential from keychain: %s", account)
            return True
        except subprocess.CalledProcessError as e:
            if e.returncode == 44:  # Item not found
                return False
            logger.error("Failed to delete credential: %s", account)
            raise CredentialError(f"Failed to delete {account}: {e}") from e

    async def list_accounts(self) -> list[str]:
        """
        List all accounts stored for this service.

        Returns:
            List of account names
        """
        try:
            result = subprocess.run(
                [
                    "security",
                    "dump-keychain",
                ],
                capture_output=True,
                text=True,
            )

            accounts = []
            current_account = None

            for line in result.stdout.split("\n"):
                if "svce" in line and f'"{self.service}"' in line:
                    # Found our service, capture next account
                    current_account = "pending"
                elif current_account == "pending" and "acct" in line:
                    # Extract account name from: acct<blob>="account_name"
                    import re
                    match = re.search(r'acct<blob>="([^"]+)"', line)
                    if match:
                        accounts.append(match.group(1))
                    current_account = None

            return accounts
        except subprocess.CalledProcessError as e:
            logger.error("Failed to list credentials: %s", e)
            raise CredentialError(f"Failed to list credentials: {e}") from e


class HybridCredentialStore:
    """
    Credentials resolver that tries Keychain first, falls back to environment.

    This allows gradual migration from .env files to Keychain.
    """

    def __init__(self, keychain: Optional[KeychainCredentialStore] = None) -> None:
        self.keychain = keychain or KeychainCredentialStore()
        self._fallback_cache: dict[str, str] = {}

    async def get(self, account: str, env_fallback: Optional[str] = None) -> Optional[str]:
        """
        Get credential from Keychain, with optional env fallback.

        Args:
            account: The credential account name
            env_fallback: Environment variable name to check if keychain fails

        Returns:
            Credential value or None
        """
        # Try keychain first
        try:
            value = await self.keychain.get(account)
            if value:
                return value
        except CredentialError:
            pass

        # Fall back to environment
        if env_fallback:
            import os
            value = os.environ.get(env_fallback)
            if value:
                logger.debug("Using env fallback for %s (%s)", account, env_fallback)
                return value

        return None

    async def migrate_from_env(self, account: str, env_var: str, delete_after: bool = False) -> bool:
        """
        Migrate a credential from environment variable to Keychain.

        Args:
            account: Account name to use in Keychain
            env_var: Environment variable name
            delete_after: If True, unset the env var after migration (note: only affects current process)

        Returns:
            True if migrated, False if env var not set
        """
        import os

        value = os.environ.get(env_var)
        if not value:
            return False

        await self.keychain.set(account, value)
        logger.info("Migrated %s -> keychain account '%s'", env_var, account)

        if delete_after:
            # Note: Can only unset from os.environ, not from .env file
            del os.environ[env_var]

        return True
