def format_price(price: float) -> str:
    if price == int(price):
        return f"{int(price)}₽"
    return f"{price:.2f}₽"


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def truncate(text: str, max_len: int = 50) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
