from aiogram.fsm.state import State, StatesGroup


class AdminCategoryStates(StatesGroup):
    waiting_parent = State()
    waiting_emoji = State()
    waiting_name = State()
    waiting_sort_order = State()
    confirming = State()


class AdminEditCategoryStates(StatesGroup):
    choosing_field = State()
    waiting_value = State()


class AdminProductStates(StatesGroup):
    choosing_category = State()
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_image = State()
    confirming = State()


class AdminEditProductStates(StatesGroup):
    choosing_field = State()
    waiting_value = State()


class AdminDeliveryStates(StatesGroup):
    waiting_content = State()


class AdminItemStates(StatesGroup):
    waiting_content = State()


class AdminPromoStates(StatesGroup):
    waiting_code = State()
    waiting_discount_type = State()
    waiting_discount_value = State()
    waiting_max_uses = State()
    waiting_expiration = State()
    confirming = State()


class AdminTextStates(StatesGroup):
    waiting_new_value = State()
    waiting_photo = State()


class AdminBroadcastStates(StatesGroup):
    waiting_message = State()
    confirming = State()


class AdminNewsStates(StatesGroup):
    waiting_title = State()
    waiting_content = State()
    waiting_image = State()
    confirming = State()


class AdminUserSearchStates(StatesGroup):
    waiting_query = State()


class AdminBalanceAdjustStates(StatesGroup):
    waiting_amount = State()
    confirming = State()


class AdminBannerStates(StatesGroup):
    waiting_photo = State()


class AdminFranchiseStates(StatesGroup):
    waiting_user_id = State()
    waiting_bot_token = State()
    waiting_name = State()
    editing_rate = State()
    waiting_rate_value = State()
