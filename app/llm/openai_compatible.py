"""Generic OpenAI-compatible chat and structured-output client factories."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.env import load_local_env
from app.core.http import choose_http_proxy


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少 {name}。请在 .env.local 中配置后重试。")
    return value


def resolve_openai_compatible_proxy() -> str | None:
    """Prefer a provider-specific proxy, then use the shared HTTP proxy setting."""
    proxy = os.getenv("OPENAI_COMPATIBLE_HTTP_PROXY", "").strip()
    if proxy.startswith(("http://", "https://")):
        return proxy
    return choose_http_proxy()


def build_chat_openai_compatible(*, temperature: float = 0) -> Any:
    """Build a chat client from explicit OpenAI-compatible endpoint settings."""
    load_local_env()
    api_key = _required_setting("OPENAI_COMPATIBLE_API_KEY")
    base_url = _required_setting("OPENAI_COMPATIBLE_BASE_URL").rstrip("/")
    model = _required_setting("OPENAI_COMPATIBLE_MODEL")

    try:
        import httpx
        from langchain_openai import ChatOpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("缺少 httpx 或 langchain-openai。请先安装依赖。") from exc

    proxy = resolve_openai_compatible_proxy()
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        http_client=httpx.Client(proxy=proxy, trust_env=False),
        http_async_client=httpx.AsyncClient(proxy=proxy, trust_env=False),
        http_socket_options=(),
    )


def build_structured_openai_compatible(
    schema: type[SchemaT],
    *,
    temperature: float = 0,
) -> Any:
    """Bind a Pydantic schema through strict function calling."""
    llm = build_chat_openai_compatible(temperature=temperature)
    return llm.with_structured_output(schema, method="function_calling", strict=True)
