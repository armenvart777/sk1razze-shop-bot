import aiosqlite


async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    cursor = await db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()


async def get_all_settings(db: aiosqlite.Connection) -> dict[str, str]:
    cursor = await db.execute("SELECT key, value FROM bot_settings")
    rows = await cursor.fetchall()
    return {r["key"]: r["value"] for r in rows}
