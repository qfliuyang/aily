# Aily Production-Grade Testing Strategy

Aily's test suite should guide the project toward production readiness, not only keep the build green. Every test should declare which risk it reduces and which production contract it enforces.

## Test lanes

| Lane | Marker | Purpose | External credentials |
| --- | --- | --- | --- |
| Unit | `unit` | Pure logic and small isolated units. Mocks are allowed. | No |
| Contract | `contract` | Boundary behavior against real local stores/transports with fake external services. | No |
| Security | `security` | Threat-model invariants and regression tests. | No by default |
| Integration | `integration` | Multiple local components working together. | Prefer no |
| E2E local | `e2e` | Product-shaped flow with local substitutions declared in an acceptance manifest. | Maybe |
| Real service | `real_service` | Feishu, Obsidian REST, browser services, provider APIs. | Yes |
| Acceptance | `acceptance` | Release evidence with real required boundaries and no undeclared fakes. | Yes |

Root pytest uses `--strict-markers`; new tests must choose one semantic lane. `slow` is a runtime modifier, not a lane by itself. Do not add nested `pytest.ini` files under `tests/`; they can change pytest root discovery and bypass parent `conftest.py` enforcement.

## Acceptance boundary rule

Acceptance evidence must declare whether these boundaries are real:

- LLM/provider
- graph database
- queue worker/lifespan
- writer API (Obsidian REST, not direct filesystem substitution)
- HTTP/browser fetching
- fake/substituted components

Local E2E tests may use substitutions, but then they are local integration evidence, not production acceptance evidence. The acceptance guard is global in `tests/conftest.py`: any test marked `acceptance`, in any directory, must provide an `acceptance_boundary_manifest` whose required boundaries are all real and whose `fake_components` list is empty.

## Regression-test template

Every production bug fix should add a regression with:

1. The exact invariant that failed.
2. A negative case that would have failed before the fix.
3. A success case that proves normal behavior still works.
4. No broad private-function patch that bypasses the contract under test.
5. A public-path or boundary-level test when the risk involves integration wiring.

## Health gate

`scripts/verify_project_health.py --check` compares current suite debt with `tests/quality_baseline.json`. The baseline is count- and identity-aware: it fails when a debt category count increases, when an error finding appears, or when a new finding key appears that is not explicitly accepted. This allows incremental improvement without hiding debt swaps. New work should reduce counts and remove accepted findings where possible; increasing the baseline requires an explicit decision.

The health report tracks:

- skipped tests
- tests without explicit assertions
- mock/patch/monkeypatch use
- missing pytest lane contract
- acceptance-boundary declarations
- generated artifacts
- stale docs and dead-code candidates

## Problem exposure rule

Real-service tests may expose rich diagnostics, but the API must distinguish observations from problems. Use `record_observation(...)` for telemetry and `expose_problem(...)` for production-blocking behavior. Merge-gated exposure assertions are fail-closed and cannot be disabled with environment variables. The legacy `expose(...)` method is only for existing tests and must use explicit `blocking=` when a category is ambiguous. Exploratory “learn something” scripts belong outside the merge gate unless their observations are converted into enforceable assertions.
