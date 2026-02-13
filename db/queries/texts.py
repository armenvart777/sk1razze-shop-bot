import aiosqlite


async def get_text(db: aiosqlite.Connection, key: str) -> str:
    cursor = await db.execute("SELECT value FROM dynamic_texts WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else key


async def get_text_photo(db: aiosqlite.Connection, key: str) -> str | None:
    cursor = await db.execute("SELECT photo_file_id FROM dynamic_texts WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["photo_file_id"] if row else None


async def get_text_with_photo(db: aiosqlite.Connection, key: str) -> tuple[str, str | None]:
    cursor = await db.execute("SELECT value, photo_file_id FROM dynamic_texts WHERE key = ?", (key,))
    row = await cursor.fetchone()
    if row:
        return row["value"], row["photo_file_id"]
    return key, None


async def get_all_texts(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM dynamic_texts ORDER BY key")
    return await cursor.fetchall()


async def update_text(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "UPDATE dynamic_texts SET value = ?, updated_at = datetime('now') WHERE key = ?",
        (value, key),
    )
    await db.commit()


async def update_text_photo(db: aiosqlite.Connection, key: str, photo_file_id: str | None) -> None:
    await db.execute(
        "UPDATE dynamic_texts SET photo_file_id = ?, updated_at = datetime('now') WHERE key = ?",
        (photo_file_id, key),
    )
    await db.commit()


async def get_button_texts(db: aiosqlite.Connection) -> dict[str, str]:
    cursor = await db.execute("SELECT key, value FROM dynamic_texts WHERE key LIKE 'btn_%'")
    rows = await cursor.fetchall()
    return {r["key"]: r["value"] for r in rows}
