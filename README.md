# Expense Ledger & Payment Service

A production-ready HTTP microservice providing strict tenant isolation, retry-safe write operations, actionable input diagnostics, and automated test coverage.

- **Live URL:** https://expense-ledger-service.vercel.app
- **Interactive API Docs:** https://expense-ledger-service.vercel.app/docs

---

## Acceptance Criteria Verification

### 1. Authentication & Tenant Isolation
- Protected endpoints require an `Authorization: Bearer <token>` header. Requests lacking valid credentials immediately reject with HTTP `401 Unauthorized`.
- Every database query strictly filters by `WHERE user_id = current_user.id`. One user cannot read, query, or alter records belonging to another tenant.
- Cross-tenant access attempts return HTTP `404 Not Found` to prevent data leakage.
- Automated verification: `test_service.py:test_user_cannot_access_another_users_rows`.

### 2. Retry-Safe Write Path (Idempotency)
- Critical write endpoint: `POST /payments`.
- Repeats are recognized using the client-provided `Idempotency-Key` HTTP header.
- When an identical `Idempotency-Key` is received for the same authenticated user, the service intercepts the request, avoids creating a duplicate database row, and returns the original stored record with HTTP `200 OK`.
- Database integrity is enforced at storage level via a `UNIQUE(user_id, idempotency_key)` constraint.
- Automated verification: `test_service.py:test_idempotent_retry_returns_original_record`.

### 3. Actionable Errors
- Malformed payloads or invalid inputs return descriptive HTTP `400 Bad Request` responses indicating the exact offending field along with actionable instructions to fix the request.
- Missing headers (`Idempotency-Key`) and invalid currencies return specific diagnostic messages rather than generic error codes.

### 4. Zero Committed Secrets
- Configuration parameters and database paths are loaded via runtime environment variables. No credentials or secrets exist within the repository.

---

## API Reference

| Method | Endpoint | Auth | Headers | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | No | None | Root status ping |
| `GET` | `/health` | No | None | System health check |
| `POST` | `/payments` | Yes | `Idempotency-Key: <key>` | Dispatches a payment record safely |
| `GET` | `/payments` | Yes | None | Retrieves all payments for the active user |
| `GET` | `/payments/{id}` | Yes | None | Fetches a specific payment by ID |

---

## Test Credentials

Use these tokens for testing authentication and tenant isolation:

- **User 1 (Alice):** `Authorization: Bearer token_user_1`
- **User 2 (Bob):** `Authorization: Bearer token_user_2`

Supported currencies: `USD`, `EUR`, `GBP`, `PKR`.

---

## Local Setup & Automated Testing

```bash
# Clone the repository
git clone: https://github.com/abdullah-ali-338/expense-ledger-service.git
cd expense-ledger-service

# Install dependencies
pip install -r requirements.txt

# Run automated tests
python -m pytest test_service.py

# Run local development server
python -m uvicorn main:app --reload
