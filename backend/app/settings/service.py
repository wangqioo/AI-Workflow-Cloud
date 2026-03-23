"""LLM and application settings service - persisted to JSON file."""

import json
import os
from pathlib import Path

# 默认存放到 backend/data/settings.json（相对于 backend 目录）
_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "settings.json"
)
_CONFIG_PATH = Path(os.environ.get("SETTINGS_PATH", _DEFAULT_PATH))

_DEFAULT_LLM = {
    "provider": "",          # "qwen-cloud" | "openai" | "vllm" | "custom"
    "api_key": "",
    "base_url": "",          # 自定义 base URL（vllm 或 openai-compatible）
    "model": "",
    "default_provider": "",  # 覆盖 settings.llm_default_provider
}


def _load() -> dict:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text())
    except Exception:
        pass
    return {}


def _save(data: dict):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_llm_config() -> dict:
    data = _load()
    return {**_DEFAULT_LLM, **data.get("llm", {})}


def save_llm_config(config: dict) -> dict:
    data = _load()
    # 只保留已知字段，不存空 api_key（防止覆盖已有的）
    merged = {**data.get("llm", {})}
    for k, v in config.items():
        if k in _DEFAULT_LLM:
            if v or k not in merged:
                merged[k] = v
    data["llm"] = merged
    _save(data)

    # 动态更新 LLM provider
    _apply_llm_config(merged)
    return merged


def _apply_llm_config(cfg: dict):
    """把保存的配置实时注入到 LLM provider 单例。"""
    from ..llm.provider import get_llm_provider, ProviderConfig
    from ..config import settings

    provider = get_llm_provider()
    name = cfg.get("provider") or cfg.get("default_provider") or ""
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "")
    model = cfg.get("model", "")

    if name == "qwen-cloud":
        provider._providers["qwen-cloud"] = ProviderConfig(
            "qwen-cloud",
            base_url or settings.qwen_base_url,
            api_key,
            model or settings.qwen_model,
        )
        provider._providers.setdefault  # ensure key exists
        settings.__dict__["llm_default_provider"] = "qwen-cloud"

    elif name == "openai":
        provider._providers["openai"] = ProviderConfig(
            "openai",
            base_url or settings.openai_base_url,
            api_key,
            model or settings.openai_model,
        )
        settings.__dict__["llm_default_provider"] = "openai"

    elif name in ("vllm", "custom"):
        provider._providers["vllm"] = ProviderConfig(
            "vllm",
            base_url or settings.vllm_base_url,
            api_key,
            model or settings.vllm_model,
        )
        settings.__dict__["llm_default_provider"] = "vllm"

    if name:
        settings.__dict__["llm_default_provider"] = name if name != "custom" else "vllm"


def apply_saved_config_on_startup():
    """服务启动时自动应用已保存的 LLM 配置。"""
    cfg = get_llm_config()
    if cfg.get("provider") or cfg.get("api_key"):
        _apply_llm_config(cfg)
