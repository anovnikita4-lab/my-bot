
import sqlite3
from datetime import datetime

DB_NAME = "database.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def _columns(cur, table):
    return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0,
            is_partner INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER UNIQUE,
            partner_id INTEGER,
            status TEXT DEFAULT 'Новый',
            commission INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS car_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            partner_id INTEGER,
            country TEXT NOT NULL,
            criteria TEXT NOT NULL,
            budget TEXT,
            year TEXT,
            mileage TEXT,
            payment TEXT,
            timing TEXT,
            engine TEXT,
            additional TEXT,
            contact TEXT,
            deal_id INTEGER,
            status TEXT DEFAULT 'Новая',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            partner_id INTEGER,
            status TEXT DEFAULT 'Новая',
            commission INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS commission_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            deal_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migration for the old users table.
    cols = _columns(cur, "users")
    if "is_partner" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_partner INTEGER DEFAULT 0")
    if "created_at" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        cur.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    cols = _columns(cur, "car_requests")
    if "engine" not in cols:
        cur.execute("ALTER TABLE car_requests ADD COLUMN engine TEXT")
    if "additional" not in cols:
        cur.execute("ALTER TABLE car_requests ADD COLUMN additional TEXT")
    if "deal_id" not in cols:
        cur.execute("ALTER TABLE car_requests ADD COLUMN deal_id INTEGER")

    # Preserve partners from the old clients table.
    cur.execute("""
        UPDATE users
        SET is_partner=1
        WHERE telegram_id IN (
            SELECT DISTINCT partner_id
            FROM clients
            WHERE partner_id IS NOT NULL
        )
    """)

    cols = _columns(cur, "clients")
    if "created_at" not in cols:
        cur.execute("ALTER TABLE clients ADD COLUMN created_at TEXT")
        cur.execute("UPDATE clients SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    conn.commit()
    conn.close()

def add_user(telegram_id, username, full_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, username, full_name)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name
    """, (telegram_id, username, full_name))
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users():
    conn = get_connection()
    rows = conn.execute("SELECT telegram_id, username, full_name, balance, is_partner, created_at FROM users ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_partner(telegram_id, value=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_partner=? WHERE telegram_id=?", (1 if value else 0, telegram_id))
    conn.commit()
    conn.close()

def is_partner(telegram_id):
    user = get_user(telegram_id)
    return bool(user and user["is_partner"])

def remove_partner(telegram_id):
    """Remove partner status but keep existing client/deal attribution."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_partner=0 WHERE telegram_id=?", (telegram_id,))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed

