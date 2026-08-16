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
            is_partner INTEGER DEFAULT 0,
            created_at TEXT
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
    # ЗАЯВКИ НА АВТО
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS car_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            client_id INTEGER UNIQUE,
            partner_id INTEGER,
            deal_id INTEGER,

            country TEXT,
            budget TEXT,
            brand_model TEXT,
            year_from TEXT,
            year_to TEXT,
            power TEXT,
            fuel TEXT,
            body TEXT,
            gearbox TEXT,
            drive TEXT,
            mileage TEXT,
            color TEXT,
            additional TEXT,

            status TEXT DEFAULT 'Заполняется',

            created_at TEXT,
            updated_at TEXT
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

    if "created_at" not in user_columns:

        try:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN created_at TEXT
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
        CREATE INDEX IF NOT EXISTS idx_transactions_partner
        ON transactions(partner_id)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_requests_partner
        ON car_requests(partner_id)
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

        # Нельзя пригласить самого себя
        if invited_by == telegram_id:
            invited_by = None

        # Проверяем пригласившего
        if invited_by is not None:

            cur.execute("""
                SELECT telegram_id
                FROM users
                WHERE telegram_id = ?
            """, (invited_by,))

            partner_exists = cur.fetchone()

            if not partner_exists:
                invited_by = None

        # -------------------------------------------------
        # Создаём пользователя
        # -------------------------------------------------

        cur.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                full_name,
                balance,
                invited_by,
                is_partner,
                created_at
            )
            VALUES (?, ?, ?, 0, ?, 0, ?)
        """, (
            telegram_id,
            username,
            full_name,
            invited_by,
            now_full()
        ))

        # -------------------------------------------------
        # ВАЖНО:
        # если пришёл по реферальной ссылке —
        # сразу создаём клиента
        # -------------------------------------------------

        if invited_by is not None:

            cur.execute("""
                INSERT OR IGNORE INTO clients (
                    telegram_id,
                    partner_id,
                    created_at
                )
                VALUES (?, ?, ?)
            """, (
                telegram_id,
                invited_by,
                now_full()
            ))

    # =====================================================
    # ПОЛЬЗОВАТЕЛЬ УЖЕ СУЩЕСТВУЕТ
    # =====================================================

    else:

        current_invited_by = existing[1]

        # -------------------------------------------------
        # Обновляем данные Telegram
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
        # Если партнёр ещё НЕ закреплён
        # -------------------------------------------------

        if current_invited_by is None:

            if invited_by is not None and invited_by != telegram_id:

                cur.execute("""
                    SELECT
                        telegram_id,
                        is_partner
                    FROM users
                    WHERE telegram_id = ?
                """, (invited_by,))

                partner = cur.fetchone()

                if partner:

                    # Закрепляем партнёра
                    cur.execute("""
                        UPDATE users
                        SET invited_by = ?
                        WHERE telegram_id = ?
                    """, (
                        invited_by,
                        telegram_id
                    ))

                    # Создаём клиента
                    cur.execute("""
                        INSERT OR IGNORE INTO clients (
                            telegram_id,
                            partner_id,
                            created_at
                        )
                        VALUES (?, ?, ?)
                    """, (
                        telegram_id,
                        invited_by,
                        now_full()
                    ))

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
# ПРОВЕРИТЬ — ЯВЛЯЕТСЯ ЛИ ПОЛЬЗОВАТЕЛЬ КЛИЕНТОМ
# =========================================================

def is_client(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT telegram_id
        FROM clients
        WHERE telegram_id = ?
    """, (telegram_id,))

    result = cur.fetchone()

    conn.close()

    return result is not None


# =========================================================
# УДАЛИТЬ ПОЛЬЗОВАТЕЛЯ
# =========================================================

