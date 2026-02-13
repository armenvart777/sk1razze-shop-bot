import aiosqlite


async def get_root_categories(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM categories WHERE parent_id IS NULL AND is_active = 1 ORDER BY sort_order, id"
    )
    return await cursor.fetchall()


async def get_all_root_categories(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM categories WHERE parent_id IS NULL ORDER BY sort_order, id"
    )
    return await cursor.fetchall()


async def get_subcategories(db: aiosqlite.Connection, parent_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM categories WHERE parent_id = ? AND is_active = 1 ORDER BY sort_order, id",
        (parent_id,),
    )
    return await cursor.fetchall()


async def get_all_subcategories(db: aiosqlite.Connection, parent_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM categories WHERE parent_id = ? ORDER BY sort_order, id",
        (parent_id,),
    )
    return await cursor.fetchall()


async def get_category(db: aiosqlite.Connection, cat_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM categories WHERE id = ?", (cat_id,))
    return await cursor.fetchone()


async def create_category(
    db: aiosqlite.Connection,
    name: str,
    emoji: str = "",
    parent_id: int | None = None,
    sort_order: int = 0,
) -> int:
    cursor = await db.execute(
        "INSERT INTO categories (name, emoji, parent_id, sort_order) VALUES (?, ?, ?, ?)",
        (name, emoji, parent_id, sort_order),
    )
    await db.commit()
    return cursor.lastrowid


async def update_category(db: aiosqlite.Connection, cat_id: int, **kwargs) -> None:
    allowed = {"name", "emoji", "sort_order", "is_active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [cat_id]
    await db.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def delete_category(db: aiosqlite.Connection, cat_id: int) -> None:
    await db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    await db.commit()


async def toggle_category(db: aiosqlite.Connection, cat_id: int) -> None:
    await db.execute(
        "UPDATE categories SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (cat_id,),
    )
    await db.commit()
