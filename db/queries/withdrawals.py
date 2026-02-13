import aiosqlite


async def create_withdrawal(
    db: aiosqlite.Connection,
    franchise_id: int,
    user_id: int,
    amount: float,
    details: str,
) -> int:
    cursor = await db.execute(
        """INSERT INTO withdrawal_requests (franchise_id, user_id, amount, details)
           VALUES (?, ?, ?, ?)""",
        (franchise_id, user_id, amount, details),
    )
    await db.commit()
    return cursor.lastrowid


async def get_pending_withdrawals(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT wr.*, f.name as franchise_name, u.username
           FROM withdrawal_requests wr
           JOIN franchises f ON wr.franchise_id = f.id
           JOIN users u ON wr.user_id = u.id
           WHERE wr.status = 'pending'
           ORDER BY wr.created_at""",
    )
    return await cursor.fetchall()


async def get_withdrawal(db: aiosqlite.Connection, pk: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """SELECT wr.*, f.name as franchise_name, u.username
           FROM withdrawal_requests wr
           JOIN franchises f ON wr.franchise_id = f.id
           JOIN users u ON wr.user_id = u.id
           WHERE wr.id = ?""",
        (pk,),
    )
    return await cursor.fetchone()


async def update_withdrawal_status(
    db: aiosqlite.Connection, pk: int, status: str,
) -> None:
    await db.execute(
        "UPDATE withdrawal_requests SET status = ?, processed_at = datetime('now') WHERE id = ?",
        (status, pk),
    )
    await db.commit()


async def get_user_withdrawals(
    db: aiosqlite.Connection, user_id: int, limit: int = 10,
) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT * FROM withdrawal_requests
           WHERE user_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    )
    return await cursor.fetchall()


async def has_pending_withdrawal(db: aiosqlite.Connection, user_id: int) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM withdrawal_requests WHERE user_id = ? AND status = 'pending' LIMIT 1",
        (user_id,),
    )
    return await cursor.fetchone() is not None
