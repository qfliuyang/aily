<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# security

## Purpose

Credential and secret management. Provides secure storage and retrieval for API keys and sensitive configuration.

## Key Files

| File | Description |
|------|-------------|
| `keychain.py` | `Keychain` — secure credential storage abstraction |

## For AI Agents

### Working In This Directory
- Keychain abstracts OS-specific credential stores
- Fallback to environment variables if keychain unavailable
- Never log or expose secrets in error messages

## Dependencies

### External
- Platform keychain libraries (macOS Keychain, Linux Secret Service)

<!-- MANUAL: -->