def delete_user(telegram_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM transactions
        WHERE partner_id = ?
    """, (telegram_id,))

    cur.execute("""
        DELETE FROM deals
        WHERE client_id = ?
           OR partner_id = ?
    """, (
        telegram_id,
        telegram_id
    ))

    cur.execute("""
        DELETE FROM car_requests
        WHERE client_id = ?
           OR partner_id = ?
    """, (
        telegram_id,
        telegram_id
    ))

    cur.execute("""
        DELETE FROM clients
        WHERE telegram_id = ?
           OR partner_id = ?
    """, (
        telegram_id,
        telegram_id
    ))

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

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (partner_id,))

    user = cur.fetchone()

    if not user:

        conn.close()
        return False

    cur.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE telegram_id = ?
    """, (
        amount,
        partner_id
    ))

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
    # Проверяем, что партнёр существует
    # -----------------------------------------------------

    cur.execute("""
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
    """, (partner_id,))

    partner = cur.fetchone()

    if not partner:

        if own_connection:
            connection.close()

        return False

    # -----------------------------------------------------
    # Клиент
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
# ПОЛУЧИТЬ КЛИЕНТОВ ПАРТНЁРА
# =========================================================

def get_clients(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.telegram_id,
            u.username,
            u.full_name
        FROM users u
        INNER JOIN clients c
            ON c.telegram_id = u.telegram_id
        WHERE c.partner_id = ?
        ORDER BY c.id DESC
    """, (partner_id,))

    users = cur.fetchall()

    conn.close()

    return users


# =========================================================
# ПОЛУЧИТЬ КЛИЕНТА
# =========================================================

def get_client(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.telegram_id,
            u.username,
            u.full_name,
            c.partner_id,
            c.created_at
        FROM users u
        INNER JOIN clients c
            ON c.telegram_id = u.telegram_id
        WHERE u.telegram_id = ?
    """, (client_id,))

    result = cur.fetchone()

    conn.close()

    return result


# =========================================================
# СДЕЛКИ
# =========================================================

def create_deal(client_id, partner_id=None):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Если партнёр не передан —
    # берём его из реферальной привязки клиента
    # -----------------------------------------------------

    if partner_id is None:

        cur.execute("""
            SELECT invited_by
            FROM users
            WHERE telegram_id = ?
        """, (client_id,))

        result = cur.fetchone()

        if not result:

            conn.close()
            return None

        partner_id = result[0]

    # -----------------------------------------------------
    # Без партнёра сделку создавать нельзя
    # -----------------------------------------------------

    if partner_id is None:

        conn.close()
        return None

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
    # Проверяем привязку клиента
    # -----------------------------------------------------

    cur.execute("""
        SELECT partner_id
        FROM clients
        WHERE telegram_id = ?
    """, (client_id,))

    client_link = cur.fetchone()

    if client_link:

        # Нельзя передать клиента другому партнёру
        if client_link[0] != partner_id:

            conn.close()
            return None

    else:

        # Если записи клиента нет — создаём
        cur.execute("""
            INSERT INTO clients (
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

    # -----------------------------------------------------
    # Проверяем, нет ли активной сделки
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM deals
        WHERE client_id = ?
          AND status != 'Завершена'
        ORDER BY id DESC
        LIMIT 1
    """, (client_id,))

    existing_deal = cur.fetchone()

    if existing_deal:

        conn.close()
        return existing_deal[0]

    # -----------------------------------------------------
    # Создаём новую сделку
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
        now_full()
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
            commission,
            created_at,
            completed_at
        FROM deals
        ORDER BY id DESC
    """)

    data = cur.fetchall()

    conn.close()

    return data


# =========================================================
# СДЕЛКИ ПАРТНЁРА
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
# АКТИВНАЯ СДЕЛКА КЛИЕНТА
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
# =========================================================
# ЗАЯВКА НА АВТО
# =========================================================
# =========================================================


# =========================================================
# СОЗДАТЬ / ПОЛУЧИТЬ ЗАЯВКУ
# =========================================================

def get_or_create_car_request(client_id):

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Уже существует
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM car_requests
        WHERE client_id = ?
    """, (client_id,))

    existing = cur.fetchone()

    if existing:

        request_id = existing[0]

        conn.close()

        return request_id

    # -----------------------------------------------------
    # Получаем партнёра
    # -----------------------------------------------------

    cur.execute("""
        SELECT invited_by
        FROM users
        WHERE telegram_id = ?
    """, (client_id,))

    user = cur.fetchone()

    if not user:

        conn.close()
        return None

    partner_id = user[0]

    # -----------------------------------------------------
    # Получаем / создаём сделку
    # -----------------------------------------------------

    deal_id = None

    if partner_id:

        # Проверяем партнёра
        cur.execute("""
            SELECT is_partner
            FROM users
            WHERE telegram_id = ?
        """, (partner_id,))

        partner = cur.fetchone()

        if partner and partner[0] == 1:

            cur.execute("""
                SELECT id
                FROM deals
                WHERE client_id = ?
                  AND status != 'Завершена'
                ORDER BY id DESC
                LIMIT 1
            """, (client_id,))

            deal = cur.fetchone()

            if deal:

                deal_id = deal[0]

            else:

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

    # -----------------------------------------------------
    # Создаём заявку
    # -----------------------------------------------------

    cur.execute("""
        INSERT INTO car_requests (
            client_id,
            partner_id,
            deal_id,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, 'Заполняется', ?, ?)
    """, (
        client_id,
        partner_id,
        deal_id,
        now_full(),
        now_full()
    ))

    request_id = cur.lastrowid

    conn.commit()
    conn.close()

    return request_id


