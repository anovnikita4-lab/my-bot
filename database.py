import sqlite3
from datetime import datetime


DB_NAME = "database.db"


# =========================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =========================

def connect():
    return sqlite3.connect(DB_NAME)


# =========================
# СОЗДАНИЕ БАЗЫ
# =========================

def init_db():

    conn = connect()
    cur = conn.cursor()

    # =========================
    # ПОЛЬЗОВАТЕЛИ
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance INTEGER DEFAULT 0,
            invited_by INTEGER DEFAULT NULL,
            is_partner INTEGER DEFAULT 0
        )
    """)

    # =========================
    # ЕСЛИ СТАРАЯ БАЗА
    # ДОБАВЛЯЕМ is_partner
    # =========================

    try:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN is_partner INTEGER DEFAULT 0
        """)
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass

    # =========================
    # КЛИЕНТЫ
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            partner_id INTEGER,
            created_at TEXT
        )
    """)

    # =========================
    # СДЕЛКИ
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            partner_id INTEGER,
            status TEXT DEFAULT 'Новая',
            commission INTEGER DEFAULT 0,
            created_at TEXT,
            completed_at TEXT
        )
    """)

    # =========================
    # ИСТОРИЯ
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER,
            amount INTEGER,
            deal_id INTEGER,
            type TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================
# ПОЛЬЗОВАТЕЛИ
# =========================

def add_user(
    telegram_id,
    username,
    full_name,
    invited_by=None
):

    conn = connect()
    cur = conn.cursor()

    # Создаём пользователя.
    # Если он уже существует:
    # обновляем username и имя.
    #
    # invited_by записываем только если
    # раньше он был пустым.
    #
    # Это важно для партнёрских ссылок.

    cur.execute("""
        INSERT INTO users (
            telegram_id,
            username,
            full_name,
            invited_by
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(telegram_id)
        DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            invited_by = CASE
                WHEN users.invited_by IS NULL
                     AND excluded.invited_by IS NOT NULL
                     AND excluded.invited_by != users.telegram_id
                THEN excluded.invited_by
                ELSE users.invited_by
            END
    """, (
        telegram_id,
        username,
        full_name,
        invited_by
    ))

    conn.commit()
    conn.close()


# =========================
# ПОЛУЧИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================

def get_user(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            telegram_id,
            username,
            full_name,
            balance,
            invited_by,
            is_partner
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    result = cur.fetchone()

    conn.close()

    return result


# =========================
# УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================

def delete_user(telegram_id):

    conn = connect()
    cur = conn.cursor()

    # Проверяем, существует ли пользователь
    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    user = cur.fetchone()

    if not user:
        conn.close()
        return 0

    # Удаляем пользователя
    cur.execute("""
        DELETE FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    # Удаляем клиентов этого партнёра
    cur.execute("""
        DELETE FROM clients
        WHERE partner_id = ?
    """, (telegram_id,))

    conn.commit()
    conn.close()

    return 1


# =========================
# БАЛАНС
# =========================

def get_balance(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT balance
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    result = cur.fetchone()

    conn.close()

    if result:
        return result[0]

    return 0


# =========================
# НАЧИСЛИТЬ БАЛАНС
# =========================

def add_balance(partner_id, amount):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

    conn.commit()
    conn.close()


# =========================
# УСТАНОВИТЬ БАЛАНС
# =========================

def set_balance(partner_id, amount):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

    conn.commit()
    conn.close()


# =========================
# ВСЕ ПОЛЬЗОВАТЕЛИ
# =========================

def get_all_users():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            telegram_id,
            full_name,
            balance
        FROM users
        ORDER BY full_name
    """)

    data = cur.fetchall()

    conn.close()

    return data


# =========================
# КЛИЕНТЫ
# =========================

def add_client(client_id, partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO clients (
            telegram_id,
            partner_id,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        client_id,
        partner_id,
        datetime.now().strftime("%d.%m.%Y")
    ))

    conn.commit()
    conn.close()


# =========================
# ПОЛУЧИТЬ КЛИЕНТОВ ПАРТНЕРА
# =========================

def get_clients(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            telegram_id,
            username,
            full_name
        FROM users
        WHERE invited_by = ?
        ORDER BY telegram_id DESC
    """, (partner_id,))

    users = cur.fetchall()

    conn.close()

    return users


# =========================
# СДЕЛКИ
# =========================

def create_deal(client_id, partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO deals (
            client_id,
            partner_id,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        client_id,
        partner_id,
        "Новая",
        datetime.now().strftime("%d.%m.%Y")
    ))

    deal_id = cur.lastrowid

    conn.commit()
    conn.close()

    return deal_id


# =========================
# ПОЛУЧИТЬ СДЕЛКИ
# =========================

def get_deals():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            partner_id,
            status,
            commission
        FROM deals
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    conn.close()

    return data


# =========================
# ИЗМЕНИТЬ СТАТУС СДЕЛКИ
# =========================

def set_deal_status(deal_id, status):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE deals
        SET status = ?
        WHERE id = ?
    """, (
        status,
        deal_id
    ))

    conn.commit()
    conn.close()


# =========================
# ЗАВЕРШИТЬ СДЕЛКУ
# =========================

def finish_deal(deal_id, amount):

    conn = connect()
    cur = conn.cursor()

    # Находим партнёра
    cur.execute("""
        SELECT partner_id
        FROM deals
        WHERE id = ?
    """, (deal_id,))

    deal = cur.fetchone()

    if not deal:
        conn.close()
        return None

    partner_id = deal[0]

    # Проверяем, не завершена ли сделка раньше
    cur.execute("""
        SELECT status
        FROM deals
        WHERE id = ?
    """, (deal_id,))

    current_deal = cur.fetchone()

    if not current_deal:
        conn.close()
        return None

    if current_deal[0] == "Завершена":
        conn.close()
        return None

    # Закрываем сделку
    cur.execute("""
        UPDATE deals
        SET
            status = 'Завершена',
            commission = ?,
            completed_at = ?
        WHERE id = ?
    """, (
        amount,
        datetime.now().strftime("%d.%m.%Y"),
        deal_id
    ))

    # Начисляем партнёру
    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

    # Записываем историю
    cur.execute("""
        INSERT INTO transactions (
            partner_id,
            amount,
            deal_id,
            type,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        partner_id,
        amount,
        deal_id,
        "Комиссия",
        datetime.now().strftime("%d.%m.%Y")
    ))

    conn.commit()
    conn.close()

    return partner_id


# =========================
# ИСТОРИЯ
# =========================

def get_history(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            amount,
            deal_id,
            created_at
        FROM transactions
        WHERE partner_id = ?
        ORDER BY id DESC
    """, (partner_id,))

    data = cur.fetchall()

    conn.close()

    return data


# =========================
# ПАРТНЕРЫ
# =========================

def get_partners():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            telegram_id,
            username,
            full_name,
            balance
        FROM users
        WHERE is_partner = 1
        ORDER BY telegram_id DESC
    """)

    users = cur.fetchall()

    conn.close()

    return users


# =========================
# ДОБАВИТЬ ПАРТНЕРА
# =========================

def add_partner(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET is_partner = 1
        WHERE telegram_id = ?
    """, (telegram_id,))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed


# =========================
# УБРАТЬ ПАРТНЕРА
# =========================

def remove_partner(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET is_partner = 0
        WHERE telegram_id = ?
    """, (telegram_id,))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed
