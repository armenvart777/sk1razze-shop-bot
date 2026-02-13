from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.callbacks import PaginationCB


def paginate(
    items: list,
    page: int,
    per_page: int = 8,
    target: str = "",
) -> tuple[list, int, bool, bool]:
    """Returns (page_items, total_pages, has_prev, has_next)."""
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    return items[start:end], total_pages, page > 0, page < total_pages - 1


def add_pagination_row(
    builder: InlineKeyboardBuilder,
    page: int,
    total_pages: int,
    has_prev: bool,
    has_next: bool,
    target: str,
) -> None:
    """Add prev/next navigation buttons to a keyboard builder."""
    if total_pages <= 1:
        return
    nav = []
    if has_prev:
        nav.append(InlineKeyboardButton(
            text="◀️",
            callback_data=PaginationCB(target=target, page=page - 1).pack(),
        ))
    nav.append(InlineKeyboardButton(
        text=f"{page + 1}/{total_pages}",
        callback_data="noop",
    ))
    if has_next:
        nav.append(InlineKeyboardButton(
            text="▶️",
            callback_data=PaginationCB(target=target, page=page + 1).pack(),
        ))
    if nav:
        builder.row(*nav)