# =========================================================
# СОХРАНИТЬ ОТВЕТ В ЗАЯВКЕ
# =========================================================

def update_car_request(client_id, field, value):

    allowed_fields = {
        "country",
        "budget",
        "brand_model",
        "year_from",
        "year_to",
        "power",
        "fuel",
        "body",
        "gearbox",
        "drive",
        "mileage",
        "color",
        "additional",
        "status"
    }

    if field not in allowed_fields:

        return False

    conn = connect()
    cur = conn.cursor()

    # -----------------------------------------------------
    # Если заявки нет — создаём
    # -----------------------------------------------------

    cur.execute("""
        SELECT id
        FROM car_requests
        WHERE client_id = ?
    """, (client_id,))

    request = cur.fetchone()

    if not request:

        conn.close()

        request_id = get_or_create_car_request(client_id)

        if not request_id:
            return False

        conn = connect()
        cur = conn.cursor()

    # -----------------------------------------------------
    # Обновляем поле
    # -----------------------------------------------------

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
# ПОЛУЧИТЬ ЗАЯВКУ
# =========================================================

def get_car_request(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            client_id,
            partner_id,
            deal_id,
            country,
            budget,
            brand_model,
            year_from,
            year_to,
            power,
            fuel,
            body,
            gearbox,
            drive,
            mileage,
            color,
            additional,
            status,
            created_at,
            updated_at
        FROM car_requests
        WHERE client_id = ?
    """, (client_id,))

    request = cur.fetchone()

    conn.close()

    return request


# =========================================================
# ЗАВЕРШИТЬ АНКЕТУ
# =========================================================

def complete_car_request(client_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        UPDATE car_requests
        SET
            status = 'Новая',
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
# ЗАЯВКИ ПАРТНЁРА
# =========================================================

def get_partner_requests(partner_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            r.id,
            r.client_id,
            r.deal_id,
            r.country,
            r.budget,
            r.brand_model,
            r.year_from,
            r.year_to,
            r.power,
            r.fuel,
            r.body,
            r.gearbox,
            r.drive,
            r.mileage,
            r.color,
            r.additional,
            r.status,
            r.created_at,

            u.username,
            u.full_name

        FROM car_requests r

        LEFT JOIN users u
            ON u.telegram_id = r.client_id

        WHERE r.partner_id = ?

        ORDER BY r.id DESC
    """, (partner_id,))

    data = cur.fetchall()

    conn.close()

    return data


# =========================================================
# ПОЛУЧИТЬ ЗАЯВКУ ПО ID
# =========================================================

def get_car_request_by_id(request_id):

    conn = connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            r.id,
            r.client_id,
            r.partner_id,
            r.deal_id,
            r.country,
            r.budget,
            r.brand_model,
            r.year_from,
            r.year_to,
            r.power,
            r.fuel,
            r.body,
            r.gearbox,
            r.drive,
            r.mileage,
            r.color,
            r.additional,
            r.status,
            r.created_at,
            r.updated_at,

            u.username,
            u.full_name

        FROM car_requests r

        LEFT JOIN users u
            ON u.telegram_id = r.client_id

        WHERE r.id = ?
    """, (request_id,))

    request = cur.fetchone()

    conn.close()

    return request


# =========================================================
# СТАТУС ЗАЯВКИ
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
