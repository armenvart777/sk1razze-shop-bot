import aiosqlite


async def get_promo_by_code(db: aiosqlite.Connection, code: str) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM promo_codes WHERE code = ? AND is_active = 1",
        (code.upper(),),
    )
    return await cursor.fetchone()


async def get_promo(db: aiosqlite.Connection, promo_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM promo_codes WHERE id = ?", (promo_id,))
    return await cursor.fetchone()


async def get_all_promos(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
    return await cursor.fetchall()


async def create_promo(
    db: aiosqlite.Connection,
    code: str,
    discount_type: str,
    discount_value: float,
    max_uses: int = 1,
    expires_at: str | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO promo_codes (code, discount_type, discount_value, max_uses, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (code.upper(), discount_type, discount_value, max_uses, expires_at),
    )
    await db.commit()
    return cursor.lastrowid


async def delete_promo(db: aiosqlite.Connection, promo_id: int) -> None:
    await db.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))
    await db.commit()


async def toggle_promo(db: aiosqlite.Connection, promo_id: int) -> None:
    await db.execute(
        "UPDATE promo_codes SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (promo_id,),
    )
    await db.commit()


async def use_promo(db: aiosqlite.Connection, promo_id: int, user_id: int, order_id: int | None = None) -> None:
    await db.execute(
        "UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = ?",
        (promo_id,),
    )
    await db.execute(
        "INSERT INTO promo_usages (promo_code_id, user_id, order_id) VALUES (?, ?, ?)",
        (promo_id, user_id, order_id),
    )
    await db.commit()


async def has_user_used_promo(db: aiosqlite.Connection, promo_id: int, user_id: int) -> bool:
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM promo_usages WHERE promo_code_id = ? AND user_id = ?",
        (promo_id, user_id),
    )
    row = await cursor.fetchone()
    return row["cnt"] > 0
