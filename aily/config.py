from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    obsidian_rest_api_key: str = ""
    obsidian_vault_path: str = ""
    obsidian_rest_api_port: int = 27123
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

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

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def queue_db_path(self) -> Path:
        return self.aily_data_dir / "aily_queue.db"

    @property
    def graph_db_path(self) -> Path:
        return self.aily_data_dir / "aily_graph.db"


SETTINGS = Settings()
