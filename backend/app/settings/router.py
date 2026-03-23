"""Settings API endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth.dependencies import get_current_user
from ..llm.provider import get_llm_provider
from ..models.user import User
from .service import get_llm_config, save_llm_config

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMConfigRequest(BaseModel):
    provider: str = ""      # "qwen-cloud" | "openai" | "vllm" | "custom"
    api_key: str = ""
    base_url: str = ""      # 自定义端点（vllm 或 openai-compatible API）
    model: str = ""


@router.get("/llm")
async def get_llm_settings(user: User = Depends(get_current_user)):
    """获取当前 LLM 配置（api_key 脱敏显示）。"""
    cfg = get_llm_config()
    # 脱敏 api_key
    key = cfg.get("api_key", "")
    if key:
        cfg["api_key"] = key[:6] + "***" + key[-4:] if len(key) > 10 else "***"
    cfg["configured"] = bool(get_llm_provider().list_providers())
    cfg["providers"] = get_llm_provider().list_providers()
    return cfg


@router.post("/llm")
async def update_llm_settings(body: LLMConfigRequest, user: User = Depends(get_current_user)):
    """保存 LLM 配置并立即生效（无需重启服务）。"""
    saved = save_llm_config(body.model_dump())
    # 返回时脱敏
    key = saved.get("api_key", "")
    if key:
        saved["api_key"] = key[:6] + "***" + key[-4:] if len(key) > 10 else "***"
    saved["providers"] = get_llm_provider().list_providers()
    saved["status"] = "saved"
    return saved


@router.post("/llm/test")
async def test_llm_connection(user: User = Depends(get_current_user)):
    """测试 LLM 连接是否正常。"""
    provider_obj = get_llm_provider()
    providers = provider_obj.list_providers()
    if not providers:
        return {"ok": False, "error": "No LLM provider configured"}
    try:
        result = await provider_obj.chat(
            [{"role": "user", "content": "reply with only: ok"}],
            max_tokens=10,
            temperature=0,
        )
        content = result["choices"][0]["message"]["content"]
        return {"ok": True, "response": content, "provider": providers[0]}
    except Exception as e:
        return {"ok": False, "error": str(e), "provider": providers[0] if providers else "none"}
