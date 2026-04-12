from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings

from aily.thinking.config import ThinkingConfig


@dataclass
class MindsConfig:
    """Configuration for Aily Three-Mind System.

    Controls the DIKIWI Mind (continuous), Innovation Mind (8am daily),
    and Entrepreneur Mind (9am daily).
    """

    # Feature toggles
    dikiwi_enabled: bool = True
    innovation_enabled: bool = True
    entrepreneur_enabled: bool = True

    # Schedule times (24-hour format)
    innovation_time: time = field(default_factory=lambda: time(8, 0))
    entrepreneur_time: time = field(default_factory=lambda: time(9, 0))

    # Quality thresholds
    proposal_min_confidence: float = 0.7  # Raised from 0.5 per eng review
    proposal_max_per_session: int = 10

    # Circuit breaker settings
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery_minutes: int = 30

    # LLM batching/caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    batch_proposals: bool = True

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "MindsConfig":
        """Create MindsConfig from settings dict (e.g., from env vars)."""
        config = cls()

        # Parse boolean flags
        config.dikiwi_enabled = settings.get("aily_dikiwi_enabled", "true").lower() == "true"
        config.innovation_enabled = settings.get("aily_innovation_enabled", "true").lower() == "true"
        config.entrepreneur_enabled = settings.get("aily_entrepreneur_enabled", "true").lower() == "true"

        # Parse times
        innovation_time_str = settings.get("aily_innovation_time", "08:00")
        entrepreneur_time_str = settings.get("aily_entrepreneur_time", "09:00")
        config.innovation_time = cls._parse_time(innovation_time_str)
        config.entrepreneur_time = cls._parse_time(entrepreneur_time_str)

        # Parse floats/ints
        config.proposal_min_confidence = float(settings.get("aily_proposal_min_confidence", "0.7"))
        config.proposal_max_per_session = int(settings.get("aily_proposal_max_per_session", "10"))
        config.circuit_breaker_threshold = int(settings.get("aily_circuit_breaker_threshold", "3"))

        return config

    @staticmethod
    def _parse_time(time_str: str) -> time:
        """Parse time string like '08:00' or '8:30'."""
        try:
            parts = time_str.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return time(hour, minute)
        except (ValueError, IndexError):
            return time(8, 0)  # Default fallback

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors (empty if valid)."""
        errors = []

        if not 0.0 <= self.proposal_min_confidence <= 1.0:
            errors.append(f"proposal_min_confidence must be between 0 and 1, got {self.proposal_min_confidence}")

        if self.proposal_max_per_session < 1:
            errors.append(f"proposal_max_per_session must be >= 1, got {self.proposal_max_per_session}")

        if self.circuit_breaker_threshold < 1:
            errors.append(f"circuit_breaker_threshold must be >= 1, got {self.circuit_breaker_threshold}")

        # Check that innovation and entrepreneur times don't overlap
        innovation_end = self.innovation_time.replace(minute=self.innovation_time.minute + 30)
        if self.innovation_enabled and self.entrepreneur_enabled:
            if innovation_end.hour > self.entrepreneur_time.hour or \
               (innovation_end.hour == self.entrepreneur_time.hour and innovation_end.minute >= self.entrepreneur_time.minute):
                errors.append("Innovation and Entrepreneur times may overlap (need 30 min gap)")

        return errors


class Settings(BaseSettings):
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    obsidian_rest_api_key: str = ""
    obsidian_vault_path: str = ""
    dikiwi_vault_path: str = str(Path.home() / "obsidian" / "aily-dikiwi")
    obsidian_rest_api_port: int = 27123
    llm_provider: str = "zhipu"
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-flash"
    llm_max_concurrency: int = 1
    llm_min_interval_seconds: float = 3.0
    dikiwi_max_llm_calls_per_source: int = 30
    dikiwi_stage_round_limit: int = 4
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-plus"

    # Tavily search API
    tavily_api_key: str = ""
    tavily_search_depth: str = "basic"  # "basic" or "advanced"

    # Browser Use commercial API
    browser_use_api_key: str = ""

    aily_digest_enabled: bool = True
    aily_digest_hour: int = 9
    aily_digest_minute: int = 0
    aily_digest_feishu_open_id: str = ""
    aily_data_dir: Path = Path.home() / ".aily"

    # Voice memo settings
    feishu_voice_enabled: bool = False  # Disabled by default until configured
    whisper_api_key: str = ""  # Falls back to llm_api_key if empty
    whisper_model: str = "whisper-1"
    voice_temp_dir: Path = Path("/tmp/aily_voice")

    # File processing limits (bytes)
    max_file_size: int = 50 * 1024 * 1024  # 50MB default limit
    max_image_size: int = 10 * 1024 * 1024  # 10MB for images (OCR memory limit)

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def queue_db_path(self) -> Path:
        return self.aily_data_dir / "aily_queue.db"

    @property
    def graph_db_path(self) -> Path:
        return self.aily_data_dir / "aily_graph.db"

    # Thinking system configuration
    thinking: ThinkingConfig = ThinkingConfig()

    # Three-Mind System configuration
    minds: MindsConfig = field(default_factory=MindsConfig)

    def model_post_init(self, __context: Any) -> None:
        """Initialize minds config from environment after main init."""
        if not self.zhipu_api_key and self.llm_provider.lower() == "zhipu":
            self.zhipu_api_key = self.llm_api_key
        if self.llm_provider.lower() == "zhipu":
            self.llm_base_url = "https://open.bigmodel.cn/api/paas/v4"
            self.llm_model = self.zhipu_model or self.llm_model

        # Parse minds config from env vars
        import os
        env_vars = {
            k.lower().replace("aily_", ""): v
            for k, v in os.environ.items()
            if k.startswith("AILY_")
        }
        self.minds = MindsConfig.from_settings(env_vars)

        # Validate and log any errors
        errors = self.minds.validate()
        if errors:
            import logging
            for error in errors:
                logging.getLogger(__name__).warning("MindsConfig validation: %s", error)


SETTINGS = Settings()
