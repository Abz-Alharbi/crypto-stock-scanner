from backend.extensions import db
from backend.models.notification import Notification
from backend.services import scan_templates


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_saved_scan_template_evaluation_creates_deduped_notification(client, monkeypatch):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "template_user",
            "email": "template@example.test",
            "password": "Password123",
        },
    )
    assert register_response.status_code == 201
    headers = _bearer(register_response.get_json()["token"])

    create_response = client.post(
        "/api/scan/templates",
        json={
            "name": "Oversold bounce",
            "market": "stocks",
            "timeframe": "1D",
            "filters": ["rsi_oversold"],
            "limit": 5,
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    template = create_response.get_json()["template"]
    assert template["criteria"]["filters"] == ["rsi_oversold"]

    def fake_scan_market(market, selected_filters, timeframe, max_results, user_id=None, job_id=None, progress_callback=None):
        assert market == "stocks"
        assert selected_filters == ["rsi_oversold"]
        assert timeframe == "1D"
        assert max_results == 5
        return {
            "results": [
                {
                    "provider_symbol": "AAPL",
                    "display_symbol": "AAPL",
                    "market": "stocks",
                    "overall_signal": "bullish",
                    "matched_filters": ["rsi_oversold"],
                    "match_pct": 100,
                }
            ],
            "meta": {"total_scanned": 1, "total_matched": 1},
        }

    monkeypatch.setattr(scan_templates.scans, "scan_market", fake_scan_market)

    evaluate_response = client.post(f"/api/scan/templates/{template['id']}/evaluate", headers=headers)
    assert evaluate_response.status_code == 200
    assert evaluate_response.get_json()["evaluation"]["notifications_created"] == 1

    notifications_response = client.get("/api/notifications", headers=headers)
    assert notifications_response.status_code == 200
    payload = notifications_response.get_json()
    assert payload["unread_count"] == 1
    assert payload["notifications"][0]["payload"]["provider_symbol"] == "AAPL"

    duplicate_response = client.post(f"/api/scan/templates/{template['id']}/evaluate", headers=headers)
    assert duplicate_response.status_code == 200
    assert duplicate_response.get_json()["evaluation"]["notifications_created"] == 0

    assert db.session.query(Notification).count() == 1
