from aiogram.fsm.state import State, StatesGroup


class FranchiseProductStates(StatesGroup):
    choosing_category = State()
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_image = State()


class FranchiseEditProductStates(StatesGroup):
    choosing_field = State()
    waiting_value = State()


class FranchiseItemStates(StatesGroup):
    waiting_content = State()


class FranchiseDeliveryStates(StatesGroup):
    waiting_content = State()


class FranchiseCreatePublicStates(StatesGroup):
    waiting_name = State()
    waiting_token = State()
