import sqlite3
import random
from datetime import datetime, timedelta
from typing import List
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

app = FastAPI(title="Library Loans Service")
DB_FILE = "library.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS book_copies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                barcode TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                copy_id INTEGER NOT NULL REFERENCES book_copies(id) ON DELETE CASCADE,
                member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
                borrowed_at TIMESTAMP NOT NULL,
                due_date TIMESTAMP NOT NULL,
                returned_at TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_copy_loan
            ON loans(copy_id)
            WHERE returned_at IS NULL;

            CREATE INDEX IF NOT EXISTS idx_loans_member_active
            ON loans(member_id, returned_at, borrowed_at DESC);
        """)
        conn.commit()

init_db()

@app.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_database():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM loans")
        if cursor.fetchone()["count"] >= 10000:
            return {"message": "Database already seeded with 10,000+ loans."}

        books_data = [(f"Book Title {i}", f"Author {i}") for i in range(1, 101)]
        cursor.executemany("INSERT INTO books (title, author) VALUES (?, ?)", books_data)

        cursor.execute("SELECT id FROM books")
        book_ids = [row["id"] for row in cursor.fetchall()]

        copies_data = []
        barcode_counter = 1
        for b_id in book_ids:
            for _ in range(30):
                copies_data.append((b_id, f"BARCODE-{barcode_counter:06d}"))
                barcode_counter += 1
        cursor.executemany("INSERT INTO book_copies (book_id, barcode) VALUES (?, ?)", copies_data)

        members_data = [(f"Member {i}", f"member{i}@example.com") for i in range(1, 501)]
        cursor.executemany("INSERT INTO members (name, email) VALUES (?, ?)", members_data)

        cursor.execute("SELECT id FROM book_copies")
        copy_ids = [row["id"] for row in cursor.fetchall()]
        cursor.execute("SELECT id FROM members")
        member_ids = [row["id"] for row in cursor.fetchall()]

        base_time = datetime.now()
        loans_data = []

        for i in range(10000):
            c_id = random.choice(copy_ids)
            m_id = random.choice(member_ids)
            b_date = base_time - timedelta(days=random.randint(20, 180))
            d_date = b_date + timedelta(days=14)
            r_date = b_date + timedelta(days=random.randint(1, 13))
            loans_data.append((c_id, m_id, b_date.isoformat(), d_date.isoformat(), r_date.isoformat()))

        active_copies = random.sample(copy_ids, 200)
        for c_id in active_copies:
            m_id = random.choice(member_ids)
            b_date = base_time - timedelta(days=random.randint(1, 7))
            d_date = b_date + timedelta(days=14)
            loans_data.append((c_id, m_id, b_date.isoformat(), d_date.isoformat(), None))

        cursor.executemany("""
            INSERT INTO loans (copy_id, member_id, borrowed_at, due_date, returned_at)
            VALUES (?, ?, ?, ?, ?)
        """, loans_data)
        conn.commit()

        return {"message": f"Successfully seeded {len(loans_data)} loan records."}

class ActiveLoanResponse(BaseModel):
    loan_id: int
    book_title: str
    copy_barcode: str
    borrowed_at: str
    due_date: str

@app.get("/members/{member_id}/active-loans", response_model=List[ActiveLoanResponse])
def get_member_active_loans(member_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM members WHERE id = ?", (member_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

        query = """
            SELECT 
                l.id AS loan_id,
                b.title AS book_title,
                bc.barcode AS copy_barcode,
                l.borrowed_at,
                l.due_date
            FROM loans l
            JOIN book_copies bc ON l.copy_id = bc.id
            JOIN books b ON bc.book_id = b.id
            WHERE l.member_id = ? AND l.returned_at IS NULL
            ORDER BY l.borrowed_at DESC
        """
        cursor.execute(query, (member_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]