def get_partners():
    conn = get_connection()
    rows = conn.execute("""
        SELECT u.telegram_id, u.username, u.full_name, u.balance,
               COUNT(c.id) AS clients_count
        FROM users u
        LEFT JOIN clients c ON c.partner_id = u.telegram_id
        WHERE u.is_partner = 1
        GROUP BY u.telegram_id
        ORDER BY u.full_name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def attach_client_to_partner(client_id, partner_id):
    if client_id == partner_id:
        return "self"
    conn = get_connection()
    cur = conn.cursor()
    partner = cur.execute("SELECT telegram_id FROM users WHERE telegram_id=? AND is_partner=1", (partner_id,)).fetchone()
    if not partner:
        conn.close()
        return "invalid_partner"
    existing = cur.execute("SELECT partner_id FROM clients WHERE client_id=?", (client_id,)).fetchone()
    if existing:
        conn.close()
        return "already" if existing["partner_id"] != partner_id else "same"
    cur.execute(
        "INSERT INTO clients (client_id, partner_id, status) VALUES (?, ?, 'Новый')",
        (client_id, partner_id),
    )
    conn.commit()
    conn.close()
    return "attached"

def get_client(client_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clients WHERE client_id=?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_partner_clients(partner_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM clients WHERE partner_id=? ORDER BY id DESC
    """, (partner_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_clients():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_client_status(client_id, status):
    conn = get_connection()
    conn.execute("UPDATE clients SET status=? WHERE client_id=?", (status, client_id))
    conn.commit()
    conn.close()

def create_car_request(client_id, partner_id, data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO car_requests
        (client_id, partner_id, country, criteria, budget, year, mileage, payment, timing, engine, additional, contact)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id, partner_id, data.get("country"), data.get("criteria"),
        data.get("budget"), data.get("year"), data.get("mileage"),
        data.get("payment"), data.get("timing"), data.get("engine"),
        data.get("additional"), data.get("contact")
    ))
    request_id = cur.lastrowid
    cur.execute("UPDATE clients SET status='Заявка создана' WHERE client_id=?", (client_id,))
    conn.commit()
    conn.close()
    return request_id

def link_request_deal(request_id, deal_id):
    conn = get_connection()
    conn.execute("UPDATE car_requests SET deal_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (deal_id, request_id))
    conn.commit()
    conn.close()

def get_request(request_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM car_requests WHERE id=?", (request_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_client_requests(client_id):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM car_requests WHERE client_id=? ORDER BY id DESC", (client_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_requests():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM car_requests ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_request_status(request_id, status):
    conn = get_connection()
    conn.execute("UPDATE car_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()

def get_balance(telegram_id):
    user = get_user(telegram_id)
    return user["balance"] if user else 0

def add_balance(telegram_id, amount):
    conn = get_connection()
    conn.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?", (amount, telegram_id))
    conn.commit()
    conn.close()

def set_balance(telegram_id, amount):
    conn = get_connection()
    conn.execute("UPDATE users SET balance=? WHERE telegram_id=?", (amount, telegram_id))
    conn.commit()
    conn.close()

def add_commission_history(partner_id, amount, deal_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO commission_history (partner_id, amount, deal_id) VALUES (?, ?, ?)",
        (partner_id, amount, deal_id),
    )
    conn.commit()
    conn.close()

def get_history(partner_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM commission_history WHERE partner_id=? ORDER BY id DESC",
        (partner_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_deal(client_id, partner_id, commission=0):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deals (client_id, partner_id, commission) VALUES (?, ?, ?)",
        (client_id, partner_id, commission),
    )
    deal_id = cur.lastrowid
    cur.execute("UPDATE clients SET status='Сделка создана' WHERE client_id=?", (client_id,))
    conn.commit()
    conn.close()
    return deal_id

def get_deals():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM deals ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_partner_deals(partner_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM deals WHERE partner_id=? ORDER BY id DESC",
        (partner_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_deal(deal_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def finish_deal(deal_id, amount):
    conn = get_connection()
    cur = conn.cursor()
    deal = cur.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
    if not deal or deal["status"] == "Завершена":
        conn.close()
        return None
    cur.execute(
        "UPDATE deals SET status='Завершена', commission=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (amount, deal_id),
    )
    if deal["partner_id"]:
        cur.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?", (amount, deal["partner_id"]))
    cur.execute("UPDATE clients SET status='Сделка завершена', commission=commission+? WHERE client_id=?", (amount, deal["client_id"]))
    conn.commit()
    partner_id = deal["partner_id"]
    conn.close()
    return partner_id

def delete_user(telegram_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE client_id=? OR partner_id=?", (telegram_id, telegram_id))
    cur.execute("DELETE FROM users WHERE telegram_id=?", (telegram_id,))
    changed = cur.rowcount
    conn.commit()
    conn.close()
    return changed

def count_stats():
    conn = get_connection()
    s = {}
    s["users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    s["partners"] = conn.execute("SELECT COUNT(*) FROM users WHERE is_partner=1").fetchone()[0]
    s["clients"] = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    s["requests"] = conn.execute("SELECT COUNT(*) FROM car_requests").fetchone()[0]
    s["deals"] = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    s["completed"] = conn.execute("SELECT COUNT(*) FROM deals WHERE status='Завершена'").fetchone()[0]
    s["balances"] = conn.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
    s["commissions"] = conn.execute("SELECT COALESCE(SUM(amount),0) FROM commission_history").fetchone()[0]
    conn.close()
    return s

if __name__ == "__main__":
    init_db()
    print("База данных готова!")
