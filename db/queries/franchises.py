import aiosqlite


async def get_franchise(db: aiosqlite.Connection, franchise_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM franchises WHERE id = ?", (franchise_id,))
    return await cursor.fetchone()


async def get_franchise_by_token(db: aiosqlite.Connection, bot_token: str) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM franchises WHERE bot_token = ?", (bot_token,))
    return await cursor.fetchone()


async def get_franchise_by_owner(db: aiosqlite.Connection, owner_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM franchises WHERE owner_id = ?", (owner_id,))
    return await cursor.fetchone()


async def get_all_franchises(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM franchises ORDER BY created_at DESC")
    return await cursor.fetchall()


async def get_active_franchises(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM franchises WHERE is_active = 1 ORDER BY id")
    return await cursor.fetchall()


async def create_franchise(
    db: aiosqlite.Connection,
    owner_id: int,
    bot_token: str,
    bot_username: str | None,
    name: str,
) -> int:
    cursor = await db.execute(
        """INSERT INTO franchises (owner_id, bot_token, bot_username, name)
           VALUES (?, ?, ?, ?)""",
        (owner_id, bot_token, bot_username, name),
    )
    await db.commit()
    return cursor.lastrowid


async def update_franchise(db: aiosqlite.Connection, franchise_id: int, **kwargs) -> None:
    allowed = {"name", "bot_token", "bot_username", "is_active",
               "commission_owner_product", "commission_own_product"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [franchise_id]
    await db.execute(f"UPDATE franchises SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def delete_franchise(db: aiosqlite.Connection, franchise_id: int) -> None:
    await db.execute("DELETE FROM franchises WHERE id = ?", (franchise_id,))
    await db.commit()


async def record_commission(
    db: aiosqlite.Connection,
    franchise_id: int,
    order_id: int,
    product_type: str,
    sale_amount: float,
    commission_rate: float,
    commission_amount: float,
    beneficiary_id: int,
) -> int:
    cursor = await db.execute(
        """INSERT INTO franchise_commissions
           (franchise_id, order_id, product_type, sale_amount, commission_rate, commission_amount, beneficiary_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (franchise_id, order_id, product_type, sale_amount, commission_rate, commission_amount, beneficiary_id),
    )
    await db.commit()
    return cursor.lastrowid


async def get_franchise_commissions(
    db: aiosqlite.Connection, franchise_id: int, offset: int = 0, limit: int = 20,
) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT fc.*, o.created_at as order_date
           FROM franchise_commissions fc
           LEFT JOIN orders o ON fc.order_id = o.id
           WHERE fc.franchise_id = ?
           ORDER BY fc.created_at DESC LIMIT ? OFFSET ?""",
        (franchise_id, limit, offset),
    )
    return await cursor.fetchall()


async def get_franchise_stats(db: aiosqlite.Connection, franchise_id: int) -> dict:
    # Total orders through this franchise
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(total_price), 0) as total FROM orders WHERE franchise_id = ?",
        (franchise_id,),
    )
    row = await cursor.fetchone()
    order_count = row["cnt"]
    total_sales = row["total"]

    # Total commissions earned by franchisee
    cursor = await db.execute(
        """SELECT COALESCE(SUM(commission_amount), 0) as total
           FROM franchise_commissions WHERE franchise_id = ? AND beneficiary_id > 0""",
        (franchise_id,),
    )
    row = await cursor.fetchone()
    total_earned = row["total"]

    # Total owner commissions
    cursor = await db.execute(
        """SELECT COALESCE(SUM(commission_amount), 0) as total
           FROM franchise_commissions WHERE franchise_id = ? AND beneficiary_id = 0""",
        (franchise_id,),
    )
    row = await cursor.fetchone()
    owner_earned = row["total"]

    # Unique buyers through this franchise
    cursor = await db.execute(
        "SELECT COUNT(DISTINCT user_id) as cnt FROM orders WHERE franchise_id = ?",
        (franchise_id,),
    )
    row = await cursor.fetchone()
    user_count = row["cnt"]

    return {
        "order_count": order_count,
        "total_sales": total_sales,
        "total_earned": total_earned,
        "owner_earned": owner_earned,
        "user_count": user_count,
    }
