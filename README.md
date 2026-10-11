# 💸 Expense Ledger & Payment Service

![License](https://img.shields.io/badge/License-Personal_Use-blue?style=for-the-badge)
![Tech Stack](https://img.shields.io/badge/Stack-FastAPI_%7C_SQLite_%7C_Pytest-orange?style=for-the-badge)

A production-ready HTTP microservice providing strict tenant isolation, retry-safe write operations, actionable input diagnostics, and automated test coverage.

---

## ✨ Features

- **Strict Tenant Isolation:** Bearer token authentication ensures database queries filter strictly by `WHERE user_id = current_user.id`. Cross-tenant record attempts return HTTP `404 Not Found` to eliminate data leakage.
- **Retry-Safe Write Operations:** Idempotent payment processing via `Idempotency-Key` headers backed by storage-level `UNIQUE(user_id, idempotency_key)` constraints.
- **Actionable Input Diagnostics:** Detailed HTTP `400 Bad Request` messages pinpoint offending input fields and missing headers.
- **Zero-Secret Codebase:** Environment-driven configurations with zero hardcoded credentials or database keys.
- **Automated Verification:** Comprehensive test suite validating security boundary enforcement and idempotency guarantees.

---

## 🛠️ Tech Stack

- **Framework:** FastAPI
- **Database:** SQLite
- **Validation:** Pydantic
- **Testing:** Pytest
- **Server:** Uvicorn

---

## 📁 Repository Structure

```text
ExpenseLedgerService/
├── main.py             # Route handlers and authentication middleware
├── database.py         # Connection pooling, tables, and unique constraints
├── schemas.py          # Pydantic input models and validation rules
├── test_service.py     # Automated test suite for auth and idempotency
├── requirements.txt    # Python dependencies
└── README.md           # Documentation
