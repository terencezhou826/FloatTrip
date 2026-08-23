from __future__ import annotations

import run


def test_resolve_port_defaults_to_8765(monkeypatch) -> None:
    monkeypatch.delenv("PORT", raising=False)

    assert run._resolve_port() == 8765


def test_main_uses_port_environment_variable(monkeypatch, capsys) -> None:
    received: dict[str, object] = {}

    def fake_run(app: str, **kwargs: object) -> None:
        received["app"] = app
        received.update(kwargs)

    monkeypatch.setenv("PORT", "8766")
    monkeypatch.setattr(run.uvicorn, "run", fake_run)

    run.main()

    assert "http://localhost:8766" in capsys.readouterr().out
    assert received == {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8766,
        "reload": False,
    }
