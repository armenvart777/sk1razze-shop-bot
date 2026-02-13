import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")

_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _connection
    if _connection is None:
        _connection = await aiosqlite.connect(DB_PATH)
        _connection.row_factory = aiosqlite.Row
        await _connection.execute("PRAGMA journal_mode=WAL")
        await _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


async def close_db():
    global _connection
    if _connection:
        await _connection.close()
        _connection = None


async def init_db():
    db = await get_db()

    await db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY,
        username        TEXT,
        first_name      TEXT,
        last_name       TEXT,
        balance         REAL    NOT NULL DEFAULT 0.0,
        total_deposited REAL    NOT NULL DEFAULT 0.0,
        referrer_id     INTEGER,
        referral_count  INTEGER NOT NULL DEFAULT 0,
        is_banned       INTEGER NOT NULL DEFAULT 0,
        registered_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        last_active_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (referrer_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS categories (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id   INTEGER,
        name        TEXT    NOT NULL,
        emoji       TEXT    DEFAULT '',
        sort_order  INTEGER NOT NULL DEFAULT 0,
        is_active   INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS products (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id     INTEGER NOT NULL,
        name            TEXT    NOT NULL,
        description     TEXT    NOT NULL DEFAULT '',
        price           REAL    NOT NULL,
        image_file_id   TEXT,
        is_active       INTEGER NOT NULL DEFAULT 1,
        is_infinite     INTEGER NOT NULL DEFAULT 0,
        stock_count     INTEGER NOT NULL DEFAULT 0,
        delivery_text   TEXT,
        delivery_file_id TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS product_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id  INTEGER NOT NULL,
        content     TEXT    NOT NULL,
        file_id     TEXT,
        is_sold     INTEGER NOT NULL DEFAULT 0,
        sold_to     INTEGER,
        sold_at     TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (sold_to) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS orders (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        product_id      INTEGER NOT NULL,
        product_item_id INTEGER,
        quantity        INTEGER NOT NULL DEFAULT 1,
        total_price     REAL    NOT NULL,
        promo_code_id   INTEGER,
        discount_amount REAL    NOT NULL DEFAULT 0.0,
        status          TEXT    NOT NULL DEFAULT 'completed',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
        FOREIGN KEY (product_item_id) REFERENCES product_items(id) ON DELETE SET NULL,
        FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS payments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        method          TEXT    NOT NULL,
        external_id     TEXT,
        amount          REAL    NOT NULL,
        currency        TEXT    NOT NULL DEFAULT 'RUB',
        status          TEXT    NOT NULL DEFAULT 'pending',
        paid_at         TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        raw_data        TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS promo_codes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        code            TEXT    NOT NULL UNIQUE,
        discount_type   TEXT    NOT NULL DEFAULT 'fixed',
        discount_value  REAL    NOT NULL,
        max_uses        INTEGER NOT NULL DEFAULT 1,
        current_uses    INTEGER NOT NULL DEFAULT 0,
        min_order_amount REAL   NOT NULL DEFAULT 0.0,
        is_active       INTEGER NOT NULL DEFAULT 1,
        expires_at      TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS promo_usages (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_code_id INTEGER NOT NULL,
        user_id       INTEGER NOT NULL,
        order_id      INTEGER,
        used_at       TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS dynamic_texts (
        key           TEXT    PRIMARY KEY,
        value         TEXT    NOT NULL,
        description   TEXT    NOT NULL DEFAULT '',
        photo_file_id TEXT,
        updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS news (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        content     TEXT    NOT NULL,
        image_file_id TEXT,
        is_published INTEGER NOT NULL DEFAULT 1,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS bot_settings (
        key     TEXT PRIMARY KEY,
        value   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS franchises (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id        INTEGER NOT NULL,
        bot_token       TEXT    NOT NULL UNIQUE,
        bot_username    TEXT,
        name            TEXT    NOT NULL,
        is_active       INTEGER NOT NULL DEFAULT 0,
        commission_owner_product  REAL NOT NULL DEFAULT 0.5,
        commission_own_product    REAL NOT NULL DEFAULT 5.0,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS private_channels (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT    NOT NULL,
        channel_id      INTEGER NOT NULL,
        description     TEXT    DEFAULT '',
        price           REAL    NOT NULL,
        duration_days   INTEGER NOT NULL,
        tier            TEXT    DEFAULT 'regular',
        is_active       INTEGER DEFAULT 1,
        franchise_id    INTEGER,
        created_by      INTEGER NOT NULL,
        image_file_id   TEXT,
        product_id      INTEGER,
        created_at      TEXT    DEFAULT (datetime('now')),
        FOREIGN KEY (franchise_id) REFERENCES franchises(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS private_subscriptions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        channel_id      INTEGER NOT NULL,
        order_id        INTEGER,
        started_at      TEXT    DEFAULT (datetime('now')),
        expires_at      TEXT    NOT NULL,
        is_active       INTEGER DEFAULT 1,
        invite_link     TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (channel_id) REFERENCES private_channels(id)
    );

    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        franchise_id    INTEGER NOT NULL,
        user_id         INTEGER NOT NULL,
        amount          REAL    NOT NULL,
        details         TEXT    NOT NULL DEFAULT '',
        status          TEXT    NOT NULL DEFAULT 'pending',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        processed_at    TEXT,
        FOREIGN KEY (franchise_id) REFERENCES franchises(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS franchise_commissions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        franchise_id    INTEGER NOT NULL,
        order_id        INTEGER NOT NULL,
        product_type    TEXT    NOT NULL,
        sale_amount     REAL    NOT NULL,
        commission_rate REAL    NOT NULL,
        commission_amount REAL  NOT NULL,
        beneficiary_id  INTEGER NOT NULL,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (franchise_id) REFERENCES franchises(id) ON DELETE CASCADE,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS franchise_broadcasts (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        franchise_id    INTEGER NOT NULL,
        owner_id        INTEGER NOT NULL,
        message_type    TEXT    NOT NULL DEFAULT 'text',
        text_content    TEXT,
        photo_file_id   TEXT,
        caption         TEXT,
        status          TEXT    NOT NULL DEFAULT 'pending',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (franchise_id) REFERENCES franchises(id) ON DELETE CASCADE
    );
    """)

    # Migration: add photo_file_id to dynamic_texts if missing
    cursor = await db.execute("PRAGMA table_info(dynamic_texts)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "photo_file_id" not in columns:
        await db.execute("ALTER TABLE dynamic_texts ADD COLUMN photo_file_id TEXT")

    # Migration: add is_infinite to products if missing
    cursor = await db.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "is_infinite" not in columns:
        await db.execute("ALTER TABLE products ADD COLUMN is_infinite INTEGER NOT NULL DEFAULT 0")

    # Migration: add franchise_id to products if missing
    cursor = await db.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "franchise_id" not in columns:
        await db.execute("ALTER TABLE products ADD COLUMN franchise_id INTEGER REFERENCES franchises(id)")

    # Migration: add franchise_id to orders if missing
    cursor = await db.execute("PRAGMA table_info(orders)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "franchise_id" not in columns:
        await db.execute("ALTER TABLE orders ADD COLUMN franchise_id INTEGER REFERENCES franchises(id)")

    # Migration: add is_template to product_items if missing
    cursor = await db.execute("PRAGMA table_info(product_items)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "is_template" not in columns:
        await db.execute("ALTER TABLE product_items ADD COLUMN is_template INTEGER DEFAULT 0")

    # Migration: add franchise_id to payments if missing
    cursor = await db.execute("PRAGMA table_info(payments)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "franchise_id" not in columns:
        await db.execute("ALTER TABLE payments ADD COLUMN franchise_id INTEGER REFERENCES franchises(id)")

    # Migration: add product_id to private_channels if missing
    cursor = await db.execute("PRAGMA table_info(private_channels)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "product_id" not in columns:
        await db.execute("ALTER TABLE private_channels ADD COLUMN product_id INTEGER REFERENCES products(id)")

    # Migration: replace news_empty with news_text
    cursor = await db.execute("SELECT 1 FROM dynamic_texts WHERE key = 'news_text'")
    if not await cursor.fetchone():
        await db.execute("DELETE FROM dynamic_texts WHERE key = 'news_empty'")
        await db.execute(
            "INSERT OR IGNORE INTO dynamic_texts (key, value, description) VALUES (?, ?, ?)",
            ("news_text", "📰 Все новости публикуются в нашем канале!\n\nПодпишитесь, чтобы не пропустить обновления.", "Текст раздела новостей"),
        )

    # Seed default texts
    default_texts = [
        ("welcome_message", "Добро пожаловать в Sk1razze Store!", "Приветственное сообщение после согласия с офертой"),
        ("offer_text", "Перед началом:\nОзнакомьтесь с нашим публичным договором оферты:", "Текст перед ссылкой на оферту"),
        ("subscription_required", "Для использования бота необходимо подписаться на канал", "Текст требования подписки"),
        ("main_menu_text", "Главное меню", "Текст над кнопками главного меню"),
        ("shop_header", "Доступные категории:", "Заголовок раздела магазина"),
        ("profile_template", "Ваш Профиль:\n👤 Юзер: @{username}\n🆔 ID: {user_id}\n💰 Баланс: {balance}₽\n💸 Всего пополнено: {total_deposited}₽\n📅 Дата регистрации: {registered_at}\n👥 Рефералов: {referral_count} чел", "Шаблон профиля"),
        ("btn_shop", "🛍 Купить", "Кнопка магазина"),
        ("btn_profile", "👤 Профиль", "Кнопка профиля"),
        ("btn_news", "📌 Новости", "Кнопка новостей"),
        ("btn_support", "💎 Саппорт", "Кнопка поддержки"),
        ("btn_topup", "💰 Пополнить баланс", "Кнопка пополнения"),
        ("btn_reviews", "⭐Отзывы⭐", "Кнопка отзывов"),
        ("btn_back", "◀️ Вернуться", "Кнопка назад"),
        ("topup_header", "Выбери способ пополнения:", "Заголовок выбора оплаты"),
        ("topup_enter_amount", "Введите сумму пополнения (от {min}₽ до 100000₽):", "Запрос суммы пополнения"),
        ("purchase_success", "Покупка успешна! Заказ #{order_id}", "Сообщение об успешной покупке"),
        ("insufficient_balance", "Недостаточно средств. Пополните баланс.", "Недостаточно средств"),
        ("support_text", "Чтобы обратиться в Тех. Поддержку нажмите кнопку ниже:", "Текст поддержки"),
        ("reviews_text", "Отзывы на товары Sk1razze Store:", "Текст отзывов"),
        ("news_text", "📰 Все новости публикуются в нашем канале!\n\nПодпишитесь, чтобы не пропустить обновления.", "Текст раздела новостей"),
    ]

    for key, value, desc in default_texts:
        await db.execute(
            "INSERT OR IGNORE INTO dynamic_texts (key, value, description) VALUES (?, ?, ?)",
            (key, value, desc),
        )

    # Seed default settings
    default_settings = [
        ("payment_crypto_bot_enabled", "1"),
        ("payment_lolz_enabled", "1"),
        ("payment_sbp_enabled", "0"),
        ("payment_stars_enabled", "0"),
        ("sbp_details", "Реквизиты не заданы. Настройте в админ-панели."),
        ("stars_rate", "1.5"),
        ("referral_bonus_percent", "5"),
        ("min_topup_amount", "50"),
        ("crypto_bot_token", os.getenv("CRYPTO_BOT_TOKEN", "")),
        ("lolz_token", os.getenv("LOLZ_TOKEN", "")),
        ("lolz_profile", os.getenv("LOLZ_PROFILE", "")),
        ("channel_username", os.getenv("CHANNEL_USERNAME", "")),
        ("offer_url", os.getenv("OFFER_URL", "")),
        ("support_url", os.getenv("SUPPORT_URL", "")),
        ("reviews_url", os.getenv("REVIEWS_URL", "")),
    ]

    for key, value in default_settings:
        await db.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    # Migrations for existing databases
    try:
        await db.execute("ALTER TABLE products ADD COLUMN delivery_text TEXT")
    except Exception:
        pass
    try:
        await db.execute("ALTER TABLE products ADD COLUMN delivery_file_id TEXT")
    except Exception:
        pass

    await db.commit()
