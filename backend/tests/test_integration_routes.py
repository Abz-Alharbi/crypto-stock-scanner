from backend.extensions import db
from backend.models.scan import ScanHistory
from backend.models.user import User


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_and_watchlist_flow(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "flow_user",
            "email": "flow@example.test",
            "password": "Password123",
        },
    )
    assert register_response.status_code == 201
    register_payload = register_response.get_json()
    assert register_payload["user"]["email"] == "flow@example.test"
    assert register_payload["token"]

    login_response = client.post(
        "/api/auth/login",
        json={"email": "flow@example.test", "password": "Password123"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.get_json()
    headers = _bearer(login_payload["token"])

    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.get_json()["user"]["username"] == "flow_user"

    add_response = client.post(
        "/api/watchlist",
        json={"symbol": "X:BTCUSD", "market": "crypto", "notes": "Integration test"},
        headers=headers,
    )
    assert add_response.status_code == 201

    list_response = client.get("/api/watchlist", headers=headers)
    assert list_response.status_code == 200
    watchlist = list_response.get_json()["watchlist"]

    assert len(watchlist) == 1
    assert watchlist[0]["provider_symbol"] == "X:BTCUSD"
    assert watchlist[0]["display_symbol"] == "X:BTCUSD"
    assert watchlist[0]["market"] == "crypto"
    assert watchlist[0]["notes"] == "Integration test"

    update_response = client.patch(
        f"/api/watchlist/{watchlist[0]['id']}",
        json={"notes": "Updated note"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated_item = update_response.get_json()["watchlist_item"]
    assert updated_item["provider_symbol"] == "X:BTCUSD"
    assert updated_item["display_symbol"] == "X:BTCUSD"
    assert updated_item["notes"] == "Updated note"


def test_admin_routes_for_admin_user(app, client, admin_headers):
    with app.app_context():
        user = User(username="managed_user", email="managed@example.test")
        user.set_password("Password123")
        db.session.add(user)
        db.session.flush()
        managed_user_id = user.id
        db.session.add(
            ScanHistory(
                user_id=user.id,
                job_id="integration-job",
                market="stocks",
                timeframe="1D",
                total_scanned=10,
                total_matched=2,
                filters_used='["rsi_oversold"]',
                duration_seconds=0.25,
            )
        )
        db.session.commit()

    users_response = client.get("/api/admin/users", headers=admin_headers)
    assert users_response.status_code == 200
    assert any(user["email"] == "managed@example.test" for user in users_response.get_json()["users"])

    update_response = client.put(
        f"/api/admin/users/{managed_user_id}",
        json={"plan": "premium", "role": "user", "is_active": True},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["user"]["plan"] == "premium"

    audit_response = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert audit_response.status_code == 200
    audit_logs = audit_response.get_json()["audit_logs"]
    assert audit_logs[0]["action"] == "update_user"
    assert audit_logs[0]["target_id"] == managed_user_id

    scans_response = client.get("/api/admin/scans", headers=admin_headers)
    assert scans_response.status_code == 200
    assert scans_response.get_json()["scans"][0]["job_id"] == "integration-job"

    stats_response = client.get("/api/admin/stats", headers=admin_headers)
    assert stats_response.status_code == 200
    stats = stats_response.get_json()
    assert stats["total_users"] == 2
    assert stats["total_scans"] == 1


def test_admin_routes_reject_non_admin(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "plain_user",
            "email": "plain@example.test",
            "password": "Password123",
        },
    )
    headers = _bearer(register_response.get_json()["token"])

    response = client.get("/api/admin/users", headers=headers)

    assert response.status_code == 403
    assert response.get_json()["code"] == "forbidden"


def test_search_route_uses_mocked_polygon_client(client):
    response = client.get("/api/search?q=AAPL&market=stocks")

    assert response.status_code == 200
    results = response.get_json()["results"]
    assert results[0]["provider_symbol"] == "AAPL"
    assert results[0]["name"] == "Apple Inc."
