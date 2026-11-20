import os

# El cliente de Groq se crea al importar app.routes.ask_routes y falla sin API key.
# Se define una falsa antes de cualquier import de la app; los tests nunca llaman a Groq.
os.environ.setdefault("API_KEY", "test-key")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import ask_routes


@pytest.fixture
def client():
    return TestClient(app)


class FakeComplete:
    """Reemplaza ask_routes.complete: devuelve respuestas en orden y registra las llamadas."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls: list[tuple[str, list[dict]]] = []

    async def __call__(self, system_prompt: str, history: list[dict]) -> str:
        self.calls.append((system_prompt, history))
        return self.replies.pop(0)


@pytest.fixture
def fake_complete(monkeypatch):
    def install(*replies: str) -> FakeComplete:
        fake = FakeComplete(*replies)
        monkeypatch.setattr(ask_routes, "complete", fake)
        return fake

    return install
