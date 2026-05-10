"""Testes da interface web (FastAPI)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from videogen.web.jobs import JobManager
from videogen.web.server import create_app


def _client() -> TestClient:
    return TestClient(create_app(manager=JobManager()))


def test_index_renders_form():
    res = _client().get("/")
    assert res.status_code == 200
    body = res.text
    assert "videogen" in body
    assert 'name="tema"' in body
    assert 'name="voice"' in body
    assert 'name="duracao"' in body


def test_health_endpoint():
    res = _client().get("/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert "gemini" in payload
    assert "pexels" in payload
    assert "pixabay" in payload


def test_create_job_requires_tema_or_script():
    res = _client().post("/api/jobs", data={})
    assert res.status_code == 400
    assert "tema" in res.json()["detail"].lower()


def test_jobs_endpoint_returns_empty_list_initially():
    res = _client().get("/api/jobs")
    assert res.status_code == 200
    assert res.json() == {"jobs": []}


def test_get_unknown_job_returns_404():
    res = _client().get("/api/jobs/does-not-exist")
    assert res.status_code == 404


def test_voices_api_falls_back_to_defaults():
    # Sem rede, list_voices falha; o endpoint ainda retorna defaults.
    res = _client().get("/api/voices?lang=pt")
    assert res.status_code == 200
    payload = res.json()
    assert "voices" in payload
    assert len(payload["voices"]) >= 1
