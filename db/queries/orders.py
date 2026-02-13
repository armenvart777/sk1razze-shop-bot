import aiosqlite


async def create_order(
    db: aiosqlite.Connection,
    user_id: int,
    product_id: int,
    product_item_id: int,
    total_price: float,
    promo_code_id: int | None = None,
    discount_amount: float = 0.0,
    franchise_id: int | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO orders (user_id, product_id, product_item_id, total_price, promo_code_id, discount_amount, franchise_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, product_id, product_item_id, total_price, promo_code_id, discount_amount, franchise_id),
    )
    await db.commit()
    return cursor.lastrowid


async def get_user_orders(db: aiosqlite.Connection, user_id: int, offset: int = 0, limit: int = 10) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT o.*, p.name as product_name
           FROM orders o LEFT JOIN products p ON o.product_id = p.id
           WHERE o.user_id = ? ORDER BY o.created_at DESC LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    )
    return await cursor.fetchall()


async def get_order(db: aiosqlite.Connection, order_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """SELECT o.*, p.name as product_name
           FROM orders o LEFT JOIN products p ON o.product_id = p.id
           WHERE o.id = ?""",
        (order_id,),
    )
    return await cursor.fetchone()


async def get_all_orders(db: aiosqlite.Connection, offset: int = 0, limit: int = 10) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT o.*, p.name as product_name, u.username
           FROM orders o
           LEFT JOIN products p ON o.product_id = p.id
           LEFT JOIN users u ON o.user_id = u.id
           ORDER BY o.created_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    )
    return await cursor.fetchall()


async def get_order_count(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM orders")
    row = await cursor.fetchone()
    return row["cnt"]


async def get_user_order_count(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return row["cnt"]


async def get_franchise_orders(
    db: aiosqlite.Connection, franchise_id: int, offset: int = 0, limit: int = 10,
) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT o.*, p.name as product_name, u.username
           FROM orders o
           LEFT JOIN products p ON o.product_id = p.id
           LEFT JOIN users u ON o.user_id = u.id
           WHERE o.franchise_id = ?
           ORDER BY o.created_at DESC LIMIT ? OFFSET ?""",
        (franchise_id, limit, offset),
    )
    return await cursor.fetchall()


async def get_franchise_order_count(db: aiosqlite.Connection, franchise_id: int) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE franchise_id = ?", (franchise_id,),
    )
    row = await cursor.fetchone()
    return row["cnt"]
