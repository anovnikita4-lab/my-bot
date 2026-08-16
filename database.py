import sqlite3
from datetime import datetime


DB_NAME = "database.db"


# =========================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =========================================================

def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# ТЕКУЩАЯ ДАТА
# =========================================================

def now():
    return datetime.now().strftime("%d.%m.%Y")


# =========================================================
# СОЗДАНИЕ / ОБНОВЛЕНИЕ БАЗЫ
# =========================================================

def init_db():

    conn = connect()
    cur = conn.cursor()

    # =====================================================
    # USERS
    # =====================================================

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

    # =====================================================
    # CLIENTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            partner_id INTEGER,
            created_at TEXT
        )
    """)

    # =====================================================
    # DEALS
    # =====================================================

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

    # =====================================================
    # TRANSACTIONS
    # =====================================================

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

    # =====================================================
    # ПРОВЕРКА СТАРОЙ БАЗЫ
    # =====================================================

    # Проверяем колонки users
    cur.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cur.fetchall()]

    if "is_partner" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN is_partner INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

    if "invited_by" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN invited_by INTEGER DEFAULT NULL
            """)
        except sqlite3.OperationalError:
            pass

    if "balance" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN balance INTEGER DEFAULT 0
            """)
        except sqlite3.OperationalError:
            pass

    # =====================================================
    # ИНДЕКСЫ
    # =====================================================

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_invited_by
        ON users(invited_by)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_deals_partner
        ON deals(partner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_partner
        ON transactions(partner_id)
    """)

    conn.commit()
    conn.close()


# =========================================================
# ПОЛЬЗОВАТЕЛИ
# =========================================================

def add_user(
    telegram_id,
    username,
    full_name,
    invited_by=None
):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Проверяем, существует ли пользователь
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            telegram_id,
            invited_by
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    existing = cur.fetchone()

    # -----------------------------------------------------
    # Новый пользователь
    # -----------------------------------------------------

    if not existing:

        # Нельзя пригласить самого себя
        if invited_by == telegram_id:
            invited_by = None

        cur.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                full_name,
                balance,
                invited_by,
                is_partner
            )
            VALUES (?, ?, ?, 0, ?, 0)
        """, (
            telegram_id,
            username,
            full_name,
            invited_by
        ))

    # -----------------------------------------------------
    # Уже существует
    # -----------------------------------------------------

    else:

        current_invited_by = existing[1]

        # Обновляем данные пользователя
        cur.execute("""
            UPDATE users
            SET
                username = ?,
                full_name = ?
            WHERE telegram_id = ?
        """, (
            username,
            full_name,
            telegram_id
        ))

        # -------------------------------------------------
        # Если раньше партнёр не был указан,
        # разрешаем привязать клиента по реферальной ссылке.
        #
        # Но если партнёр уже установлен,
        # менять его нельзя.
        # -------------------------------------------------

        if current_invited_by is None:

            if invited_by is not None and invited_by != telegram_id:

                cur.execute("""
                    SELECT telegram_id
                    FROM users
                    WHERE telegram_id = ?
                """, (invited_by,))

                partner_exists = cur.fetchone()

                if partner_exists:

                    cur.execute("""
                        UPDATE users
                        SET invited_by = ?
                        WHERE telegram_id = ?
                    """, (
                        invited_by,
                        telegram_id
                    ))

                    # Также записываем клиента
                    add_client(
                        client_id=telegram_id,
                        partner_id=invited_by,
                        connection=conn
                    )

    conn.commit()
    conn.close()


# =========================================================
# ПОЛУЧИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================================================

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


# =========================================================
# УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================================================

def delete_user(telegram_id):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Удаляем самого пользователя
    # -----------------------------------------------------

    cur.execute("""
        DELETE FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    deleted = cur.rowcount

    # -----------------------------------------------------
    # Удаляем его запись клиента
    # -----------------------------------------------------

    cur.execute("""
        DELETE FROM clients
        WHERE telegram_id = ?
    """, (telegram_id,))

    # -----------------------------------------------------
    # Удаляем клиентов, привязанных к этому партнёру
    # -----------------------------------------------------

    cur.execute("""
        DELETE FROM clients
        WHERE partner_id = ?
    """, (telegram_id,))

    conn.commit()
    conn.close()

    return deleted


# =========================================================
# БАЛАНС
# =========================================================

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
        return result[0] or 0

    return 0


# =========================================================
# НАЧИСЛИТЬ БАЛАНС
#
# Используется для /commission
# =========================================================

