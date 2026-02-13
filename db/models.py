from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    balance: float
    total_deposited: float
    referrer_id: Optional[int]
    referral_count: int
    is_banned: bool
    registered_at: str
    last_active_at: str


@dataclass
class Category:
    id: int
    parent_id: Optional[int]
    name: str
    emoji: str
    sort_order: int
    is_active: bool
    created_at: str


@dataclass
class Product:
    id: int
    category_id: int
    name: str
    description: str
    price: float
    image_file_id: Optional[str]
    is_active: bool
    stock_count: int
    created_at: str


@dataclass
class ProductItem:
    id: int
    product_id: int
    content: str
    file_id: Optional[str]
    is_sold: bool
    sold_to: Optional[int]
    sold_at: Optional[str]


@dataclass
class Order:
    id: int
    user_id: int
    product_id: int
    product_item_id: Optional[int]
    quantity: int
    total_price: float
    promo_code_id: Optional[int]
    discount_amount: float
    status: str
    created_at: str


@dataclass
class Payment:
    id: int
    user_id: int
    method: str
    external_id: Optional[str]
    amount: float
    currency: str
    status: str
    paid_at: Optional[str]
    created_at: str
    raw_data: Optional[str]


@dataclass
class PromoCode:
    id: int
    code: str
    discount_type: str
    discount_value: float
    max_uses: int
    current_uses: int
    min_order_amount: float
    is_active: bool
    expires_at: Optional[str]
    created_at: str


@dataclass
class DynamicText:
    key: str
    value: str
    description: str
    updated_at: str


@dataclass
class News:
    id: int
    title: str
    content: str
    image_file_id: Optional[str]
    is_published: bool
    created_at: str
