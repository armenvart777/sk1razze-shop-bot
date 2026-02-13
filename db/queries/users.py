import aiosqlite


async def get_user(db: aiosqlite.Connection, user_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return await cursor.fetchone()


async def create_user(
    db: aiosqlite.Connection,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    referrer_id: int | None = None,
) -> None:
    await db.execute(
        """INSERT OR IGNORE INTO users (id, username, first_name, last_name, referrer_id)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, username, first_name, last_name, referrer_id),
    )
    if referrer_id:
        await db.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE id = ?",
            (referrer_id,),
        )
    await db.commit()


async def update_user_activity(db: aiosqlite.Connection, user_id: int, username: str | None) -> None:
    await db.execute(
        "UPDATE users SET last_active_at = datetime('now'), username = ? WHERE id = ?",
        (username, user_id),
    )
    await db.commit()


async def update_balance(db: aiosqlite.Connection, user_id: int, amount: float) -> None:
    await db.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, user_id),
    )
    if amount > 0:
        await db.execute(
            "UPDATE users SET total_deposited = total_deposited + ? WHERE id = ?",
            (amount, user_id),
        )
    await db.commit()


async def set_balance(db: aiosqlite.Connection, user_id: int, amount: float) -> None:
    await db.execute("UPDATE users SET balance = ? WHERE id = ?", (amount, user_id))
    await db.commit()


async def get_all_user_ids(db: aiosqlite.Connection) -> list[int]:
    cursor = await db.execute("SELECT id FROM users WHERE is_banned = 0")
    rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def get_user_count(db: aiosqlite.Connection) -> int:
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
    row = await cursor.fetchone()
    return row["cnt"]


async def get_users_page(db: aiosqlite.Connection, offset: int = 0, limit: int = 10) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM users ORDER BY registered_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return await cursor.fetchall()


async def toggle_ban(db: aiosqlite.Connection, user_id: int) -> bool:
    user = await get_user(db, user_id)
    if not user:
        return False
    new_val = 0 if user["is_banned"] else 1
    await db.execute("UPDATE users SET is_banned = ? WHERE id = ?", (new_val, user_id))
    await db.commit()
    return True


async def search_user(db: aiosqlite.Connection, query: str) -> aiosqlite.Row | None:
    if query.isdigit():
        return await get_user(db, int(query))
    q = query.lstrip("@")
    cursor = await db.execute("SELECT * FROM users WHERE username = ?", (q,))
    return await cursor.fetchone()
