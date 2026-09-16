import os
import pytest
from fastapi.testclient import TestClient

os.environ["DB_FILE"] = "test_ledger.db"

from main import app, init_db, get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_database():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM payments;")
        conn.commit()
    yield

def test_unauthenticated_request_returns_401():
    response = client.get("/payments")
    assert response.status_code == 401

def test_missing_idempotency_key_returns_400():
    headers = {"Authorization": "Bearer token_user_1"}
    payload = {"recipient": "carol", "amount": 100.0, "currency": "USD"}
    response = client.post("/payments", json=payload, headers=headers)
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]

def test_idempotent_retry_returns_original_record():
    headers = {
        "Authorization": "Bearer token_user_1",
        "Idempotency-Key": "req_uuid_101"
    }
    payload = {"recipient": "carol", "amount": 50.0, "currency": "USD"}
    
    res1 = client.post("/payments", json=payload, headers=headers)
    assert res1.status_code == 201
    
    res2 = client.post("/payments", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res1.json()["id"] == res2.json()["id"]

def test_user_cannot_access_another_users_rows():
    headers_u1 = {"Authorization": "Bearer token_user_1", "Idempotency-Key": "u1_tx_1"}
    payload = {"recipient": "dave", "amount": 200.0, "currency": "USD"}
    res = client.post("/payments", json=payload, headers=headers_u1)
    payment_id = res.json()["id"]

    headers_u2 = {"Authorization": "Bearer token_user_2"}
    res_forbidden = client.get(f"/payments/{payment_id}", headers=headers_u2)
    assert res_forbidden.status_code == 404

    list_res = client.get("/payments", headers=headers_u2)
    assert len(list_res.json()) == 0