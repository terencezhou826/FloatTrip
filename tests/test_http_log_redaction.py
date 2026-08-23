from __future__ import annotations

import logging

import httpx

from app.core.http import install_http_log_redaction


def test_httpx_info_log_redacts_amap_key_but_keeps_request_diagnostics(caplog):
    secret = "amap-secret-value"
    install_http_log_redaction()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "1"})

    with caplog.at_level(logging.INFO, logger="httpx"):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            client.get(
                f"https://restapi.amap.com/v3/place/text?keywords=test&key={secret}"
            )

    rendered = caplog.text
    assert secret not in rendered
    assert "restapi.amap.com/v3/place/text" in rendered
    assert "200 OK" in rendered
    assert "key=<redacted>" in rendered


def test_openai_authorization_log_is_redacted(caplog):
    secret = "openai-compatible-secret"
    install_http_log_redaction()

    with caplog.at_level(logging.ERROR, logger="openai"):
        logging.getLogger("openai").error(
            "request failed Authorization: Bearer %s", secret
        )

    assert secret not in caplog.text
    assert "Authorization: Bearer <redacted>" in caplog.text