def add_balance(partner_id, amount):

    conn = connect()
    cur = conn.cursor()

    # Проверяем пользователя
    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (partner_id,))

    user = cur.fetchone()

    if not user:

        conn.close()
        return False

    # -----------------------------------------------------
    # Начисляем деньги
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

    # -----------------------------------------------------
    # Записываем операцию в историю
    #
    # deal_id = NULL означает ручное начисление
    # -----------------------------------------------------

    cur.execute("""
        INSERT INTO transactions (
            partner_id,
            amount,
            deal_id,
            type,
            created_at
        )
        VALUES (?, ?, NULL, ?, ?)
    """, (
        partner_id,
        amount,
        "Комиссия",
        now()
    ))

    conn.commit()
    conn.close()

    return True


# =========================================================
# УСТАНОВИТЬ БАЛАНС
# =========================================================

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

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed


# =========================================================
# ОБЩАЯ СУММА БАЛАНСОВ
# =========================================================

def get_total_balance():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(balance), 0)
        FROM users
    """)

    result = cur.fetchone()

    conn.close()

    return result[0] if result else 0


# =========================================================
# ВСЕ ПОЛЬЗОВАТЕЛИ
# =========================================================

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


# =========================================================
# ДОБАВИТЬ КЛИЕНТА
# =========================================================

def add_client(
    client_id,
    partner_id,
    connection=None
):

    own_connection = connection is None

    if own_connection:
        connection = connect()

    cur = connection.cursor()

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
        now()
    ))

    if own_connection:
        connection.commit()
        connection.close()


# =========================================================
# ПОЛУЧИТЬ КЛИЕНТОВ ПАРТНЁРА
# =========================================================

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


# =========================================================
# СДЕЛКИ
# =========================================================

def create_deal(client_id, partner_id):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Проверяем клиента
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (client_id,))

    client = cur.fetchone()

    if not client:

        conn.close()
        return None

    # -----------------------------------------------------
    # Проверяем партнёра
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            telegram_id,
            is_partner
        FROM users
        WHERE telegram_id = ?
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        conn.close()
        return None

    if partner[1] != 1:

        conn.close()
        return None

    # -----------------------------------------------------
    # Создаём сделку
    # -----------------------------------------------------

    cur.execute("""
        INSERT INTO deals (
            client_id,
            partner_id,
            status,
            commission,
            created_at
        )
        VALUES (?, ?, ?, 0, ?)
    """, (
        client_id,
        partner_id,
        "Новая",
        now()
    ))

    deal_id = cur.lastrowid

    conn.commit()
    conn.close()

    return deal_id


# =========================================================
# ПОЛУЧИТЬ СДЕЛКИ
# =========================================================

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


# =========================================================
# ИЗМЕНИТЬ СТАТУС СДЕЛКИ
# =========================================================

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

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed


# =========================================================
# ПОЛУЧИТЬ СДЕЛКУ
# =========================================================

def get_deal(deal_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            partner_id,
            status,
            commission,
            created_at,
            completed_at
        FROM deals
        WHERE id = ?
    """, (deal_id,))

    deal = cur.fetchone()

    conn.close()

    return deal


# =========================================================
# ЗАВЕРШИТЬ СДЕЛКУ
#
# ВАЖНО:
# Повторно завершить сделку невозможно.
# Это защищает от двойного начисления.
# =========================================================

def finish_deal(deal_id, amount):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Получаем сделку
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            partner_id,
            status
        FROM deals
        WHERE id = ?
    """, (deal_id,))

    deal = cur.fetchone()

    if not deal:

        conn.close()
        return None

    partner_id = deal[0]
    status = deal[1]

    # -----------------------------------------------------
    # Уже завершена
    # -----------------------------------------------------

    if status == "Завершена":

        conn.close()
        return "ALREADY_COMPLETED"

    # -----------------------------------------------------
    # Проверяем партнёра
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        conn.close()
        return None

    # -----------------------------------------------------
    # Закрываем сделку
    # -----------------------------------------------------

    cur.execute("""
        UPDATE deals
        SET
            status = 'Завершена',
            commission = ?,
            completed_at = ?
        WHERE id = ?
    """, (
        amount,
        now(),
        deal_id
    ))

    # -----------------------------------------------------
    # Начисляем партнёру
    # -----------------------------------------------------

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

    # -----------------------------------------------------
    # Записываем историю
    # -----------------------------------------------------

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
        now()
    ))

    conn.commit()
    conn.close()

    return partner_id


# =========================================================
# ИСТОРИЯ
# =========================================================

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


# =========================================================
# ПАРТНЁРЫ
# =========================================================

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


# =========================================================
# ДОБАВИТЬ ПАРТНЁРА
# =========================================================

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


# =========================================================
# УБРАТЬ ПАРТНЁРА
# =========================================================

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
