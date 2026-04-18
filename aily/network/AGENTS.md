<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-18 | Updated: 2026-04-18 -->

# network

## Purpose

Network utilities for Tailscale integration. Provides VPN-based service discovery and secure internal networking between Aily instances.

## Key Files

| File | Description |
|------|-------------|
| `tailscale.py` | Tailscale API client and device discovery |

## For AI Agents

### Working In This Directory
- Tailscale is used for secure inter-node communication
- Device discovery lists peers on the tailnet
- Optional: not required for single-instance deployments

## Dependencies

### External
- `tailscale` CLI (system dependency)

<!-- MANUAL: -->
