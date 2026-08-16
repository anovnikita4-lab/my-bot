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


def now_full():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


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
    # ЗАЯВКИ НА АВТОМОБИЛИ
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS car_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            client_id INTEGER UNIQUE,
            deal_id INTEGER,

            country TEXT,
            car_type TEXT,

            brand TEXT,
            model TEXT,

            budget TEXT,
            year_from TEXT,
            mileage TEXT,

            engine TEXT,
            fuel TEXT,
            drive TEXT,
            body TEXT,

            additional TEXT,
            free_text TEXT,

            status TEXT DEFAULT 'Новая',

            created_at TEXT,
            updated_at TEXT
        )
    """)

    # =====================================================
    # ПРОВЕРКА СТАРОЙ БАЗЫ USERS
    # =====================================================

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

    if "username" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN username TEXT
            """)
        except sqlite3.OperationalError:
            pass

    if "full_name" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN full_name TEXT
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
        CREATE INDEX IF NOT EXISTS idx_users_partner
        ON users(is_partner)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_clients_partner
        ON clients(partner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_deals_partner
        ON deals(partner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_deals_client
        ON deals(client_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_deals_status
        ON deals(status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_partner
        ON transactions(partner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_car_requests_client
        ON car_requests(client_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_car_requests_deal
        ON car_requests(deal_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_car_requests_status
        ON car_requests(status)
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
    # Нельзя пригласить самого себя
    # -----------------------------------------------------

    if invited_by == telegram_id:
        invited_by = None

    # -----------------------------------------------------
    # Проверяем пользователя
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            telegram_id,
            invited_by,
            is_partner
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    existing = cur.fetchone()

    # =====================================================
    # НОВЫЙ ПОЛЬЗОВАТЕЛЬ
    # =====================================================

    if not existing:

        valid_partner = None

        # Проверяем реферального партнёра
        if invited_by is not None:

            cur.execute("""
                SELECT telegram_id
                FROM users
                WHERE telegram_id = ?
                  AND is_partner = 1
            """, (invited_by,))

            partner = cur.fetchone()

            if partner:
                valid_partner = invited_by

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
            valid_partner
        ))

        # -------------------------------------------------
        # Если пришёл по реферальной ссылке,
        # автоматически создаём клиента
        # -------------------------------------------------

        if valid_partner is not None:

            add_client(
                client_id=telegram_id,
                partner_id=valid_partner,
                connection=conn
            )

    # =====================================================
    # ПОЛЬЗОВАТЕЛЬ УЖЕ ЕСТЬ
    # =====================================================

    else:

        current_invited_by = existing[1]

        # -------------------------------------------------
        # Обновляем Telegram-данные
        # -------------------------------------------------

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
        # Если партнёр ещё НЕ закреплён,
        # пытаемся закрепить первого партнёра
        # -------------------------------------------------

        if current_invited_by is None:

            if invited_by is not None and invited_by != telegram_id:

                cur.execute("""
                    SELECT telegram_id
                    FROM users
                    WHERE telegram_id = ?
                      AND is_partner = 1
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
# ПОЛУЧИТЬ ПАРТНЁРА КЛИЕНТА
# =========================================================

def get_client_partner(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT invited_by
        FROM users
        WHERE telegram_id = ?
    """, (client_id,))

    result = cur.fetchone()

    conn.close()

    if result:
        return result[0]

    return None


# =========================================================
# ПРОВЕРИТЬ — ЯВЛЯЕТСЯ ЛИ ПОЛЬЗОВАТЕЛЬ ПАРТНЁРОМ
# =========================================================

def is_partner(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT is_partner
        FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    result = cur.fetchone()

    conn.close()

    if result:
        return result[0] == 1

    return False


# =========================================================
# УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================================================

def delete_user(telegram_id):

    conn = connect()
    cur = conn.cursor()

    # Удаляем заявки
    cur.execute("""
        DELETE FROM car_requests
        WHERE client_id = ?
    """, (telegram_id,))

    # Удаляем сделки клиента
    cur.execute("""
        DELETE FROM deals
        WHERE client_id = ?
    """, (telegram_id,))

    # Удаляем клиента
    cur.execute("""
        DELETE FROM clients
        WHERE telegram_id = ?
    """, (telegram_id,))

    # Удаляем самого пользователя
    cur.execute("""
        DELETE FROM users
        WHERE telegram_id = ?
    """, (telegram_id,))

    deleted = cur.rowcount

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
    # Начисляем
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
    # История
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
        now_full()
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

    # -----------------------------------------------------
    # Проверяем, что партнёр действительно партнёр
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
          AND is_partner = 1
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        if own_connection:
            connection.close()

        return False

    # -----------------------------------------------------
    # INSERT OR IGNORE защищает от дублей
    # -----------------------------------------------------

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
        now_full()
    ))

    if own_connection:
        connection.commit()
        connection.close()

    return True


# =========================================================
# ПОЛУЧИТЬ КЛИЕНТА
# =========================================================

def get_client(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            telegram_id,
            partner_id,
            created_at
        FROM clients
        WHERE telegram_id = ?
    """, (client_id,))

    result = cur.fetchone()

    conn.close()

    return result


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
# КОЛИЧЕСТВО КЛИЕНТОВ
# =========================================================

def get_clients_count(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE invited_by = ?
    """, (partner_id,))

    result = cur.fetchone()

    conn.close()

    return result[0] if result else 0


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
        VALUES (?, ?, 'Новая', 0, ?)
    """, (
        client_id,
        partner_id,
        now_full()
    ))

    deal_id = cur.lastrowid

    conn.commit()
    conn.close()

    return deal_id


# =========================================================
# ПОЛУЧИТЬ ИЛИ СОЗДАТЬ СДЕЛКУ
#
# ВАЖНО:
# Именно эту функцию будем использовать в bot.py.
#
# Она не создаёт новую сделку каждый раз,
# если у клиента уже есть активная сделка.
# =========================================================

def get_or_create_deal(client_id, partner_id):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Сначала проверяем активную сделку
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM deals
        WHERE client_id = ?
          AND partner_id = ?
          AND status != 'Завершена'
        ORDER BY id DESC
        LIMIT 1
    """, (
        client_id,
        partner_id
    ))

    existing = cur.fetchone()

    if existing:

        deal_id = existing[0]

        conn.close()

        return deal_id

    # -----------------------------------------------------
    # Проверяем партнёра
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
          AND is_partner = 1
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        conn.close()

        return None

    # -----------------------------------------------------
    # Проверяем, что клиент действительно закреплён
    # за этим партнёром
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
          AND invited_by = ?
    """, (
        client_id,
        partner_id
    ))

    client = cur.fetchone()

    if not client:

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
        VALUES (?, ?, 'Новая', 0, ?)
    """, (
        client_id,
        partner_id,
        now_full()
    ))

    deal_id = cur.lastrowid

    conn.commit()
    conn.close()

    return deal_id


# =========================================================
# ПОЛУЧИТЬ АКТИВНУЮ СДЕЛКУ КЛИЕНТА
# =========================================================

def get_active_deal(client_id):

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
        WHERE client_id = ?
          AND status != 'Завершена'
        ORDER BY id DESC
        LIMIT 1
    """, (client_id,))

    deal = cur.fetchone()

    conn.close()

    return deal


# =========================================================
# ПОЛУЧИТЬ СДЕЛКУ КЛИЕНТА
# =========================================================

def get_client_deal(client_id):

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
        WHERE client_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (client_id,))

    deal = cur.fetchone()

    conn.close()

    return deal


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
# ПОЛУЧИТЬ СДЕЛКИ ПАРТНЁРА
# =========================================================

def get_partner_deals(partner_id):

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
        WHERE partner_id = ?
        ORDER BY id DESC
    """, (partner_id,))

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
# Повторное завершение невозможно.
# Это защищает от двойного начисления комиссии.
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
        now_full(),
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
    # История
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
        now_full()
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


# =========================================================
# ЗАЯВКИ НА АВТО
# =========================================================

def create_car_request(client_id, deal_id=None):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Если заявка уже существует — возвращаем её ID
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM car_requests
        WHERE client_id = ?
    """, (client_id,))

    existing = cur.fetchone()

    if existing:

        # Если появилась сделка — привязываем её
        if deal_id is not None:

            cur.execute("""
                UPDATE car_requests
                SET
                    deal_id = ?,
                    updated_at = ?
                WHERE client_id = ?
            """, (
                deal_id,
                now_full(),
                client_id
            ))

            conn.commit()

        conn.close()

        return existing[0]

    # -----------------------------------------------------
    # Создаём новую заявку
    # -----------------------------------------------------

    cur.execute("""
        INSERT INTO car_requests (
            client_id,
            deal_id,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'Новая', ?, ?)
    """, (
        client_id,
        deal_id,
        now_full(),
        now_full()
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    return request_id


# =========================================================
# ПОЛУЧИТЬ ИЛИ СОЗДАТЬ ЗАЯВКУ
# =========================================================

def get_or_create_car_request(client_id, deal_id=None):

    return create_car_request(
        client_id=client_id,
        deal_id=deal_id
    )


# =========================================================
# ОБНОВИТЬ ПОЛЕ ЗАЯВКИ
# =========================================================

def update_car_request(client_id, field, value):

    # -----------------------------------------------------
    # Разрешённые поля.
    #
    # Это важно для безопасности:
    # нельзя передать произвольное имя SQL-колонки.
    # -----------------------------------------------------

    allowed_fields = {
        "country",
        "car_type",
        "brand",
        "model",
        "budget",
        "year_from",
        "mileage",
        "engine",
        "fuel",
        "drive",
        "body",
        "additional",
        "free_text",
        "status"
    }

    if field not in allowed_fields:
        return False

    conn = connect()
    cur = conn.cursor()

    query = f"""
        UPDATE car_requests
        SET
            {field} = ?,
            updated_at = ?
        WHERE client_id = ?
    """

    cur.execute(query, (
        value,
        now_full(),
        client_id
    ))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed > 0


# =========================================================
# ОБНОВИТЬ СРАЗУ НЕСКОЛЬКО ПОЛЕЙ ЗАЯВКИ
# =========================================================

def update_car_request_fields(client_id, **fields):

    allowed_fields = {
        "country",
        "car_type",
        "brand",
        "model",
        "budget",
        "year_from",
        "mileage",
        "engine",
        "fuel",
        "drive",
        "body",
        "additional",
        "free_text",
        "status"
    }

    if not fields:
        return False

    safe_fields = {}

    for field, value in fields.items():

        if field in allowed_fields:
            safe_fields[field] = value

    if not safe_fields:
        return False

    conn = connect()
    cur = conn.cursor()

    set_parts = []
    values = []

    for field, value in safe_fields.items():

        set_parts.append(f"{field} = ?")
        values.append(value)

    set_parts.append("updated_at = ?")
    values.append(now_full())

    values.append(client_id)

    query = f"""
        UPDATE car_requests
        SET {", ".join(set_parts)}
        WHERE client_id = ?
    """

    cur.execute(query, values)

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed > 0


# =========================================================
# ПОЛУЧИТЬ ЗАЯВКУ КЛИЕНТА
# =========================================================

def get_car_request(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            deal_id,
            country,
            car_type,
            brand,
            model,
            budget,
            year_from,
            mileage,
            engine,
            fuel,
            drive,
            body,
            additional,
            free_text,
            status,
            created_at,
            updated_at
        FROM car_requests
        WHERE client_id = ?
    """, (client_id,))

    result = cur.fetchone()

    conn.close()

    return result


