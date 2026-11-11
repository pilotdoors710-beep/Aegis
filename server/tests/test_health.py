from fastapi.testclient import TestClient

from api.main import app


def test_healthz_and_browser() -> None:
    with TestClient(app) as client:  # runs lifespan -> launches Chromium
        assert client.get("/healthz").json() == {"status": "ok"}
        body = client.get("/healthz/browser").json()
        assert body["title"] == "Aegis OK"
        assert len(body["screenshot_b64"]) > 1000
