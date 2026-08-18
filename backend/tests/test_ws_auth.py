"""WebSocket authentication and routing."""

from tests.conftest import join_participant


def test_authenticated_ws_connects(client):
    _, auth = join_participant(client, "WsUser")
    token = auth["Authorization"].split(" ", 1)[1]
    with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "CONNECTED"
        assert msg["payload"]["authenticated"] is True


def test_anonymous_ws_connects_public(client):
    with client.websocket_connect("/api/v1/ws") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "CONNECTED"
        assert msg["payload"]["authenticated"] is False


def test_order_requires_auth(client):
    client.post("/api/v1/admin/simulation/reset")
    stocks = client.get("/api/v1/stocks").json()
    res = client.post(
        "/api/v1/orders",
        json={
            "trader_id": 1,
            "stock_id": stocks[0]["id"],
            "side": "buy",
            "order_type": "market",
            "quantity": 1,
        },
    )
    assert res.status_code == 401
