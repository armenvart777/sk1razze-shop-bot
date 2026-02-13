import aiohttp

BASE_URL = "https://pay.crypt.bot/api"


async def create_invoice(
    amount: float,
    currency: str = "USDT",
    description: str = "Пополнение баланса",
    payload: str = "",
    token: str = "",
) -> dict | None:
    if not token:
        return None
    headers = {"Crypto-Pay-API-Token": token}
    params = {
        "asset": currency,
        "amount": str(amount),
        "description": description,
        "payload": payload,
        "allow_anonymous": True,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_URL}/createInvoice", headers=headers, json=params) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data["result"]
            return None


async def get_invoice_status(invoice_id: int, token: str = "") -> dict | None:
    if not token:
        return None
    headers = {"Crypto-Pay-API-Token": token}
    params = {"invoice_ids": str(invoice_id)}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/getInvoices", headers=headers, params=params) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"].get("items"):
                return data["result"]["items"][0]
            return None
