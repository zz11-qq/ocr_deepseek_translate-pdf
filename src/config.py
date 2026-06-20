"""Environment-based application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} 必须是整数，当前值：{raw_value!r}") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} 必须大于 0，当前值：{value}")
    return value


@dataclass(frozen=True)
class AppConfig:
    """Validated runtime settings loaded from a .env file."""

    baidu_api_key: str
    baidu_secret_key: str
    deepseek_api_key: str
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    ocr_render_dpi: int = 200
    translation_chunk_size: int = 2500

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> "AppConfig":
        """Load configuration and raise a clear error for missing credentials."""
        load_dotenv(dotenv_path=env_path, override=False)
        values = {
            "BAIDU_OCR_API_KEY": os.getenv("BAIDU_OCR_API_KEY", "").strip(),
            "BAIDU_OCR_SECRET_KEY": os.getenv("BAIDU_OCR_SECRET_KEY", "").strip(),
            "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", "").strip(),
        }
        missing = [
            name
            for name, value in values.items()
            if not value or value.startswith("your_")
        ]
        if missing:
            raise ConfigurationError(
                "缺少必要的 API 配置：" + ", ".join(missing) + "。请复制 .env.example 为 .env 并填写真实密钥。"
            )

        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise ConfigurationError("DEEPSEEK_BASE_URL 必须是有效的 HTTP(S) 地址。")

        return cls(
            baidu_api_key=values["BAIDU_OCR_API_KEY"],
            baidu_secret_key=values["BAIDU_OCR_SECRET_KEY"],
            deepseek_api_key=values["DEEPSEEK_API_KEY"],
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
            deepseek_base_url=base_url,
            ocr_render_dpi=_positive_int("OCR_RENDER_DPI", 200),
            translation_chunk_size=_positive_int("TRANSLATION_CHUNK_SIZE", 2500),
        )
