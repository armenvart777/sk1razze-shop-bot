import aiosqlite
import json


async def create_payment(
    db: aiosqlite.Connection,
    user_id: int,
    method: str,
    amount: float,
    currency: str = "RUB",
    external_id: str | None = None,
    franchise_id: int | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO payments (user_id, method, amount, currency, external_id, franchise_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, method, amount, currency, external_id, franchise_id),
    )
    await db.commit()
    return cursor.lastrowid


async def get_payment(db: aiosqlite.Connection, payment_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    return await cursor.fetchone()


async def get_payment_by_external(db: aiosqlite.Connection, method: str, external_id: str) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM payments WHERE method = ? AND external_id = ?",
        (method, external_id),
    )
    return await cursor.fetchone()


async def update_payment_status(
    db: aiosqlite.Connection,
    payment_id: int,
    status: str,
    raw_data: dict | None = None,
) -> None:
    if status == "paid":
        await db.execute(
            "UPDATE payments SET status = ?, paid_at = datetime('now'), raw_data = ? WHERE id = ?",
            (status, json.dumps(raw_data) if raw_data else None, payment_id),
        )
    else:
        await db.execute(
            "UPDATE payments SET status = ?, raw_data = ? WHERE id = ?",
            (status, json.dumps(raw_data) if raw_data else None, payment_id),
        )
    await db.commit()


async def update_payment_external_id(db: aiosqlite.Connection, payment_id: int, external_id: str) -> None:
    await db.execute(
        "UPDATE payments SET external_id = ? WHERE id = ?",
        (external_id, payment_id),
    )
    await db.commit()