# =========================================================
# ПОЛУЧИТЬ ЗАЯВКУ ПО ID
# =========================================================

def get_car_request_by_id(request_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            deal_id,
            country,
            car_type,
            brand,
            model,
            budget,
            year_from,
            mileage,
            engine,
            fuel,
            drive,
            body,
            additional,
            free_text,
            status,
            created_at,
            updated_at
        FROM car_requests
        WHERE id = ?
    """, (request_id,))

    result = cur.fetchone()

    conn.close()

    return result


# =========================================================
# ПОЛУЧИТЬ ЗАЯВКУ ПО СДЕЛКЕ
# =========================================================

def get_car_request_by_deal(deal_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            deal_id,
            country,
            car_type,
            brand,
            model,
            budget,
            year_from,
            mileage,
            engine,
            fuel,
            drive,
            body,
            additional,
            free_text,
            status,
            created_at,
            updated_at
        FROM car_requests
        WHERE deal_id = ?
    """, (deal_id,))

    result = cur.fetchone()

    conn.close()

    return result


# =========================================================
# ЗАВЕРШИТЬ ЗАЯВКУ
# =========================================================

def complete_car_request(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE car_requests
        SET
            status = 'Заполнена',
            updated_at = ?
        WHERE client_id = ?
    """, (
        now_full(),
        client_id
    ))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed > 0


# =========================================================
# ИЗМЕНИТЬ СТАТУС ЗАЯВКИ
# =========================================================

def set_request_status(request_id, status):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE car_requests
        SET
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        status,
        now_full(),
        request_id
    ))

    changed = cur.rowcount

    conn.commit()
    conn.close()

    return changed > 0


# =========================================================
# ЗАЯВКИ ПАРТНЁРА
# =========================================================

def get_partner_requests(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            cr.id,
            cr.client_id,
            cr.deal_id,
            cr.country,
            cr.car_type,
            cr.brand,
            cr.model,
            cr.budget,
            cr.year_from,
            cr.mileage,
            cr.engine,
            cr.fuel,
            cr.drive,
            cr.body,
            cr.additional,
            cr.free_text,
            cr.status,
            cr.created_at
        FROM car_requests cr
        JOIN deals d
            ON d.id = cr.deal_id
        WHERE d.partner_id = ?
        ORDER BY cr.id DESC
    """, (partner_id,))

    data = cur.fetchall()

    conn.close()

    return data


