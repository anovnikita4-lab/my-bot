import sqlite3

DB_NAME = "database.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER UNIQUE,
            partner_id INTEGER,
            status TEXT DEFAULT 'Новый',
            commission INTEGER DEFAULT 0
        )
        """
    )

    conn.commit()
    conn.close()


def add_user(telegram_id, username, full_name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users
        (telegram_id, username, full_name)
        VALUES (?, ?, ?)
        """,
        (telegram_id, username, full_name),
    )

    conn.commit()
    conn.close()


def get_balance(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE telegram_id = ?",
        (telegram_id,),
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else 0


def add_balance(telegram_id, amount):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
        (amount, telegram_id),
    )

    conn.commit()
    conn.close()


def set_balance(telegram_id, amount):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET balance = ? WHERE telegram_id = ?",
        (amount, telegram_id),
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT telegram_id, full_name, balance FROM users ORDER BY full_name"
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def add_client(client_id, partner_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO clients
        (client_id, partner_id)
        VALUES (?, ?)
        """,
        (client_id, partner_id),
    )

    conn.commit()
    conn.close()


def get_partner_clients(partner_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT client_id, status FROM clients WHERE partner_id = ?",
        (partner_id,),
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def get_all_clients():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT client_id, partner_id, status FROM clients ORDER BY id DESC"
    )

    rows = cur.fetchall()
    conn.close()

    return rows


def set_client_status(client_id, status):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE clients SET status = ? WHERE client_id = ?",
        (status, client_id),
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("База данных готова!")