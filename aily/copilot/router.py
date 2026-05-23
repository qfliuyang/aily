"""FastAPI router for Aily-Copilot product APIs."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection

from aily.copilot.chat import ChatLLM, CopilotVaultChatService
from aily.copilot.context import CopilotContextEnvelopeBuilder
from aily.copilot.vault import VaultSearchService
from aily.dossier import DossierBuildRequest, DossierService
from aily.security.rate_limit import FixedWindowRateLimiter
from aily.writer.vault_layout import inspect_v1_vault_layout


class VaultSearchRequest(BaseModel):
    query: str = ""
    limit: int = Field(default=10, ge=1, le=50)
    include_dirs: list[str] = Field(default_factory=list)
    exclude_dirs: list[str] = Field(default_factory=list)


class ReadNoteRequest(BaseModel):
    path: str
    chunk_index: int = Field(default=0, ge=0)
    chunk_lines: int = Field(default=180, ge=25, le=500)


class NeighborhoodRequest(BaseModel):
    path: str
    limit: int = Field(default=20, ge=1, le=100)


class ContextEnvelopeRequest(BaseModel):
    user_message: str
    search_results: list[dict[str, Any]] = Field(default_factory=list)
    previous_context: list[dict[str, Any]] = Field(default_factory=list)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    system_prompt: str | None = None


class ChatRequest(BaseModel):
    message: str
    search_query: str = ""
    limit: int = Field(default=8, ge=1, le=20)
    include_dirs: list[str] = Field(default_factory=list)
    exclude_dirs: list[str] = Field(default_factory=list)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    use_llm: bool = True


class DossierGenerateRequest(BaseModel):
    topic: str
    query_terms: list[str] = Field(default_factory=list)
    seed_claims: list[str] = Field(default_factory=list)
    max_vault_evidence: int = Field(default=40, ge=5, le=120)
    max_tavily_evidence: int = Field(default=20, ge=0, le=80)


def create_copilot_router(
    *,
    vault_path: Path,
    llm_client_factory: Callable[[], ChatLLM] | None = None,
    auth_token: str = "",
    rate_limiter: FixedWindowRateLimiter | None = None,
    trust_proxy_headers: bool = False,
) -> APIRouter:
    vault = vault_path.expanduser().resolve()
    search_service = VaultSearchService(vault)
    context_builder = CopilotContextEnvelopeBuilder()
    chat_service = CopilotVaultChatService(vault_search=search_service, context_builder=context_builder)
    dossier_service = DossierService()

    def _request_authorized(request: HTTPConnection) -> bool:
        if not auth_token:
            return True
        bearer = request.headers.get("authorization", "")
        explicit_token = request.headers.get("x-aily-token", "")
        query_token = request.query_params.get("token", "")
        cookie_token = request.cookies.get("aily_ui_token", "")
        return (
            bearer == f"Bearer {auth_token}"
            or explicit_token == auth_token
            or query_token == auth_token
            or cookie_token == auth_token
        )

    async def _require_auth(request: HTTPConnection) -> None:
        if not _request_authorized(request):
            raise HTTPException(status_code=401, detail="Aily-Copilot authentication required")

    router = APIRouter(prefix="/api/copilot", tags=["copilot"], dependencies=[Depends(_require_auth)])

    def _client_key(request: HTTPConnection) -> str:
        if trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                return forwarded_for.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"

    def _check_rate_limit(request: HTTPConnection) -> None:
        if rate_limiter is None:
            return
        allowed, retry_after = rate_limiter.allow(_client_key(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    @router.get("/status")
    async def status() -> dict[str, Any]:
        return {
            "status": "ok",
            "vault_path": str(vault),
            "vault_exists": vault.exists(),
            "layout": inspect_v1_vault_layout(vault),
            "features": {
                "vault_search": True,
                "read_note": True,
                "context_envelope": True,
                "graph_neighborhood": True,
                "grounded_chat": True,
                "dossier_generation": True,
            },
        }

    @router.post("/vault/search")
    async def search_vault(request: Request, payload: VaultSearchRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        return await asyncio.to_thread(
            search_service.search,
            payload.query,
            limit=payload.limit,
            include_dirs=payload.include_dirs,
            exclude_dirs=payload.exclude_dirs,
        )

    @router.post("/vault/read")
    async def read_note(request: Request, payload: ReadNoteRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        try:
            return await asyncio.to_thread(
                search_service.read_note,
                payload.path,
                chunk_index=payload.chunk_index,
                chunk_lines=payload.chunk_lines,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/vault/neighborhood")
    async def graph_neighborhood(request: Request, payload: NeighborhoodRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        try:
            return await asyncio.to_thread(search_service.neighborhood, payload.path, limit=payload.limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/context/envelope")
    async def context_envelope(request: Request, payload: ContextEnvelopeRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        return context_builder.build(
            user_message=payload.user_message,
            search_results=payload.search_results,
            previous_context=payload.previous_context,
            chat_history=payload.chat_history,
            system_prompt=payload.system_prompt,
        )

    @router.post("/chat")
    async def chat(request: Request, payload: ChatRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        llm_client = llm_client_factory() if payload.use_llm and llm_client_factory is not None else None
        return await chat_service.answer(
            message=payload.message,
            search_query=payload.search_query,
            limit=payload.limit,
            include_dirs=payload.include_dirs,
            exclude_dirs=payload.exclude_dirs,
            chat_history=payload.chat_history,
            use_llm=payload.use_llm,
            llm_client=llm_client,
        )

    @router.post("/dossiers/generate")
    async def generate_dossier(request: Request, payload: DossierGenerateRequest) -> dict[str, Any]:
        _check_rate_limit(request)
        try:
            result = await asyncio.to_thread(
                dossier_service.build_and_write,
                DossierBuildRequest(
                    topic=payload.topic,
                    vault_path=vault,
                    query_terms=payload.query_terms or [payload.topic],
                    seed_claims=payload.seed_claims,
                    tavily_research_jobs=[],
                    max_vault_evidence=payload.max_vault_evidence,
                    max_tavily_evidence=payload.max_tavily_evidence,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Dossier generation failed: {exc}") from exc
        return {
            "dossier_id": result.draft.dossier_id,
            "topic": result.draft.topic,
            "title": result.draft.title,
            "output_path": str(result.output_path or ""),
            "relative_path": (
                str(result.output_path.relative_to(vault))
                if result.output_path is not None and _is_relative_to(result.output_path, vault)
                else ""
            ),
            "claim_count": len(result.draft.claims),
            "evidence_count": len(result.draft.evidence),
            "verification": result.draft.verification.__dict__ if result.draft.verification else None,
        }

    return router


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
