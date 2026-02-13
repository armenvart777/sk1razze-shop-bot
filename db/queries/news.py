import aiosqlite


async def get_published_news(db: aiosqlite.Connection, limit: int = 5) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM news WHERE is_published = 1 ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    return await cursor.fetchall()


async def get_all_news(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM news ORDER BY created_at DESC")
    return await cursor.fetchall()


async def get_news_item(db: aiosqlite.Connection, news_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM news WHERE id = ?", (news_id,))
    return await cursor.fetchone()


async def create_news(
    db: aiosqlite.Connection,
    title: str,
    content: str,
    image_file_id: str | None = None,
) -> int:
    cursor = await db.execute(
        "INSERT INTO news (title, content, image_file_id) VALUES (?, ?, ?)",
        (title, content, image_file_id),
    )
    await db.commit()
    return cursor.lastrowid


async def update_news(db: aiosqlite.Connection, news_id: int, **kwargs) -> None:
    allowed = {"title", "content", "image_file_id", "is_published"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [news_id]
    await db.execute(f"UPDATE news SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def delete_news(db: aiosqlite.Connection, news_id: int) -> None:
    await db.execute("DELETE FROM news WHERE id = ?", (news_id,))
    await db.commit()


async def toggle_news(db: aiosqlite.Connection, news_id: int) -> None:
    await db.execute(
        "UPDATE news SET is_published = CASE WHEN is_published = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (news_id,),
    )
    await db.commit()
