import aiohttp

BASE_URL = "https://api.lzt.market"


async def create_payment_link(amount: float, comment: str = "", profile: str = "") -> str | None:
    """Generate a Lolz payment link using the profile URL."""
    if not profile:
        return None
    # Extract user ID from profile URL like https://lolz.live/members/9493832/
    profile = profile.rstrip("/")
    user_id = profile.split("/")[-1]
    amount_int = int(amount) if amount == int(amount) else amount
    return f"https://lolz.live/market/balance/transfer?user_id={user_id}&amount={amount_int}&comment={comment}&hold=0"


async def check_payment(comment: str, token: str = "") -> bool:
    """Check if payment with given comment was received via Lolz API."""
    if not token:
        return False
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/user/payments",
                headers=headers,
                params={"type": "income", "comment": comment},
            ) as resp:
                data = await resp.json()
                if data.get("payments"):
                    return True
    except Exception:
        pass
    return False
