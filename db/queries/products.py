import aiosqlite


async def get_products_by_category(db: aiosqlite.Connection, category_id: int, franchise_id: int | None = None) -> list[aiosqlite.Row]:
    if franchise_id is not None:
        cursor = await db.execute(
            """SELECT * FROM products WHERE category_id = ? AND is_active = 1
               AND (franchise_id IS NULL OR franchise_id = ?)
               ORDER BY franchise_id IS NOT NULL, id""",
            (category_id, franchise_id),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM products WHERE category_id = ? AND is_active = 1 AND franchise_id IS NULL ORDER BY id",
            (category_id,),
        )
    return await cursor.fetchall()


async def get_all_products_by_category(db: aiosqlite.Connection, category_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM products WHERE category_id = ? ORDER BY id",
        (category_id,),
    )
    return await cursor.fetchall()


async def get_product(db: aiosqlite.Connection, product_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    return await cursor.fetchone()


async def create_product(
    db: aiosqlite.Connection,
    category_id: int,
    name: str,
    description: str,
    price: float,
    image_file_id: str | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO products (category_id, name, description, price, image_file_id)
           VALUES (?, ?, ?, ?, ?)""",
        (category_id, name, description, price, image_file_id),
    )
    await db.commit()
    return cursor.lastrowid


async def update_product(db: aiosqlite.Connection, product_id: int, **kwargs) -> None:
    allowed = {"name", "description", "price", "image_file_id", "is_active", "is_infinite", "category_id", "delivery_text", "delivery_file_id"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [product_id]
    await db.execute(f"UPDATE products SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def delete_product(db: aiosqlite.Connection, product_id: int) -> None:
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()


async def update_stock_count(db: aiosqlite.Connection, product_id: int) -> None:
    await db.execute(
        """UPDATE products SET stock_count = (
            SELECT COUNT(*) FROM product_items WHERE product_id = ? AND is_sold = 0
        ) WHERE id = ?""",
        (product_id, product_id),
    )
    await db.commit()


async def get_available_item(db: aiosqlite.Connection, product_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM product_items WHERE product_id = ? AND is_sold = 0 LIMIT 1",
        (product_id,),
    )
    return await cursor.fetchone()


async def mark_item_sold(db: aiosqlite.Connection, item_id: int, user_id: int) -> None:
    await db.execute(
        "UPDATE product_items SET is_sold = 1, sold_to = ?, sold_at = datetime('now') WHERE id = ?",
        (user_id, item_id),
    )
    await db.commit()


async def add_product_items(db: aiosqlite.Connection, product_id: int, contents: list[str]) -> int:
    count = 0
    for content in contents:
        content = content.strip()
        if content:
            await db.execute(
                "INSERT INTO product_items (product_id, content) VALUES (?, ?)",
                (product_id, content),
            )
            count += 1
    await db.commit()
    await update_stock_count(db, product_id)
    return count


async def get_product_items(db: aiosqlite.Connection, product_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM product_items WHERE product_id = ? ORDER BY is_sold, id",
        (product_id,),
    )
    return await cursor.fetchall()


async def get_franchise_products(db: aiosqlite.Connection, franchise_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM products WHERE franchise_id = ? ORDER BY id",
        (franchise_id,),
    )
    return await cursor.fetchall()


async def create_franchise_product(
    db: aiosqlite.Connection,
    franchise_id: int,
    category_id: int,
    name: str,
    description: str,
    price: float,
    image_file_id: str | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO products (category_id, name, description, price, image_file_id, franchise_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (category_id, name, description, price, image_file_id, franchise_id),
    )
    await db.commit()
    return cursor.lastrowid


async def get_template_item(db: aiosqlite.Connection, product_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM product_items WHERE product_id = ? AND is_template = 1 LIMIT 1",
        (product_id,),
    )
    return await cursor.fetchone()


async def set_template_item(db: aiosqlite.Connection, item_id: int, is_template: bool) -> None:
    await db.execute(
        "UPDATE product_items SET is_template = ? WHERE id = ?",
        (1 if is_template else 0, item_id),
    )
    await db.commit()


async def delete_unsold_items(db: aiosqlite.Connection, product_id: int) -> int:
    cursor = await db.execute(
        "DELETE FROM product_items WHERE product_id = ? AND is_sold = 0",
        (product_id,),
    )
    await db.commit()
    await update_stock_count(db, product_id)
    return cursor.rowcount
