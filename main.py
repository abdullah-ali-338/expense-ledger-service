import os
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Expense Ledger Service")

DB_FILE = os.getenv("DB_FILE", "/tmp/ledger.db" if os.environ.get("VERCEL") else "ledger.db")

ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "PKR"}

USERS = {
    "token_user_1": {"id": 1, "username": "alice"},
    "token_user_2": {"id": 2, "username": "bob"}
}

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipient TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, idempotency_key)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id_id_desc ON payments(user_id, id DESC);")
        conn.commit()

init_db()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    field_name = errors[0]["loc"][-1] if errors else "body"
    msg = errors[0]["msg"] if errors else "Invalid input"
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": f"Invalid field '{field_name}': {msg}",
            "field": str(field_name),
            "suggestion": "Check field format and constraints."
        }
    )

def authenticate_user(authorization: Optional[str] = Header(None)):
    """Authenticate incoming requests using a Bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Provide 'Bearer <token>'."
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization scheme. Use 'Bearer <token>'."
        )
    
    token = parts[1]
    if token not in USERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Token not recognized."
        )
    
    return USERS[token]

class PaymentCreate(BaseModel):
    recipient: str = Field(..., min_length=2, max_length=50)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)

@app.get("/")
def root():
    """Root status ping with endpoint navigation."""
    return {"message": "Expense Ledger API is live", "docs": "/docs", "health": "/health"}

@app.post("/payments", status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: dict = Depends(authenticate_user)
):
    """Create a payment record with tenant isolation and idempotency checks."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' is required on write paths to ensure retry-safety."
        )

    clean_currency = payload.currency.strip().upper()
    if clean_currency not in ALLOWED_CURRENCIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported currency '{payload.currency}'. Must be one of USD, EUR, GBP, PKR."
        )

    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, recipient, amount, currency, idempotency_key FROM payments WHERE user_id = ? AND idempotency_key = ?",
            (current_user["id"], idempotency_key)
        )
        existing = cursor.fetchone()
        if existing:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=dict(existing)
            )

        cursor.execute(
            "INSERT INTO payments (user_id, recipient, amount, currency, idempotency_key) VALUES (?, ?, ?, ?, ?)",
            (current_user["id"], payload.recipient.strip(), payload.amount, clean_currency, idempotency_key)
        )
        conn.commit()
        new_id = cursor.lastrowid

        return {
            "id": new_id,
            "recipient": payload.recipient.strip(),
            "amount": payload.amount,
            "currency": clean_currency,
            "idempotency_key": idempotency_key
        }

@app.get("/payments")
def list_payments(current_user: dict = Depends(authenticate_user)):
    """Retrieve all payments belonging to the authenticated tenant."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, recipient, amount, currency, idempotency_key, created_at FROM payments WHERE user_id = ? ORDER BY id DESC",
            (current_user["id"],)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@app.get("/payments/{payment_id}")
def get_payment(payment_id: int, current_user: dict = Depends(authenticate_user)):
    """Retrieve a single payment scoped strictly to the authenticated tenant."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, recipient, amount, currency, idempotency_key, created_at FROM payments WHERE id = ? AND user_id = ?",
            (payment_id, current_user["id"])
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment {payment_id} not found or access denied."
            )
        return dict(row)

@app.get("/health")

def health_check():
    """Service health probe."""
    return {"status": "ok"}
