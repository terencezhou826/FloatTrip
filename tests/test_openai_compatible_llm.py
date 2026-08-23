from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from app.llm import factory
from app.planning.schemas import PlannerTravelRoute


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SmokeSchema(BaseModel):
    ok: bool
    message: str


class FakeChatOpenAI:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.structured_calls = []
        self.__class__.calls.append(kwargs)

    def with_structured_output(self, schema, **kwargs):
        self.structured_calls.append((schema, kwargs))
        return {"client": self, "schema": schema, "options": kwargs}


@pytest.fixture(autouse=True)
def isolated_openai_compatible_env(monkeypatch):
    for name in (
        "LLM_PROVIDER",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_BASE_URL",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_HTTP_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "https_proxy",
        "http_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    FakeChatOpenAI.calls.clear()


def _configure(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://llm.example/v1/")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "configured-model-id")


def _fake_clients(monkeypatch):
    sync_clients = []
    async_clients = []

    def sync_client(**kwargs):
        sync_clients.append(kwargs)
        return ("sync", kwargs)

    def async_client(**kwargs):
        async_clients.append(kwargs)
        return ("async", kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("httpx.Client", sync_client)
    monkeypatch.setattr("httpx.AsyncClient", async_client)
    return sync_clients, async_clients


def test_factory_resolves_openai_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    assert factory.resolve_llm_provider() == "openai_compatible"


@pytest.mark.parametrize(
    ("missing", "message"),
    [
        ("OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_API_KEY"),
        ("OPENAI_COMPATIBLE_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL"),
        ("OPENAI_COMPATIBLE_MODEL", "OPENAI_COMPATIBLE_MODEL"),
    ],
)
def test_missing_required_configuration_fails(monkeypatch, missing, message):
    _configure(monkeypatch)
    monkeypatch.delenv(missing)
    monkeypatch.setattr(
        "app.llm.openai_compatible.load_local_env", lambda: None
    )

    from app.llm.openai_compatible import build_chat_openai_compatible

    with pytest.raises(RuntimeError, match=message):
        build_chat_openai_compatible()


def test_chat_client_uses_exact_configuration_without_provider_extras(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("OPENAI_COMPATIBLE_HTTP_PROXY", "http://127.0.0.1:7890")
    sync_clients, async_clients = _fake_clients(monkeypatch)

    client = factory.build_chat_llm(
        model="must-not-override-openai-compatible-config",
        temperature=0.3,
    )

    assert isinstance(client, FakeChatOpenAI)
    assert client.kwargs["model"] == "configured-model-id"
    assert client.kwargs["base_url"] == "https://llm.example/v1"
    assert client.kwargs["api_key"] == "test-key"
    assert client.kwargs["temperature"] == 0.3
    assert "extra_body" not in client.kwargs
    assert "thinking" not in str(client.kwargs).lower()
    assert sync_clients == [{"proxy": "http://127.0.0.1:7890", "trust_env": False}]
    assert async_clients == [{"proxy": "http://127.0.0.1:7890", "trust_env": False}]


def test_structured_client_uses_function_calling_strict(monkeypatch):
    _configure(monkeypatch)
    _fake_clients(monkeypatch)

    structured = factory.build_structured_llm(
        SmokeSchema,
        model="ignored-per-stage-model",
        temperature=0,
    )

    assert structured["schema"] is SmokeSchema
    assert structured["options"] == {
        "method": "function_calling",
        "strict": True,
    }
    assert structured["client"].kwargs["model"] == "configured-model-id"


def test_existing_provider_dispatch_is_unchanged(monkeypatch):
    monkeypatch.setattr(
        "app.llm.deepseek.build_chat_deepseek",
        lambda **kwargs: ("deepseek", kwargs),
    )
    monkeypatch.setattr(
        "app.llm.doubao.build_chat_doubao",
        lambda **kwargs: ("doubao", kwargs),
    )

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    assert factory.build_chat_llm(model="a", temperature=0.1) == (
        "deepseek", {"model": "a", "temperature": 0.1}
    )
    monkeypatch.setenv("LLM_PROVIDER", "doubao")
    assert factory.build_chat_llm(model="b", temperature=0.2) == (
        "doubao", {"model": "b", "temperature": 0.2}
    )


def test_llm_core_has_no_deployment_brand_literal():
    prohibited = "sub2api"
    for path in (PROJECT_ROOT / "app" / "llm").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert all(
            prohibited not in node.value.casefold()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )


def test_planner_schema_exact_openai_compatible_tool_request(monkeypatch, caplog):
    secret = "mock-openai-compatible-secret"
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", secret)
    monkeypatch.setenv("OPENAI_COMPATIBLE_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "configured-model-id")
    captured = {}
    real_client = httpx.Client
    real_async_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        payload = {
            "reasoning": "checked",
            "days": [
                {
                    "day": 1,
                    "spots": [
                        {
                            "candidate_ref": "legacy:abc",
                            "name": "Candidate",
                            "period": "morning",
                            "start_time": "09:00",
                            "end_time": "10:00",
                        }
                    ],
                    "theme": "day",
                }
            ],
            "notes": "done",
            "modification_concern": "",
        }
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "configured-model-id",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-test",
                                    "type": "function",
                                    "function": {
                                        "name": "PlannerTravelRoute",
                                        "arguments": json.dumps(
                                            payload, ensure_ascii=False
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    transport = httpx.MockTransport(handler)

    class MockClient(real_client):
        def __init__(self, **_kwargs):
            super().__init__(transport=transport)

    class MockAsyncClient(real_async_client):
        def __init__(self, **_kwargs):
            super().__init__(transport=transport)

    monkeypatch.setattr(httpx, "Client", MockClient)
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    with caplog.at_level(logging.INFO, logger="httpx"):
        result = factory.build_structured_llm(
            PlannerTravelRoute, temperature=0
        ).invoke("Select the supplied candidate_ref.")

    assert isinstance(result, PlannerTravelRoute)
    body = captured["body"]
    tool = body["tools"][0]["function"]
    assert tool["name"] == "PlannerTravelRoute"
    assert tool["strict"] is True
    assert body["tool_choice"]["function"]["name"] == "PlannerTravelRoute"
    assert body["parallel_tool_calls"] is False

    def assert_strict_objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                assert node.get("additionalProperties") is False
            for value in node.values():
                assert_strict_objects(value)
        elif isinstance(node, list):
            for value in node:
                assert_strict_objects(value)

    assert_strict_objects(tool["parameters"])
    assert secret not in caplog.text
