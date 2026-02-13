import aiosqlite


async def get_stats(db: aiosqlite.Connection) -> dict:
    stats = {}

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
    stats["total_users"] = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE registered_at >= datetime('now', '-1 day')"
    )
    stats["new_users_24h"] = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE registered_at >= datetime('now', '-7 days')"
    )
    stats["new_users_7d"] = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM orders")
    stats["total_orders"] = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE created_at >= datetime('now', '-1 day')"
    )
    stats["orders_24h"] = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COALESCE(SUM(total_price), 0) as total FROM orders"
    )
    stats["total_revenue"] = (await cursor.fetchone())["total"]

    cursor = await db.execute(
        "SELECT COALESCE(SUM(total_price), 0) as total FROM orders WHERE created_at >= datetime('now', '-1 day')"
    )
    stats["revenue_24h"] = (await cursor.fetchone())["total"]

    cursor = await db.execute(
        "SELECT COALESCE(SUM(total_price), 0) as total FROM orders WHERE created_at >= datetime('now', '-7 days')"
    )
    stats["revenue_7d"] = (await cursor.fetchone())["total"]

    cursor = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'paid'"
    )
    stats["total_deposited"] = (await cursor.fetchone())["total"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM promo_codes WHERE is_active = 1"
    )
    stats["active_promos"] = (await cursor.fetchone())["cnt"]

    return stats