# =========================================================
# ВСЕ ЗАЯВКИ
# =========================================================

def get_all_car_requests():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            deal_id,
            country,
            car_type,
            brand,
            model,
            budget,
            year_from,
            mileage,
            engine,
            fuel,
            drive,
            body,
            additional,
            free_text,
            status,
            created_at,
            updated_at
        FROM car_requests
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    conn.close()

    return data


# =========================================================
# НОВЫЕ ЗАЯВКИ
# =========================================================

def get_new_car_requests():

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            deal_id,
            country,
            car_type,
            brand,
            model,
            budget,
            year_from,
            mileage,
            engine,
            fuel,
            drive,
            body,
            additional,
            free_text,
            status,
            created_at,
            updated_at
        FROM car_requests
        WHERE status = 'Новая'
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    conn.close()

    return data


# =========================================================
# КОЛИЧЕСТВО ЗАЯВОК ПАРТНЁРА
# =========================================================

def get_partner_requests_count(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM car_requests cr
        JOIN deals d
            ON d.id = cr.deal_id
        WHERE d.partner_id = ?
    """, (partner_id,))

    result = cur.fetchone()

    conn.close()

    return result[0] if result else 0


# =========================================================
# СТАТИСТИКА
# =========================================================

def get_statistics():

    conn = connect()
    cur = conn.cursor()

    # Пользователи
    cur.execute("""
        SELECT COUNT(*)
        FROM users
    """)

    users_count = cur.fetchone()[0]

    # Партнёры
    cur.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE is_partner = 1
    """)

    partners_count = cur.fetchone()[0]

    # Клиенты
    cur.execute("""
        SELECT COUNT(*)
        FROM clients
    """)

    clients_count = cur.fetchone()[0]

    # Сделки
    cur.execute("""
        SELECT COUNT(*)
        FROM deals
    """)

    deals_count = cur.fetchone()[0]

    # Активные сделки
    cur.execute("""
        SELECT COUNT(*)
        FROM deals
        WHERE status != 'Завершена'
    """)

    active_deals_count = cur.fetchone()[0]

    # Завершённые сделки
    cur.execute("""
        SELECT COUNT(*)
        FROM deals
        WHERE status = 'Завершена'
    """)

    completed_deals_count = cur.fetchone()[0]

    # Заявки
    cur.execute("""
        SELECT COUNT(*)
        FROM car_requests
    """)

    requests_count = cur.fetchone()[0]

    # Новые заявки
    cur.execute("""
        SELECT COUNT(*)
        FROM car_requests
        WHERE status = 'Новая'
    """)

    new_requests_count = cur.fetchone()[0]

    # Общий баланс
    cur.execute("""
        SELECT COALESCE(SUM(balance), 0)
        FROM users
        WHERE is_partner = 1
    """)

    total_balance = cur.fetchone()[0]

    # Выплаченные комиссии
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE type = 'Комиссия'
    """)

    total_commission = cur.fetchone()[0]

    conn.close()

    return {
        "users": users_count,
        "partners": partners_count,
        "clients": clients_count,
        "deals": deals_count,
        "active_deals": active_deals_count,
        "completed_deals": completed_deals_count,
        "requests": requests_count,
        "new_requests": new_requests_count,
        "total_balance": total_balance,
        "total_commission": total_commission
    }


# =========================================================
# ПРОВЕРКА / ИСПРАВЛЕНИЕ СВЯЗИ КЛИЕНТА
# =========================================================

def ensure_client_connection(client_id, partner_id):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Проверяем партнёра
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
          AND is_partner = 1
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        conn.close()

        return False

    # -----------------------------------------------------
    # Проверяем клиента
    # -----------------------------------------------------

    cur.execute("""
        SELECT
            telegram_id,
            invited_by
        FROM users
        WHERE telegram_id = ?
    """, (client_id,))

    client = cur.fetchone()

    if not client:

        conn.close()

        return False

    # -----------------------------------------------------
    # Если клиент уже закреплён за другим партнёром,
    # НИКОГДА его не переносим.
    # -----------------------------------------------------

    if client[1] is not None and client[1] != partner_id:

        conn.close()

        return False

    # -----------------------------------------------------
    # Закрепляем
    # -----------------------------------------------------

    if client[1] is None:

        cur.execute("""
            UPDATE users
            SET invited_by = ?
            WHERE telegram_id = ?
        """, (
            partner_id,
            client_id
        ))

    # -----------------------------------------------------
    # Добавляем в clients
    # -----------------------------------------------------

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
        now_full()
    ))

    conn.commit()
    conn.close()

    return True
