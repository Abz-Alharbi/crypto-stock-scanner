from backend.api import ops_routes
from backend.services.patternDetection.yoloService import get_yolo_service


class FakeRedis:
    def ping(self):
        return True


def test_health_reports_db_and_redis_ok(client, monkeypatch):
    monkeypatch.setattr(ops_routes, "get_redis_client", lambda: FakeRedis())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "redis": "ok"}


def test_ready_requires_db_and_loaded_model(client, monkeypatch):
    service = get_yolo_service()
    monkeypatch.setattr(service, "_model", object())

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ready", "db": "ok", "model": "ok"}
