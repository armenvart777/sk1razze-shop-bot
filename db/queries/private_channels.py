import aiosqlite


async def get_active_channels(
    db: aiosqlite.Connection, franchise_id: int | None = None,
) -> list[aiosqlite.Row]:
    if franchise_id is not None:
        cursor = await db.execute(
            """SELECT * FROM private_channels
               WHERE is_active = 1 AND (franchise_id IS NULL OR franchise_id = ?)
               ORDER BY id""",
            (franchise_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM private_channels WHERE is_active = 1 AND franchise_id IS NULL ORDER BY id",
        )
    return await cursor.fetchall()


async def get_all_channels(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute("SELECT * FROM private_channels ORDER BY id")
    return await cursor.fetchall()


async def get_channel(db: aiosqlite.Connection, channel_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute("SELECT * FROM private_channels WHERE id = ?", (channel_id,))
    return await cursor.fetchone()


async def get_channel_by_product_id(db: aiosqlite.Connection, product_id: int) -> aiosqlite.Row | None:
    cursor = await db.execute(
        "SELECT * FROM private_channels WHERE product_id = ?", (product_id,),
    )
    return await cursor.fetchone()


async def create_channel(
    db: aiosqlite.Connection,
    name: str,
    channel_id: int,
    price: float,
    duration_days: int,
    created_by: int,
    description: str = "",
    franchise_id: int | None = None,
    image_file_id: str | None = None,
    product_id: int | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO private_channels
           (name, channel_id, price, duration_days, created_by, description, franchise_id, image_file_id, product_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, channel_id, price, duration_days, created_by, description, franchise_id, image_file_id, product_id),
    )
    await db.commit()
    return cursor.lastrowid


async def update_channel(db: aiosqlite.Connection, pk: int, **kwargs) -> None:
    allowed = {"name", "channel_id", "price", "duration_days", "description",
               "is_active", "image_file_id", "tier", "product_id"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [pk]
    await db.execute(f"UPDATE private_channels SET {set_clause} WHERE id = ?", values)
    await db.commit()


async def delete_channel(db: aiosqlite.Connection, pk: int) -> None:
    await db.execute("DELETE FROM private_channels WHERE id = ?", (pk,))
    await db.commit()


async def get_franchise_channels(db: aiosqlite.Connection, franchise_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        "SELECT * FROM private_channels WHERE franchise_id = ? ORDER BY id",
        (franchise_id,),
    )
    return await cursor.fetchall()


# --- Subscriptions ---

async def create_subscription(
    db: aiosqlite.Connection,
    user_id: int,
    channel_id: int,
    expires_at: str,
    order_id: int | None = None,
    invite_link: str | None = None,
) -> int:
    cursor = await db.execute(
        """INSERT INTO private_subscriptions
           (user_id, channel_id, order_id, expires_at, invite_link)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, channel_id, order_id, expires_at, invite_link),
    )
    await db.commit()
    return cursor.lastrowid


async def get_active_subscription(
    db: aiosqlite.Connection, user_id: int, channel_id: int,
) -> aiosqlite.Row | None:
    cursor = await db.execute(
        """SELECT * FROM private_subscriptions
           WHERE user_id = ? AND channel_id = ? AND is_active = 1
           ORDER BY expires_at DESC LIMIT 1""",
        (user_id, channel_id),
    )
    return await cursor.fetchone()


async def get_user_subscriptions(db: aiosqlite.Connection, user_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT ps.*, pc.name as channel_name
           FROM private_subscriptions ps
           JOIN private_channels pc ON ps.channel_id = pc.id
           WHERE ps.user_id = ? AND ps.is_active = 1
           ORDER BY ps.expires_at""",
        (user_id,),
    )
    return await cursor.fetchall()


async def get_expired_subscriptions(db: aiosqlite.Connection) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT ps.*, pc.channel_id as tg_channel_id, pc.name as channel_name
           FROM private_subscriptions ps
           JOIN private_channels pc ON ps.channel_id = pc.id
           WHERE ps.is_active = 1 AND ps.expires_at <= datetime('now')""",
    )
    return await cursor.fetchall()


async def deactivate_subscription(db: aiosqlite.Connection, sub_id: int) -> None:
    await db.execute(
        "UPDATE private_subscriptions SET is_active = 0 WHERE id = ?", (sub_id,),
    )
    await db.commit()


async def get_channel_subscriptions(db: aiosqlite.Connection, channel_id: int) -> list[aiosqlite.Row]:
    cursor = await db.execute(
        """SELECT ps.*, u.username
           FROM private_subscriptions ps
           JOIN users u ON ps.user_id = u.id
           WHERE ps.channel_id = ? AND ps.is_active = 1
           ORDER BY ps.expires_at""",
        (channel_id,),
    )
    return await cursor.fetchall()
